"""Pydantic schemas for recommendation API contracts."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class RecommendationResponse(BaseModel):
    """Single LLM-generated recommendation."""

    id: uuid.UUID
    priority: int = Field(..., ge=1, le=5, examples=[1])
    category: Literal["hard_skill", "soft_skill", "formatting", "certification"] = Field(
        ..., examples=["hard_skill"]
    )
    title: str = Field(..., examples=["Добавьте навык Docker"])
    description: str = Field(
        ...,
        examples=["Docker — один из самых востребованных навыков для backend-разработчиков. "
                   "85% вакансий Senior Python Developer требуют его знание."],
    )
    impact: str = Field(..., examples=["+25 000 руб. к медиане"])
    action: str = Field(
        ...,
        examples=["Добавьте 'Docker' в раздел навыков и опишите опыт контейнеризации в блоке опыта работы."],
    )

    model_config = {"from_attributes": True}
