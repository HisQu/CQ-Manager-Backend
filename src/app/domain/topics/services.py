import re
from typing import Iterable, Sequence
from uuid import UUID

from domain.groups.models import Group
from domain.questions.models import Question
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from .models import Topic

TOPIC_IDENTIFIER_PATTERN = re.compile(r"^[A-Z]+$")


def normalize_topic_identifier(identifier: str | None) -> str | None:
    if identifier is None:
        return None

    normalized = identifier.strip().upper()
    if not TOPIC_IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError("Topic identifier must contain alphabetical characters only.")
    return normalized


def topic_identifier_to_number(identifier: str) -> int:
    number = 0
    for character in identifier:
        number = number * 26 + (ord(character) - ord("A") + 1)
    return number


def number_to_topic_identifier(number: int) -> str:
    if number < 1:
        raise ValueError("Topic identifier number must be positive.")

    identifier = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        identifier = chr(ord("A") + remainder) + identifier
    return identifier


def next_topic_identifier(identifiers: Iterable[str]) -> str:
    used_numbers = {
        topic_identifier_to_number(identifier)
        for identifier in identifiers
        if TOPIC_IDENTIFIER_PATTERN.fullmatch(identifier)
    }
    candidate = 1
    while candidate in used_numbers:
        candidate += 1
    return number_to_topic_identifier(candidate)


def topic_identifier_sort_key(topic: Topic) -> int:
    return topic_identifier_to_number(topic.identifier)


class TopicService:
    @staticmethod
    async def list_topics(
        session: AsyncSession,
        project_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Topic]:
        statement = select(Topic).where(Topic.project_id == project_id)
        if options:
            statement = statement.options(*options)
        topics = (await session.scalars(statement)).all()
        return sorted(topics, key=topic_identifier_sort_key)

    @staticmethod
    async def get_topic(
        session: AsyncSession,
        project_id: UUID,
        topic_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Topic:
        statement = select(Topic).where(Topic.id == topic_id, Topic.project_id == project_id)
        if options:
            statement = statement.options(*options)

        topic = await session.scalar(statement)
        if not topic:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Topic not found.")
        return topic

    @staticmethod
    async def create_topic(session: AsyncSession, project_id: UUID, name: str, identifier: str | None) -> Topic:
        existing_identifiers = (
            await session.scalars(select(Topic.identifier).where(Topic.project_id == project_id))
        ).all()

        topic_identifier = identifier or next_topic_identifier(existing_identifiers)
        if topic_identifier in existing_identifiers:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Topic identifier is already in use.",
            )

        topic = Topic(name=name, identifier=topic_identifier, project_id=project_id)
        session.add(topic)
        await session.commit()
        await session.refresh(topic)
        return topic

    @staticmethod
    async def update_topic(session: AsyncSession, project_id: UUID, topic_id: UUID, name: str) -> Topic:
        topic = await TopicService.get_topic(session, project_id, topic_id)
        topic.name = name
        await session.commit()
        await session.refresh(topic)
        return topic

    @staticmethod
    async def get_project_question(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        statement = select(Question).join(Group).where(Question.id == question_id, Group.project_id == project_id)
        if options:
            statement = statement.options(*options)

        question = await session.scalar(statement)
        if not question:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Question not found.")
        return question

    @staticmethod
    async def assign_question(
        session: AsyncSession,
        project_id: UUID,
        topic_id: UUID,
        question_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        await TopicService.get_topic(session, project_id, topic_id)
        question = await TopicService.get_project_question(
            session,
            project_id,
            question_id,
            [selectinload(Question.topic)],
        )

        if question.topic_id is not None:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Question already has a topic. Use the change endpoint instead.",
            )

        question.topic_id = topic_id
        await session.commit()
        await session.refresh(question)
        return await TopicService.get_project_question(session, project_id, question.id, options)

    @staticmethod
    async def change_question_topic(
        session: AsyncSession,
        project_id: UUID,
        topic_id: UUID,
        question_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        await TopicService.get_topic(session, project_id, topic_id)
        question = await TopicService.get_project_question(session, project_id, question_id)
        question.topic_id = topic_id
        await session.commit()
        await session.refresh(question)
        return await TopicService.get_project_question(session, project_id, question.id, options)

    @staticmethod
    async def remove_question_topic(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        question = await TopicService.get_project_question(session, project_id, question_id)
        question.topic_id = None
        await session.commit()
        await session.refresh(question)
        return await TopicService.get_project_question(session, project_id, question.id, options)
