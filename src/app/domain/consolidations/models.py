from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

if TYPE_CHECKING:
    from domain.accounts.models import User
    from domain.projects.models import Project
    from domain.questions.models import Question


ConsolidatedQuestions = Table(
    "consolidated_questions",
    UUIDAuditBase.metadata,
    Column[UUID]("consolidation_id", ForeignKey("consolidation.id"), primary_key=True),
    Column[UUID]("question_id", ForeignKey("question.id"), primary_key=True),
)


class Consolidation(UUIDAuditBase):
    engineer_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"))
    result_question_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question.id"), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="consolidations")
    engineer: Mapped[User] = relationship(back_populates="consolidations")
    questions: Mapped[list[Question]] = relationship(
        secondary="consolidated_questions",
        back_populates="consolidations",
        foreign_keys=[
            ConsolidatedQuestions.c.consolidation_id,
            ConsolidatedQuestions.c.question_id,
        ],
    )
    result_question: Mapped[Question | None] = relationship(
        foreign_keys=[result_question_id]
    )

    @hybrid_property
    def no_questions(self) -> int:
        return len(self.questions)
