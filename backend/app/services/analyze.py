"""Analyze pipeline that matches the GPT-OSS technical specification."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.llm_salary_result import LlmSalaryResult
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, GptOssSalaryResult
from app.services.gpt_oss_client import GptOssClientError, gpt_oss_client
from app.services.preflight import (
    NoCandidateVacanciesError,
    find_llm_result_by_hash,
    preflight_salary_request,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OutputValidation:
    status: str
    output: GptOssSalaryResult | None
    raw_output: dict[str, Any]
    errors: list[str]


class AnalyzeService:
    """Orchestrates preflight, one model call, validation, and persistence."""

    async def analyze(
        self,
        *,
        db: AsyncSession,
        request: AnalyzeRequest,
        redis: aioredis.Redis | None = None,
    ) -> AnalyzeResponse:
        try:
            preflight = await preflight_salary_request(db, request)
        except NoCandidateVacanciesError as exc:
            return AnalyzeResponse(
                status="error",
                code="NO_CANDIDATE_VACANCIES",
                message=str(exc),
            )

        if preflight.existing_result is not None:
            return self._response_from_cached(preflight.existing_result)

        assert preflight.llm_input_payload is not None
        lock_key = f"llm_salary_result:{preflight.request_hash}"
        lock_acquired = await self._acquire_lock(redis, lock_key)
        if not lock_acquired:
            existing = await find_llm_result_by_hash(db, preflight.request_hash)
            if existing is not None:
                return self._response_from_cached(existing)
            return AnalyzeResponse(
                status="error",
                code="DUPLICATE_REQUEST",
                message="A request with the same request_hash is already being processed.",
            )

        try:
            raw_output = await gpt_oss_client.generate_once(preflight.llm_input_payload)
            validation = validate_gpt_oss_output(raw_output, preflight.llm_input_payload)
            output_payload = validation.output.model_dump(mode="json") if validation.output else validation.raw_output
            await self._save_result(
                db=db,
                request=request,
                input_payload=preflight.llm_input_payload,
                output_payload=output_payload,
                validation_status=validation.status,
                validation_errors=validation.errors,
            )
        except GptOssClientError:
            return AnalyzeResponse(
                status="error",
                code="MODEL_CALL_FAILED",
                message="Model service did not return a usable response.",
            )
        finally:
            await self._release_lock(redis, lock_key, lock_acquired=lock_acquired)

        if validation.status != "valid" or validation.output is None:
            return AnalyzeResponse(
                status="error",
                code="LLM_OUTPUT_VALIDATION_FAILED",
                message="The model returned a payload that does not match the expected schema.",
                validation_errors=validation.errors,
            )

        return AnalyzeResponse(status="success", source="gpt-oss-20b", data=validation.output)

    def _response_from_cached(self, result: LlmSalaryResult) -> AnalyzeResponse:
        if result.validation_status != "valid" or not result.output_payload:
            return AnalyzeResponse(
                status="error",
                source="cache",
                code="LLM_OUTPUT_VALIDATION_FAILED",
                message="Cached model output is invalid.",
                validation_errors=result.validation_errors or [],
            )

        try:
            output = GptOssSalaryResult.model_validate(result.output_payload)
        except ValidationError as exc:
            return AnalyzeResponse(
                status="error",
                source="cache",
                code="LLM_OUTPUT_VALIDATION_FAILED",
                message="Cached model output no longer matches the response schema.",
                validation_errors=[str(error) for error in exc.errors()],
            )

        return AnalyzeResponse(status="success", source="cache", data=output)

    async def _save_result(
        self,
        *,
        db: AsyncSession,
        request: AnalyzeRequest,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        validation_status: str,
        validation_errors: list[str],
    ) -> None:
        segment = input_payload["segment"]
        result = LlmSalaryResult(
            request_hash=input_payload["request_hash"],
            profile_snapshot=request.profile.model_dump(mode="json"),
            segment_key=segment["segment_key"],
            segment_data_version=segment["segment_data_version"],
            model_name=settings.GPT_OSS_MODEL_NAME,
            model_version=settings.GPT_OSS_MODEL_VERSION,
            prompt_version=settings.GPT_OSS_PROMPT_VERSION,
            input_payload=input_payload,
            output_payload=output_payload,
            validation_status=validation_status,
            validation_errors=validation_errors or None,
        )
        db.add(result)
        await db.flush()
        # Commit before releasing the Redis lock so another worker can see the
        # saved request_hash and will not make a second model call.
        await db.commit()

    async def _acquire_lock(self, redis: aioredis.Redis | None, lock_key: str) -> bool:
        if redis is None:
            return True
        acquired = await redis.set(lock_key, "1", nx=True, ex=300)
        return bool(acquired)

    async def _release_lock(self, redis: aioredis.Redis | None, lock_key: str, *, lock_acquired: bool) -> None:
        if redis is None or not lock_acquired:
            return
        await redis.delete(lock_key)


def validate_gpt_oss_output(raw_output: dict[str, Any], input_payload: dict[str, Any]) -> OutputValidation:
    errors: list[str] = []
    try:
        output = GptOssSalaryResult.model_validate(raw_output)
    except ValidationError as exc:
        return OutputValidation(
            status="failed",
            output=None,
            raw_output=raw_output,
            errors=[f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()],
        )

    if output.request_hash != input_payload["request_hash"]:
        errors.append("request_hash does not match input payload")

    input_segment = input_payload["segment"]
    if output.segment.segment_key != input_segment["segment_key"]:
        errors.append("segment.segment_key does not match input payload")
    if output.segment.segment_data_version != input_segment["segment_data_version"]:
        errors.append("segment.segment_data_version does not match input payload")

    market_sample = output.market_sample
    if market_sample.vacancies_used_for_estimation > market_sample.candidate_vacancies_received:
        errors.append("vacancies_used_for_estimation exceeds candidate_vacancies_received")

    input_vacancy_ids = {str(vacancy["id"]) for vacancy in input_payload["candidate_vacancies"]}
    unknown_used_ids = [
        vacancy_id for vacancy_id in market_sample.used_vacancy_ids if vacancy_id not in input_vacancy_ids
    ]
    if unknown_used_ids:
        errors.append(f"used_vacancy_ids are not present in candidate_vacancies: {unknown_used_ids}")

    if market_sample.candidate_vacancies_received != len(input_vacancy_ids):
        errors.append("candidate_vacancies_received does not match input candidate_vacancies length")

    return OutputValidation(
        status="valid" if not errors else "failed",
        output=output,
        raw_output=raw_output,
        errors=errors,
    )


analyze_service = AnalyzeService()
