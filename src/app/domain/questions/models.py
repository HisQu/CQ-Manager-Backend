from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from advanced_alchemy.types import DateTimeUTC
from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, Text, UniqueConstraint, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, ORMExecuteState, Session, mapped_column, relationship, with_loader_criteria

if TYPE_CHECKING:
    from domain.accounts.models import User
    from domain.comments.models import Comment
    from domain.consolidations.models import Consolidation
    from domain.groups.models import Group
    from domain.ratings.models import Rating
    from domain.tags.models import Tag
    from domain.topics.models import Topic
    from domain.versions.models import Version
    from domain.terms.models import Passage

# Execution option that makes a `select` also return soft deleted `Question`s.
INCLUDE_DELETED = "include_deleted"


def format_cq_catalogue_identifier(topic_identifier: str, catalogue_index: int | None) -> str:
    return f"{topic_identifier}.{catalogue_index}"


class QuestionCatalogueReservation(UUIDAuditBase):
    __table_args__ = (UniqueConstraint("topic_id", "catalogue_index"),)

    topic_id: Mapped[UUID] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    catalogue_index: Mapped[int] = mapped_column()
    question_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question.id", ondelete="SET NULL"),
        default=None,
        unique=True,
    )


class Question(UUIDAuditBase):
    __table_args__ = (UniqueConstraint("topic_id", "catalogue_index"),)

    version_number: Mapped[int]
    question: Mapped[str]
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    reference: Mapped[str | None] = mapped_column(Text, default=None)
    anchor: Mapped[str | None] = mapped_column(Text, default=None)
    example_answer: Mapped[str | None] = mapped_column(Text, default=None)
    type: Mapped[str | None] = mapped_column(default=None)
    sparql_query: Mapped[str | None]
    catalogue_index: Mapped[int | None] = mapped_column(default=None)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    editor_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    group_id: Mapped[UUID] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"))
    topic_id: Mapped[UUID | None] = mapped_column(ForeignKey("topic.id"), default=None)
    # Deleted questions are kept for provenance and hidden from every query, see `_hide_deleted_questions`.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTimeUTC(timezone=True), default=None)

    author: Mapped[User] = relationship(foreign_keys=[author_id], back_populates="questions")
    editor: Mapped[User] = relationship(foreign_keys=[editor_id], back_populates="edited_questions")
    group: Mapped[Group] = relationship(back_populates="questions")
    topic: Mapped[Topic | None] = relationship(back_populates="questions")
    ratings: Mapped[list[Rating]] = relationship(back_populates="question", cascade="all, delete-orphan")
    comments: Mapped[list[Comment]] = relationship(back_populates="question", cascade="all, delete-orphan")
    consolidations: Mapped[list[Consolidation]] = relationship(
        secondary="consolidated_questions", back_populates="questions"
    )
    target_consolidations: Mapped[list[Consolidation]] = relationship(
        "Consolidation",
        primaryjoin="Question.id == Consolidation.result_question_id",
        foreign_keys="Consolidation.result_question_id",
        viewonly=True,
    )
    versions: Mapped[list[Version]] = relationship(back_populates="question", cascade="all, delete-orphan")
    annotations: Mapped[list[Passage]] = relationship(secondary="annotated_passages", back_populates="questions")
    tags: Mapped[list[Tag]] = relationship(secondary="question_tags", back_populates="questions", order_by="Tag.name")

    @hybrid_property
    def no_consolidations(self) -> int:
        return len(self.consolidations)

    @hybrid_property
    def no_comments(self) -> int:
        return len(self.comments)

    @hybrid_property
    def last_comment_at(self) -> datetime | None:
        return max((c.created_at for c in self.comments), default=None)

    @hybrid_property
    def aggregated_rating(self) -> int:
        return sum(map(lambda r: r.rating, self.ratings)) // len(self.ratings) if len(self.ratings) > 0 else 0

    @hybrid_property
    def cq_catalogue_identifier(self) -> str | None:
        if self.topic is None or self.catalogue_index is None:
            return None
        return format_cq_catalogue_identifier(self.topic.identifier, self.catalogue_index)


@event.listens_for(Session, "do_orm_execute")
def _hide_deleted_questions(state: ORMExecuteState) -> None:
    """Filters soft deleted `Question`s out of every ORM `select`, including relationship loads."""
    if (
        state.is_select
        and not state.is_column_load
        and not state.is_relationship_load
        and not state.execution_options.get(INCLUDE_DELETED, False)
    ):
        state.statement = state.statement.options(
            with_loader_criteria(Question, Question.deleted_at.is_(None), include_aliases=True)
        )
