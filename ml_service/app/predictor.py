"""Stub predictor — deterministic heuristic that the ML developer will replace.

TODO for ML developer:
1. Load trained CatBoost/LightGBM models (.pkl or .onnx) in __init__
2. Implement real feature engineering in _build_feature_vector()
3. Replace predict() with actual model inference
4. Generate real SHAP values via TreeExplainer
5. Implement DiCE counterfactual generation
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas import Counterfactual, PredictionRequest, PredictionResponse

logger = logging.getLogger(__name__)

# Heuristic base salaries by rough keyword matching
ROLE_BASE_SALARIES: dict[str, int] = {
    "junior": 50_000,
    "middle": 90_000,
    "senior": 150_000,
    "lead": 200_000,
    "head": 250_000,
    "director": 300_000,
    "cto": 350_000,
    "default": 80_000,
}

LOCATION_MULTIPLIERS: dict[str, float] = {
    "москва": 1.3,
    "санкт-петербург": 1.15,
    "новосибирск": 0.85,
    "екатеринбург": 0.9,
    "казань": 0.85,
    "remote": 1.1,
    "default": 0.8,
}

HIGH_VALUE_SKILLS = {
    "kubernetes": 12_000,
    "docker": 8_000,
    "aws": 15_000,
    "gcp": 12_000,
    "python": 10_000,
    "go": 15_000,
    "rust": 18_000,
    "react": 8_000,
    "typescript": 7_000,
    "postgresql": 6_000,
    "kafka": 10_000,
    "spark": 12_000,
    "terraform": 10_000,
    "ci/cd": 5_000,
    "machine learning": 15_000,
}

EDUCATION_BONUS = {
    "none": 0,
    "bachelor": 5_000,
    "master": 12_000,
    "phd": 20_000,
}


class StubPredictor:
    """Deterministic heuristic predictor — placeholder for real ML models."""

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Generate a heuristic salary prediction."""
        # Base salary from role
        title_lower = request.job_title.lower()
        base = ROLE_BASE_SALARIES["default"]
        for level, salary in ROLE_BASE_SALARIES.items():
            if level in title_lower:
                base = salary
                break

        # Location multiplier
        loc_lower = request.location.lower()
        multiplier = LOCATION_MULTIPLIERS.get(loc_lower, LOCATION_MULTIPLIERS["default"])

        # Experience bonus
        exp_bonus = int(request.experience_years * 10_000)

        # Skill bonuses + SHAP
        shap_values: dict[str, float] = {}
        skill_total = 0
        user_skills_lower = {s.lower() for s in request.skills}

        for skill in request.skills:
            skill_lower = skill.lower()
            bonus = HIGH_VALUE_SKILLS.get(skill_lower, 3_000)
            skill_total += bonus
            shap_values[f"skills:{skill}"] = float(bonus)

        # Education
        edu_bonus = EDUCATION_BONUS.get(request.education_level, 0)

        # SHAP for non-skill features
        shap_values["experience_years"] = float(exp_bonus)
        shap_values[f"location:{request.location}"] = float(int(base * (multiplier - 1)))
        shap_values[f"education:{request.education_level}"] = float(edu_bonus)

        # Compute median
        p50 = int((base + exp_bonus + skill_total + edu_bonus) * multiplier)
        p25 = int(p50 * 0.75)
        p75 = int(p50 * 1.35)

        # Generate counterfactuals — suggest missing high-value skills
        counterfactuals = []
        for skill_name, bonus in sorted(HIGH_VALUE_SKILLS.items(), key=lambda x: -x[1]):
            if skill_name not in user_skills_lower and len(counterfactuals) < 3:
                counterfactuals.append(
                    Counterfactual(
                        change_description=f"Добавьте навык {skill_name.title()}",
                        feature_changed="skills",
                        new_value=skill_name.title(),
                        estimated_salary_increase=int(bonus * multiplier),
                    )
                )

        logger.info("Stub prediction: p50=%d for '%s'", p50, request.job_title)

        return PredictionResponse(
            p25_salary=p25,
            p50_salary=p50,
            p75_salary=p75,
            shap_values=shap_values,
            counterfactuals=counterfactuals,
        )

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a GPT-OSS-compatible JSON response for local development."""
        profile = payload["profile"]
        candidate_vacancies = payload["candidate_vacancies"]
        used_vacancies = candidate_vacancies[: min(5, len(candidate_vacancies))]

        salaries = [_salary_midpoint(v) for v in used_vacancies]
        salaries = sorted(s for s in salaries if s > 0)
        if not salaries:
            salaries = [100_000]

        p25 = _percentile(salaries, 0.25)
        p50 = _percentile(salaries, 0.50)
        p75 = _percentile(salaries, 0.75)

        profile_skills = {str(skill).casefold() for skill in profile.get("skills", [])}
        required_skills: list[str] = []
        for vacancy in used_vacancies:
            required_skills.extend(vacancy.get("skills_required") or [])

        matched_skills = []
        missing_skills = []
        seen_required: set[str] = set()
        for skill in required_skills:
            normalized = str(skill).casefold()
            if normalized in seen_required:
                continue
            seen_required.add(normalized)
            if normalized in profile_skills:
                matched_skills.append(str(skill))
            elif len(missing_skills) < 3:
                missing_skills.append(
                    {
                        "skill": str(skill),
                        "impact": "medium",
                        "reason": "Skill appears in the candidate vacancies provided to the model.",
                    }
                )

        if missing_skills:
            recommendations = [
                {
                    "priority": index + 1,
                    "type": "skill_gap",
                    "title": f"Add evidence for {item['skill']}",
                    "resume_change": f"Add {item['skill']} only with real experience and describe a concrete project.",
                    "expected_salary_effect": None,
                }
                for index, item in enumerate(missing_skills)
            ]
        else:
            recommendations = [
                {
                    "priority": 1,
                    "type": "experience_detail",
                    "title": "Add measurable project details",
                    "resume_change": "Describe scope, load, business result, and technologies for the strongest project.",
                    "expected_salary_effect": None,
                }
            ]

        used_ids = [str(v["id"]) for v in used_vacancies]
        excluded = [
            {"id": str(v["id"]), "reason": "Not used by the local stub because of the context limit."}
            for v in candidate_vacancies[len(used_vacancies) :]
        ]

        return {
            "request_hash": payload["request_hash"],
            "segment": {
                "segment_key": payload["segment"]["segment_key"],
                "segment_data_version": payload["segment"]["segment_data_version"],
            },
            "market_sample": {
                "candidate_vacancies_received": len(candidate_vacancies),
                "vacancies_used_for_estimation": len(used_vacancies),
                "used_vacancy_ids": used_ids,
                "excluded_vacancies": excluded,
                "salary_quantiles": {"p25": p25, "p50": p50, "p75": p75},
            },
            "salary_range": {
                "min": p25,
                "median": p50,
                "max": p75,
                "currency": "RUB",
            },
            "confidence": {
                "score": min(0.9, 0.45 + len(used_vacancies) / 100),
                "level": "medium" if len(used_vacancies) < 20 else "high",
                "reason": f"Local stub used {len(used_vacancies)} candidate vacancies.",
            },
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "factor_analysis": [
                {
                    "factor": f"Experience: {profile.get('experience_years')} years",
                    "impact": "neutral",
                    "explanation": "Temporary model stub; final interpretation belongs to gpt-oss-20b.",
                }
            ],
            "recommendations": recommendations,
        }


def _salary_midpoint(vacancy: dict[str, Any]) -> int:
    salary_min = vacancy.get("salary_min_net")
    salary_max = vacancy.get("salary_max_net")
    if salary_min and salary_max:
        return int((int(salary_min) + int(salary_max)) / 2)
    if salary_min:
        return int(salary_min)
    if salary_max:
        return int(salary_max)
    return 0


def _percentile(values: list[int], q: float) -> int:
    if len(values) == 1:
        return values[0]
    index = round((len(values) - 1) * q)
    return values[index]


predictor = StubPredictor()
