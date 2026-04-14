from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.db import Base

if TYPE_CHECKING:
    from app.persistence.models.job import Job


class JobStep(Base):
    __tablename__ = "job_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "step_index", name="uq_job_steps_job_id_step_index"),
        Index("ix_job_steps_job_id_step_index", "job_id", "step_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    step_index: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    output_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    job: Mapped[Job] = relationship("Job", back_populates="steps")
