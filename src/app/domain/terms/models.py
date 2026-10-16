from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from domain.projects.models import Project
    from domain.versions.models import AnnotationVersion


class Term(UUIDAuditBase):
    __table_args__ = (UniqueConstraint("content", "project_id"),)

    content: Mapped[str] = mapped_column()
    definition: Mapped[str | None] = mapped_column(Text, default=None)
    concept_iri: Mapped[str | None] = mapped_column(Text, default=None)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"))

    project: Mapped[Project] = relationship(back_populates="terms")
    passages: Mapped[list[Passage]] = relationship(
        back_populates="term", cascade="all, delete-orphan"
    )


class Passage(UUIDAuditBase):
    __table_args__ = (
        # prevent the same term being annotated at the same place in one annotation snapshot
        UniqueConstraint("annotation_version_id", "term_id", "start", "end"),
        CheckConstraint("start >= 0", name="ck_passage_start_nonnegative"),
        CheckConstraint("end > start", name="ck_passage_end_after_start"),
    )

    content: Mapped[str] = mapped_column()
    # Offsets are UTF-16 code units (matching browser Range offsets); end is exclusive.
    start: Mapped[int] = mapped_column()
    end: Mapped[int] = mapped_column()
    annotation_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("annotation_version.id", ondelete="CASCADE")
    )
    term_id: Mapped[UUID] = mapped_column(ForeignKey("term.id"))

    term: Mapped[Term] = relationship(back_populates="passages")
    annotation_version: Mapped[AnnotationVersion] = relationship(back_populates="annotations")
