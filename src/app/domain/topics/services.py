import re
from typing import Iterable, Sequence
from uuid import UUID

from domain.groups.models import Group
from domain.history.services import HistoryService
from domain.projects.models import Project
from domain.questions.models import Question, QuestionCatalogueReservation
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from .models import Topic

TOPIC_IDENTIFIER_PATTERN = re.compile(r"^[A-Z]+$")

# Every project has one catch-all catalogue for CQs that are not (yet) part of a real catalogue.
UNCATALOGUED_IDENTIFIER = "#"
UNCATALOGUED_NAME = "Uncatalogued"


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


def next_catalogue_index(indices: Iterable[int | None]) -> int:
    used_indices = {index for index in indices if index is not None and index > 0}
    return max(used_indices, default=0) + 1


def is_uncatalogued(topic: Topic | None) -> bool:
    return topic is not None and topic.identifier == UNCATALOGUED_IDENTIFIER


def topic_identifier_sort_key(topic: Topic) -> tuple[bool, int]:
    """Orders catalogues by identifier with the uncatalogued catch-all last."""
    if is_uncatalogued(topic):
        return True, 0
    return False, topic_identifier_to_number(topic.identifier)


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
    async def get_uncatalogued_topic(session: AsyncSession, project_id: UUID) -> Topic:
        """Gets the uncatalogued catch-all of a `Project`, creating it if it does not exist yet."""
        topic = await session.scalar(
            select(Topic).where(Topic.project_id == project_id, Topic.identifier == UNCATALOGUED_IDENTIFIER)
        )
        if topic is None:
            topic = Topic(name=UNCATALOGUED_NAME, identifier=UNCATALOGUED_IDENTIFIER, project_id=project_id)
            session.add(topic)
            await session.flush()
        return topic

    @staticmethod
    async def assign_uncatalogued(
        session: AsyncSession,
        project_id: UUID,
        question: Question,
        actor_id: UUID | None,
    ) -> None:
        """Puts a `Question` into the uncatalogued catch-all. Needs a flushed question."""
        topic = await TopicService.get_uncatalogued_topic(session, project_id)
        await TopicService._place_question(session, question, topic, actor_id)

    @staticmethod
    async def _place_question(session: AsyncSession, question: Question, topic: Topic, actor_id: UUID | None) -> None:
        """Gives a `Question` the next free identifier of a catalogue and records it in the question's history."""
        await TopicService.unassign_catalogue_identifier(session, question)
        question.topic_id = topic.id
        question.catalogue_index = await TopicService.reserve_catalogue_identifier(session, topic.id, question.id)
        HistoryService.record_catalogue_assignment(session, question, topic, actor_id)

    @staticmethod
    async def assign_all_uncatalogued(session: AsyncSession) -> None:
        """Moves every `Question` without a catalogue into its project's uncatalogued catch-all.

        Runs on start up so that projects and CQs created before the catch-all existed get one, too.
        """
        project_ids = (await session.scalars(select(Project.id))).all()
        for project_id in project_ids:
            topic = await TopicService.get_uncatalogued_topic(session, project_id)
            questions = (
                await session.scalars(
                    select(Question)
                    .join(Group)
                    .where(Group.project_id == project_id, Question.topic_id.is_(None))
                    .order_by(Question.created_at)
                )
            ).all()
            if not questions:
                continue

            catalogue_index = await TopicService.get_next_catalogue_index(session, topic.id)
            for question in questions:
                question.topic_id = topic.id
                question.catalogue_index = catalogue_index
                session.add(
                    QuestionCatalogueReservation(
                        topic_id=topic.id,
                        catalogue_index=catalogue_index,
                        question_id=question.id,
                    )
                )
                HistoryService.record_catalogue_assignment(session, question, topic, None)
                catalogue_index += 1
        await session.commit()

    @staticmethod
    async def update_topic(session: AsyncSession, project_id: UUID, topic_id: UUID, name: str) -> Topic:
        topic = await TopicService.get_topic(session, project_id, topic_id)
        if is_uncatalogued(topic):
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"The {UNCATALOGUED_NAME} catalogue cannot be renamed.",
            )
        topic.name = name
        await session.commit()
        await session.refresh(topic)
        return topic

    @staticmethod
    async def get_next_catalogue_index(session: AsyncSession, topic_id: UUID) -> int:
        existing_indices = (
            await session.scalars(
                select(QuestionCatalogueReservation.catalogue_index).where(
                    QuestionCatalogueReservation.topic_id == topic_id
                )
            )
        ).all()
        return next_catalogue_index(existing_indices)

    @staticmethod
    async def reserve_catalogue_identifier(
        session: AsyncSession,
        topic_id: UUID,
        question_id: UUID,
    ) -> int:
        catalogue_index = await TopicService.get_next_catalogue_index(session, topic_id)
        session.add(
            QuestionCatalogueReservation(
                topic_id=topic_id,
                catalogue_index=catalogue_index,
                question_id=question_id,
            )
        )
        await session.flush()
        return catalogue_index

    @staticmethod
    async def unassign_catalogue_identifier(
        session: AsyncSession,
        question: Question,
    ) -> None:
        if question.topic_id is None or question.catalogue_index is None:
            return

        reservation = await session.scalar(
            select(QuestionCatalogueReservation).where(
                QuestionCatalogueReservation.topic_id == question.topic_id,
                QuestionCatalogueReservation.catalogue_index == question.catalogue_index,
                QuestionCatalogueReservation.question_id == question.id,
            )
        )
        if reservation:
            reservation.question_id = None

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
        actor_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        topic = await TopicService.get_topic(session, project_id, topic_id)
        question = await TopicService.get_project_question(
            session,
            project_id,
            question_id,
            [selectinload(Question.topic)],
        )

        if question.topic_id is not None and not is_uncatalogued(question.topic):
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Question already has a topic. Use the change endpoint instead.",
            )

        if question.topic_id != topic_id:
            await TopicService._place_question(session, question, topic, actor_id)
        await session.commit()
        await session.refresh(question)
        return await TopicService.get_project_question(session, project_id, question.id, options)

    @staticmethod
    async def change_question_topic(
        session: AsyncSession,
        project_id: UUID,
        topic_id: UUID,
        question_id: UUID,
        actor_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        topic = await TopicService.get_topic(session, project_id, topic_id)
        question = await TopicService.get_project_question(session, project_id, question_id)
        if question.topic_id != topic_id or question.catalogue_index is None:
            await TopicService._place_question(session, question, topic, actor_id)
        await session.commit()
        await session.refresh(question)
        return await TopicService.get_project_question(session, project_id, question.id, options)

    @staticmethod
    async def remove_question_topic(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        actor_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        question = await TopicService.get_project_question(
            session,
            project_id,
            question_id,
            [selectinload(Question.topic)],
        )
        if not is_uncatalogued(question.topic):
            await TopicService.assign_uncatalogued(session, project_id, question, actor_id)
        await session.commit()
        await session.refresh(question)
        return await TopicService.get_project_question(session, project_id, question.id, options)
