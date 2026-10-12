from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey



if TYPE_CHECKING:
    from domain.questions.models import Question
    from domain.accounts.models import User


class Version(UUIDAuditBase):
    """Snapshot of the revised fields of a `Question` revision, written when the next revision replaces it."""

    question_string: Mapped[str]
    sparql_query: Mapped[str | None] = mapped_column(default=None)
    example_answer: Mapped[str | None] = mapped_column(Text, default=None)
    version_number: Mapped[int]
    editor_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))

    question_id: Mapped[UUID] = mapped_column(ForeignKey("question.id"))
    question: Mapped[Question] = relationship(back_populates="versions")
    editor: Mapped[User] = relationship(back_populates="edited_versions")
