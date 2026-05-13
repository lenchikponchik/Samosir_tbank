"""Vacancy dataset ORM model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Vacancy(Base):
    """Market vacancy from external sources (hh.ru, etc.)."""

    __tablename__ = "vacancies_dataset"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_net: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skills_required: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    experience_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    parsed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
