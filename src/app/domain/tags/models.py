from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import Column, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from domain.projects.models import Project
    from domain.questions.models import Question

QuestionTags = Table(
    "question_tags",
    UUIDAuditBase.metadata,
    Column[UUID]("question_id", ForeignKey("question.id", ondelete="CASCADE"), primary_key=True),
    Column[UUID]("tag_id", ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(UUIDAuditBase):
    __table_args__ = (UniqueConstraint("name", "project_id"),)

    name: Mapped[str] = mapped_column()
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))

    project: Mapped[Project] = relationship(back_populates="tags")
    questions: Mapped[list[Question]] = relationship(secondary="question_tags", back_populates="tags")
