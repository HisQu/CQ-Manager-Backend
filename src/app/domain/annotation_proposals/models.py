from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from advanced_alchemy.types import DateTimeUTC
from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import Boolean, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class AnnotationProposalRun(UUIDAuditBase):
    """One generated proposal set for a question revision and its review state."""

    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    question_id: Mapped[UUID] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"))
    question_version_id: Mapped[UUID] = mapped_column(ForeignKey("version.id", ondelete="CASCADE"))
    proposer_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTimeUTC(timezone=True), default=None)
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("user.id"), default=None)
    matcher_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    proposals: Mapped[list[AnnotationProposalItem]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AnnotationProposalItem.start"
    )


class AnnotationProposalItem(UUIDAuditBase):
    """A candidate span, its original glossary suggestion, and the user's eventual decision."""

    run_id: Mapped[UUID] = mapped_column(ForeignKey("annotation_proposal_run.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    start: Mapped[int]
    end: Mapped[int]
    lemma: Mapped[str] = mapped_column(Text)
    extraction_rule: Mapped[str] = mapped_column(Text)
    match_status: Mapped[str]
    match_score: Mapped[float | None] = mapped_column(Float, default=None)
    suggested_term: Mapped[str] = mapped_column(Text)
    suggested_term_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("term.id", ondelete="SET NULL"), default=None
    )
    suggested_term_is_new: Mapped[bool] = mapped_column(Boolean)
    token_data: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    span_accepted: Mapped[bool | None] = mapped_column(Boolean, default=None)
    term_accepted: Mapped[bool | None] = mapped_column(Boolean, default=None)
    final_term: Mapped[str | None] = mapped_column(Text, default=None)

    run: Mapped[AnnotationProposalRun] = relationship(back_populates="proposals")
