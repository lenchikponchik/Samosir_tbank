"""Technical preflight for salary analysis requests."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.llm_salary_result import LlmSalaryResult
from app.models.market_segment import MarketSegment
from app.models.vacancy import Vacancy
from app.schemas.analyze import AnalyzeRequest, CandidateVacancy, GptOssInputPayload, ResumeProfile, SegmentPayload

SEGMENT_STALE_DAYS = 14
DEFAULT_CANDIDATE_LIMIT = 80


class NoCandidateVacanciesError(RuntimeError):
    """Raised when preflight cannot provide vacancies to the model."""


@dataclass(slots=True)
class SegmentParts:
    role_cluster: str
    specialization: str
    region: str
    experience_bucket: str

    @property
    def segment_key(self) -> str:
        return ":".join((self.role_cluster, self.specialization, self.region, self.experience_bucket))


@dataclass(slots=True)
class PreflightResult:
    request_hash: str
    segment_key: str
    segment_data_version: str
    llm_input_payload: dict[str, Any] | None = None
    existing_result: LlmSalaryResult | None = None


def build_segment_key(profile: ResumeProfile) -> str:
    """Build the technical segment key; no salary analytics happen here."""
    return _segment_parts(profile).segment_key


def is_stale(last_successful_update_at: datetime | None, *, days: int = SEGMENT_STALE_DAYS) -> bool:
    if last_successful_update_at is None:
        return True
    updated_at = last_successful_update_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - updated_at
    return age.days >= days


def calculate_request_hash(
    *,
    profile: ResumeProfile,
    segment_key: str,
    segment_data_version: str,
    model_version: str = settings.GPT_OSS_MODEL_VERSION,
    prompt_version: str = settings.GPT_OSS_PROMPT_VERSION,
) -> str:
    payload = {
        "profile": profile.model_dump(mode="json"),
        "segment_key": segment_key,
        "segment_data_version": segment_data_version,
        "model_version": model_version,
        "prompt_version": prompt_version,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def preflight_salary_request(db: AsyncSession, request: AnalyzeRequest) -> PreflightResult:
    """Prepare model input and enforce cache lookup before the model call."""
    profile = request.profile
    segment_parts = _segment_parts(profile)
    segment = await _get_or_create_segment(db, segment_parts)

    if request.options.force_refresh or is_stale(segment.last_successful_update_at):
        await refresh_segment_vacancies(db, segment)
        await db.flush()

    segment_data_version = segment.segment_data_version or datetime.now(timezone.utc).date().isoformat()
    request_hash = calculate_request_hash(
        profile=profile,
        segment_key=segment.segment_key,
        segment_data_version=segment_data_version,
    )

    existing_result = await find_llm_result_by_hash(db, request_hash)
    if existing_result is not None:
        return PreflightResult(
            request_hash=request_hash,
            segment_key=segment.segment_key,
            segment_data_version=segment_data_version,
            existing_result=existing_result,
        )

    candidate_vacancies = await get_candidate_vacancies(
        db=db,
        segment_key=segment.segment_key,
        limit=DEFAULT_CANDIDATE_LIMIT,
    )
    if not candidate_vacancies:
        raise NoCandidateVacanciesError(f"No candidate vacancies for segment {segment.segment_key}")

    payload = GptOssInputPayload(
        request_hash=request_hash,
        profile=profile.model_dump(mode="json"),
        segment=SegmentPayload(
            segment_key=segment.segment_key,
            segment_data_version=segment_data_version,
            last_successful_update_at=segment.last_successful_update_at,
        ),
        candidate_vacancies=candidate_vacancies,
        rules={
            "use_only_candidate_vacancies": True,
            "do_not_use_external_salary_knowledge": True,
            "return_only_json": True,
        },
    )
    return PreflightResult(
        request_hash=request_hash,
        segment_key=segment.segment_key,
        segment_data_version=segment_data_version,
        llm_input_payload=payload.model_dump(mode="json"),
    )


async def find_llm_result_by_hash(db: AsyncSession, request_hash: str) -> LlmSalaryResult | None:
    result = await db.execute(select(LlmSalaryResult).where(LlmSalaryResult.request_hash == request_hash))
    return result.scalar_one_or_none()


async def get_candidate_vacancies(db: AsyncSession, segment_key: str, limit: int) -> list[CandidateVacancy]:
    """Return candidate vacancies without final relevance or salary analytics."""
    query = (
        select(Vacancy)
        .where(Vacancy.segment_key == segment_key)
        .where(Vacancy.salary_currency == "RUB")
        .where(or_(Vacancy.salary_min_net.is_not(None), Vacancy.salary_max_net.is_not(None)))
        .order_by(Vacancy.published_at.desc().nullslast(), Vacancy.parsed_at.desc().nullslast())
        .limit(limit)
    )
    result = await db.execute(query)
    return [_vacancy_to_candidate(vacancy) for vacancy in result.scalars().all()]


async def refresh_segment_vacancies(db: AsyncSession, segment: MarketSegment) -> None:
    """Refresh segment metadata after the external parser has run.

    The actual parser/model work is intentionally outside backend logic for now.
    This hook keeps the backend contract ready for a segment-scoped parser call.
    """
    now = datetime.now(timezone.utc)
    count_result = await db.execute(select(func.count(Vacancy.id)).where(Vacancy.segment_key == segment.segment_key))
    segment.last_successful_update_at = now
    segment.segment_data_version = now.date().isoformat()
    segment.vacancies_count = int(count_result.scalar_one() or 0)


async def _get_or_create_segment(db: AsyncSession, parts: SegmentParts) -> MarketSegment:
    result = await db.execute(select(MarketSegment).where(MarketSegment.segment_key == parts.segment_key))
    segment = result.scalar_one_or_none()
    if segment is not None:
        return segment

    segment = MarketSegment(
        segment_key=parts.segment_key,
        role_cluster=parts.role_cluster,
        specialization=parts.specialization,
        region=parts.region,
        experience_bucket=parts.experience_bucket,
    )
    db.add(segment)
    await db.flush()
    return segment


def _vacancy_to_candidate(vacancy: Vacancy) -> CandidateVacancy:
    return CandidateVacancy(
        id=str(vacancy.id),
        title=vacancy.title,
        description=vacancy.description,
        salary_min_net=vacancy.salary_min_net,
        salary_max_net=vacancy.salary_max_net,
        location=vacancy.location,
        experience_range=vacancy.experience_range,
        skills_required=vacancy.skills_required or [],
        source=vacancy.source,
        published_at=vacancy.published_at,
    )


def _segment_parts(profile: ResumeProfile) -> SegmentParts:
    title = profile.title.casefold()
    skills = [skill.casefold() for skill in profile.skills]
    return SegmentParts(
        role_cluster=_role_cluster(title, skills),
        specialization=_specialization(title, skills),
        region=_region(profile.location),
        experience_bucket=_experience_bucket(profile.experience_years),
    )


def _role_cluster(title: str, skills: list[str]) -> str:
    text = " ".join([title, *skills])
    if any(token in text for token in ("backend", "back-end", "fastapi", "django", "python", "java", "go")):
        return "backend_developer"
    if any(token in text for token in ("frontend", "front-end", "react", "vue", "angular")):
        return "frontend_developer"
    if any(token in text for token in ("data", "ml", "machine learning", "аналитик")):
        return "data_specialist"
    if any(token in text for token in ("devops", "sre", "kubernetes", "terraform")):
        return "devops_engineer"
    return _slug(title, fallback="general_specialist")


def _specialization(title: str, skills: list[str]) -> str:
    text = " ".join([title, *skills])
    ordered = (
        "python",
        "java",
        "go",
        "javascript",
        "typescript",
        "react",
        "devops",
        "data",
        "ml",
        "postgresql",
    )
    for token in ordered:
        if token in text:
            return "machine_learning" if token == "ml" else token
    return _slug(skills[0] if skills else title, fallback="general")


def _region(location: str) -> str:
    normalized = location.casefold().strip()
    mapping = {
        "москва": "moscow",
        "moscow": "moscow",
        "санкт-петербург": "saint_petersburg",
        "санкт петербург": "saint_petersburg",
        "spb": "saint_petersburg",
        "remote": "remote",
        "удаленно": "remote",
        "удалённо": "remote",
    }
    return mapping.get(normalized, _slug(normalized, fallback="unknown_region"))


def _experience_bucket(experience_years: float) -> str:
    if experience_years < 2:
        return "junior"
    if experience_years < 5:
        return "middle"
    return "senior"


def _slug(value: str, *, fallback: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[^a-z0-9а-яё]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or fallback
