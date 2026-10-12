from typing import Iterable, Sequence
from uuid import UUID

from domain.history.models import QuestionEventType
from domain.history.services import HistoryService
from domain.questions.models import INCLUDE_DELETED, Question
from domain.topics.services import TopicService
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from sqlalchemy import Select, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from .models import QuestionTags, Tag

TAG_NAME_MAX_LENGTH = 50


def normalize_tag_name(name: str) -> str:
    """Trims and collapses whitespace so `" open   issue "` and `"open issue"` are the same tag."""
    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("Tag name must not be empty.")
    if len(normalized) > TAG_NAME_MAX_LENGTH:
        raise ValueError(f"Tag name must not be longer than {TAG_NAME_MAX_LENGTH} characters.")
    return normalized


class TagService:
    @staticmethod
    def _with_question_counts(statement: Select[tuple[Tag]]) -> Select[tuple[Tag, int]]:
        return (
            statement.add_columns(func.count(Question.id))
            .outerjoin(QuestionTags, QuestionTags.c.tag_id == Tag.id)
            .outerjoin(Question, and_(Question.id == QuestionTags.c.question_id, Question.deleted_at.is_(None)))
            .group_by(Tag.id)
            .execution_options(**{INCLUDE_DELETED: True})
        )

    @staticmethod
    async def list_tags(session: AsyncSession, project_id: UUID) -> Sequence[tuple[Tag, int]]:
        """Lists all `Tag`s of a `Project` with their number of tagged `Question`s, ordered by name."""
        statement = TagService._with_question_counts(select(Tag).where(Tag.project_id == project_id))
        rows = (await session.execute(statement)).tuples().all()
        return sorted(rows, key=lambda row: row[0].name.casefold())

    @staticmethod
    async def get_tag_with_count(session: AsyncSession, project_id: UUID, tag_id: UUID) -> tuple[Tag, int]:
        statement = TagService._with_question_counts(
            select(Tag).where(Tag.id == tag_id, Tag.project_id == project_id)
        )
        row = (await session.execute(statement)).tuples().first()
        if not row:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Tag not found.")
        return row

    @staticmethod
    async def get_tag(session: AsyncSession, project_id: UUID, tag_id: UUID) -> Tag:
        tag = await session.scalar(select(Tag).where(Tag.id == tag_id, Tag.project_id == project_id))
        if not tag:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Tag not found.")
        return tag

    @staticmethod
    async def _ensure_unique_name(
        session: AsyncSession,
        project_id: UUID,
        name: str,
        exclude_tag_id: UUID | None = None,
    ) -> None:
        statement = select(Tag.id).where(Tag.project_id == project_id, func.lower(Tag.name) == name.lower())
        if exclude_tag_id is not None:
            statement = statement.where(Tag.id != exclude_tag_id)
        if await session.scalar(statement):
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="A tag with this name already exists.")

    @staticmethod
    async def create_tag(session: AsyncSession, project_id: UUID, name: str) -> Tag:
        await TagService._ensure_unique_name(session, project_id, name)
        tag = Tag(name=name, project_id=project_id)
        session.add(tag)
        await session.commit()
        await session.refresh(tag)
        return tag

    @staticmethod
    async def rename_tag(session: AsyncSession, project_id: UUID, tag_id: UUID, name: str) -> Tag:
        tag = await TagService.get_tag(session, project_id, tag_id)
        await TagService._ensure_unique_name(session, project_id, name, exclude_tag_id=tag_id)
        tag.name = name
        await session.commit()
        await session.refresh(tag)
        return tag

    @staticmethod
    async def delete_tag(session: AsyncSession, project_id: UUID, tag_id: UUID, actor_id: UUID) -> None:
        """Deletes a `Tag`, recording its removal in the history of every `Question` that had it."""
        tag = await TagService.get_tag(session, project_id, tag_id)
        questions = await session.scalars(
            select(Question)
            .join(QuestionTags, QuestionTags.c.question_id == Question.id)
            .where(QuestionTags.c.tag_id == tag_id)
            .execution_options(**{INCLUDE_DELETED: True})
        )
        for question in questions:
            HistoryService.record_tag_changes(session, question, [tag], [], actor_id)
        await session.execute(delete(QuestionTags).where(QuestionTags.c.tag_id == tag_id))
        await session.delete(tag)
        await session.commit()

    @staticmethod
    async def resolve_tags(session: AsyncSession, project_id: UUID, tag_ids: Iterable[UUID]) -> list[Tag]:
        """Loads the given `Tag`s and ensures that every one of them belongs to the `Project`."""
        unique_ids = set(tag_ids)
        if not unique_ids:
            return []

        tags = (
            await session.scalars(select(Tag).where(Tag.id.in_(unique_ids), Tag.project_id == project_id))
        ).all()
        if len(tags) != len(unique_ids):
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Unknown tag for this project.")
        return sorted(tags, key=lambda tag: tag.name.casefold())

    @staticmethod
    async def set_question_tags(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        tag_ids: Iterable[UUID],
        actor_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        """Replaces the `Tag`s of a `Question` with the given ones and records the changes in its history."""
        question = await TopicService.get_project_question(
            session, project_id, question_id, [selectinload(Question.tags)]
        )
        tags = await TagService.resolve_tags(session, project_id, tag_ids)
        HistoryService.record_tag_changes(session, question, question.tags, tags, actor_id)
        question.tags = tags
        await session.commit()
        return await TopicService.get_project_question(session, project_id, question_id, options)
