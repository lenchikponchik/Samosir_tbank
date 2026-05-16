"""Tests for the GPT-OSS analyze contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.schemas.analyze import AnalyzeRequest, GptOssSalaryResult
from app.services.analyze import validate_gpt_oss_output
from app.services.preflight import build_segment_key, calculate_request_hash, is_stale


def _request() -> AnalyzeRequest:
    return AnalyzeRequest(
        profile={
            "title": "Python Backend Developer",
            "experience_years": 3,
            "location": "Москва",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "resume_text": "Built FastAPI services.",
            "current_salary": 150000,
        },
        options={"target_salary": 250000, "force_refresh": False},
    )


def _input_payload(request_hash: str) -> dict:
    return {
        "request_hash": request_hash,
        "profile": _request().profile.model_dump(mode="json"),
        "segment": {
            "segment_key": "backend_developer:python:moscow:middle",
            "segment_data_version": "2026-05-15",
            "last_successful_update_at": "2026-05-15T09:30:00Z",
        },
        "candidate_vacancies": [
            {
                "id": "v1",
                "title": "Python Backend Developer",
                "description": "FastAPI services",
                "salary_min_net": 180000,
                "salary_max_net": 250000,
                "location": "Москва",
                "experience_range": "3-6",
                "skills_required": ["Python", "FastAPI", "Docker"],
                "source": "hh",
                "published_at": "2026-05-10",
            }
        ],
        "rules": {
            "use_only_candidate_vacancies": True,
            "do_not_use_external_salary_knowledge": True,
            "return_only_json": True,
        },
    }


def _valid_output(request_hash: str) -> dict:
    return {
        "request_hash": request_hash,
        "segment": {
            "segment_key": "backend_developer:python:moscow:middle",
            "segment_data_version": "2026-05-15",
        },
        "market_sample": {
            "candidate_vacancies_received": 1,
            "vacancies_used_for_estimation": 1,
            "used_vacancy_ids": ["v1"],
            "excluded_vacancies": [],
            "salary_quantiles": {"p25": 180000, "p50": 210000, "p75": 250000},
        },
        "salary_range": {"min": 180000, "median": 210000, "max": 250000, "currency": "RUB"},
        "confidence": {"score": 0.8, "level": "high", "reason": "Fresh candidate vacancies."},
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": [{"skill": "Docker", "impact": "high", "reason": "Present in candidate vacancy."}],
        "factor_analysis": [
            {"factor": "Experience 3 years", "impact": "positive", "explanation": "Matches middle segment."}
        ],
        "recommendations": [
            {
                "priority": 1,
                "type": "skill_gap",
                "title": "Add Docker",
                "resume_change": "Add Docker only if there is real project experience.",
                "expected_salary_effect": None,
            }
        ],
    }


def test_segment_key_matches_spec_example():
    assert build_segment_key(_request().profile) == "backend_developer:python:moscow:middle"


def test_stale_after_14_days():
    assert is_stale(datetime.now(timezone.utc) - timedelta(days=14))
    assert not is_stale(datetime.now(timezone.utc) - timedelta(days=13, hours=23))


def test_request_hash_is_stable_for_same_payload():
    request = _request()
    first = calculate_request_hash(
        profile=request.profile,
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-15",
    )
    second = calculate_request_hash(
        profile=request.profile,
        segment_key="backend_developer:python:moscow:middle",
        segment_data_version="2026-05-15",
    )
    assert first == second
    assert len(first) == 64


def test_gpt_oss_result_schema_accepts_spec_payload():
    result = GptOssSalaryResult.model_validate(_valid_output("hash"))
    assert result.salary_range.currency == "RUB"
    assert result.recommendations[0].type == "skill_gap"


def test_output_validation_checks_linkage_to_input_payload():
    request_hash = "abc123"
    validation = validate_gpt_oss_output(_valid_output(request_hash), _input_payload(request_hash))
    assert validation.status == "valid"
    assert validation.errors == []


def test_output_validation_rejects_unknown_used_vacancy_id():
    request_hash = "abc123"
    output = _valid_output(request_hash)
    output["market_sample"]["used_vacancy_ids"] = ["missing"]
    validation = validate_gpt_oss_output(output, _input_payload(request_hash))
    assert validation.status == "failed"
    assert any("used_vacancy_ids" in error for error in validation.errors)
