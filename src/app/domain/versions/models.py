from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey



if TYPE_CHECKING:
    from domain.questions.models import Question
    from domain.accounts.models import User
    from domain.terms.models import Passage


class Version(UUIDAuditBase):
    """A stable revision of a Question, including the current revision."""

    __table_args__ = (UniqueConstraint("question_id", "version_number"),)

    question_string: Mapped[str]
    sparql_query: Mapped[str | None] = mapped_column(default=None)
    example_answer: Mapped[str | None] = mapped_column(Text, default=None)
    version_number: Mapped[int]
    editor_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))

    question_id: Mapped[UUID] = mapped_column(ForeignKey("question.id"))
    question: Mapped[Question] = relationship(back_populates="versions")
    editor: Mapped[User] = relationship(back_populates="edited_versions")
    annotation_versions: Mapped[list[AnnotationVersion]] = relationship(
        back_populates="question_version", cascade="all, delete-orphan", order_by="AnnotationVersion.version_number"
    )


class AnnotationVersion(UUIDAuditBase):
    """An immutable snapshot of all annotations for one question revision."""

    __table_args__ = (UniqueConstraint("question_version_id", "version_number"),)

    version_number: Mapped[int]
    question_version_id: Mapped[UUID] = mapped_column(ForeignKey("version.id", ondelete="CASCADE"))
    editor_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    retained_from_annotation_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("annotation_version.id", ondelete="SET NULL"), default=None
    )

    question_version: Mapped[Version] = relationship(back_populates="annotation_versions")
    editor: Mapped[User] = relationship()
    annotations: Mapped[list[Passage]] = relationship(
        back_populates="annotation_version", cascade="all, delete-orphan", order_by="Passage.start"
    )
