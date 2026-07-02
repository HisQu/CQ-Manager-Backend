from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import Column, ForeignKey, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey, UniqueConstraint

if TYPE_CHECKING:
    from domain.projects.models import Project
    from domain.questions.models import Question


class Term(UUIDAuditBase):
    __table_args__ = (UniqueConstraint("content", "project_id"),)

    content: Mapped[str] = mapped_column()
    definition: Mapped[str | None] = mapped_column(Text, default=None)
    concept_iri: Mapped[str | None] = mapped_column(Text, default=None)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"))

    project: Mapped[Project] = relationship(back_populates="terms")
    passages: Mapped[list[Passage]] = relationship(back_populates="term")


AnnotatedPassages = Table(
    "annotated_passages",
    UUIDAuditBase.metadata,
    Column[UUID]("question_id", ForeignKey("question.id"), primary_key=True),
    Column[UUID]("passage_id", ForeignKey("passage.id"), primary_key=True),
)


class Passage(UUIDAuditBase):
    __table_args__ = (UniqueConstraint("content", "term_id"),)

    content: Mapped[str] = mapped_column()

    #author_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    term_id: Mapped[UUID] = mapped_column(ForeignKey("term.id"))

    term: Mapped[Term] = relationship(back_populates="passages")
    questions: Mapped[list[Question]] = relationship(secondary="annotated_passages", back_populates="annotations")
