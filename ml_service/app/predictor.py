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


predictor = StubPredictor()
