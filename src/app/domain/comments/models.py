from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types import DateTimeUTC
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from ..accounts.models import User
    from ..ratings.models import Question


class Comment(UUIDAuditBase):
    comment: Mapped[str]
    question_id: Mapped[UUID] = mapped_column(ForeignKey("question.id"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))

    author: Mapped[User] = relationship(back_populates="comments")
    question: Mapped[Question] = relationship(back_populates="comments")


class CommentReadMarker(UUIDAuditBase):
    """Remembers until when a `User` has read the comments of a `Question`."""

    __table_args__ = (UniqueConstraint("user_id", "question_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    question_id: Mapped[UUID] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"))
    read_at: Mapped[datetime] = mapped_column(DateTimeUTC(timezone=True))
