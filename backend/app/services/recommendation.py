"""LLM-powered recommendation generation using Anthropic Claude."""

from __future__ import annotations

import json
import logging
import uuid

from anthropic import AsyncAnthropic

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — эксперт по рынку труда и карьерный консультант.
Твоя задача: на основе профиля соискателя, предсказанной зарплатной вилки и SHAP-анализа
сгенерировать конкретные, измеримые рекомендации по улучшению резюме.

ПРАВИЛА:
1. Каждая рекомендация должна содержать конкретное действие, а НЕ размытые советы.
2. Указывай денежный эквивалент влияния на основе SHAP-данных.
3. Приоритет 1 = самый важный, 5 = наименее важный.
4. Категории: hard_skill, soft_skill, formatting, certification.
5. Отвечай СТРОГО в формате JSON-массива без markdown-разметки.

ФОРМАТ ОТВЕТА (JSON array):
[
  {
    "priority": 1,
    "category": "hard_skill",
    "title": "Краткий заголовок",
    "description": "Подробное обоснование почему это важно на рынке",
    "impact": "+XX 000 руб. к медиане",
    "action": "Конкретное действие в резюме"
  }
]
"""


class RecommendationService:
    """Generates structured resume improvement recommendations via Claude API."""

    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
        self.model = settings.ANTHROPIC_MODEL

    async def generate(
        self,
        job_title: str,
        skills: list[str],
        experience_years: float,
        location: str,
        salary_p50: int,
        shap_values: dict[str, float],
        counterfactuals: list[dict],
    ) -> list[dict]:
        """Generate recommendations from LLM based on profile + SHAP analysis."""
        if not self.client:
            logger.warning("Anthropic API key not set, returning template recommendations")
            return self._template_recommendations(shap_values)

        user_prompt = self._build_user_prompt(
            job_title, skills, experience_years, location, salary_p50, shap_values, counterfactuals
        )

        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw_text = message.content[0].text
            recommendations = json.loads(raw_text)

            # Assign UUIDs
            for rec in recommendations:
                rec["id"] = str(uuid.uuid4())

            return recommendations[:5]  # Max 5 recommendations

        except Exception as exc:
            logger.error("LLM recommendation generation failed: %s", exc)
            return self._template_recommendations(shap_values)

    def _build_user_prompt(
        self,
        job_title: str,
        skills: list[str],
        experience_years: float,
        location: str,
        salary_p50: int,
        shap_values: dict[str, float],
        counterfactuals: list[dict],
    ) -> str:
        """Assemble structured prompt from profile and ML outputs."""
        negative_shap = {k: v for k, v in shap_values.items() if v < 0}
        positive_shap = {k: v for k, v in shap_values.items() if v > 0}

        return f"""ПРОФИЛЬ СОИСКАТЕЛЯ:
- Должность: {job_title}
- Опыт: {experience_years} лет
- Навыки: {", ".join(skills)}
- Регион: {location}

ПРЕДСКАЗАННАЯ МЕДИАНА ЗАРПЛАТЫ: {salary_p50:,} руб.

SHAP-АНАЛИЗ (вклад признаков в зарплату):
Положительный вклад: {json.dumps(positive_shap, ensure_ascii=False)}
Отрицательный вклад (чего не хватает): {json.dumps(negative_shap, ensure_ascii=False)}

КОНТРФАКТУАЛЬНЫЕ ПУТИ РОСТА:
{json.dumps(counterfactuals, ensure_ascii=False) if counterfactuals else "Нет данных"}

Сгенерируй 3-5 рекомендаций в формате JSON-массива."""

    def _template_recommendations(self, shap_values: dict[str, float]) -> list[dict]:
        """Fallback template recommendations when LLM is unavailable."""
        recommendations = []
        sorted_shap = sorted(shap_values.items(), key=lambda x: x[1])

        for i, (feature, value) in enumerate(sorted_shap[:3], start=1):
            recommendations.append(
                {
                    "id": str(uuid.uuid4()),
                    "priority": i,
                    "category": "hard_skill",
                    "title": f"Улучшите показатель: {feature}",
                    "description": f"Признак '{feature}' снижает вашу оценку на {abs(int(value)):,} руб.",
                    "impact": f"+{abs(int(value)):,} руб. к медиане",
                    "action": f"Добавьте информацию о '{feature}' в ваше резюме.",
                }
            )

        return recommendations


recommendation_service = RecommendationService()
