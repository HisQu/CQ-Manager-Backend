from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .dtos import CommentCreate
from .models import Comment, CommentReadMarker

if TYPE_CHECKING:
    from domain.questions.models import Question


@dataclass(frozen=True)
class CommentReader:
    """The read state of one `User`: own comments and comments up to `read_at` count as read."""

    user_id: UUID
    read_at: dict[UUID, datetime] = field(default_factory=dict)

    def unread_comments(self, question: "Question") -> list[Comment]:
        since = self.read_at.get(question.id)
        return [
            comment
            for comment in question.comments
            if comment.author_id != self.user_id and (since is None or comment.created_at > since)
        ]


class CommentsService:
    @staticmethod
    async def get_comments(session: AsyncSession, quesion_id: UUID) -> Sequence[Comment]:
        return (await session.scalars(select(Comment).where(Comment.question_id == quesion_id))).all()

    @staticmethod
    async def get_reader(session: AsyncSession, user_id: UUID) -> CommentReader:
        markers = await session.scalars(select(CommentReadMarker).where(CommentReadMarker.user_id == user_id))
        return CommentReader(user_id=user_id, read_at={marker.question_id: marker.read_at for marker in markers})

    @staticmethod
    async def mark_read(session: AsyncSession, user_id: UUID, question_id: UUID) -> None:
        """Marks every comment of the `Question` written until now as read by the `User`."""
        marker = await session.scalar(
            select(CommentReadMarker).where(
                CommentReadMarker.user_id == user_id, CommentReadMarker.question_id == question_id
            )
        )
        now = datetime.now(timezone.utc)
        if marker:
            marker.read_at = now
        else:
            session.add(CommentReadMarker(user_id=user_id, question_id=question_id, read_at=now))

    @staticmethod
    async def create_comment(session: AsyncSession, author_id: UUID, data: CommentCreate) -> Comment:
        comment = Comment(author_id=author_id, question_id=data.question_id, comment=data.comment)
        session.add(comment)
        await CommentsService.mark_read(session, author_id, data.question_id)
        await session.commit()
        await session.refresh(comment)
        return await session.scalar(
            select(Comment).where(Comment.id == comment.id).options(selectinload(Comment.author))
        )
