from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence
from uuid import UUID

from domain.questions.models import INCLUDE_DELETED, Question, format_cq_catalogue_identifier
from domain.tags.models import Tag
from domain.topics.models import Topic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import QuestionEvent, QuestionEventType

# Tags and catalogue placements that predate the history get this timestamp, as their real one is unknown.
IMPORTED_AT = datetime(2026, 9, 5, 10, tzinfo=timezone(timedelta(hours=2)))


class HistoryService:
    @staticmethod
    def record(
        session: AsyncSession,
        question: Question,
        event_type: QuestionEventType,
        actor_id: UUID | None,
        **details: object,
    ) -> None:
        """Adds an event for the current revision of the `Question`, committed together with the change itself."""
        session.add(
            QuestionEvent(
                question_id=question.id,
                actor_id=actor_id,
                event_type=event_type.value,
                version_number=question.version_number,
                **details,
            )
        )

    @staticmethod
    def record_tag_changes(
        session: AsyncSession,
        question: Question,
        old_tags: Iterable[Tag],
        new_tags: Iterable[Tag],
        actor_id: UUID | None,
    ) -> None:
        old_by_id = {tag.id: tag for tag in old_tags}
        new_by_id = {tag.id: tag for tag in new_tags}
        for event_type, tags, other in (
            (QuestionEventType.TAG_REMOVED, old_by_id, new_by_id),
            (QuestionEventType.TAG_ADDED, new_by_id, old_by_id),
        ):
            for tag_id, tag in tags.items():
                if tag_id not in other:
                    HistoryService.record(session, question, event_type, actor_id, tag_id=tag.id, tag_name=tag.name)

    @staticmethod
    def record_catalogue_assignment(
        session: AsyncSession,
        question: Question,
        topic: Topic,
        actor_id: UUID | None,
    ) -> None:
        HistoryService.record(
            session,
            question,
            QuestionEventType.CATALOGUE_ASSIGNED,
            actor_id,
            topic_id=topic.id,
            catalogue_identifier=format_cq_catalogue_identifier(topic.identifier, question.catalogue_index),
        )

    @staticmethod
    async def list_events(session: AsyncSession, question_id: UUID) -> Sequence[QuestionEvent]:
        statement = (
            select(QuestionEvent)
            .where(QuestionEvent.question_id == question_id)
            .order_by(QuestionEvent.created_at)
            .options(selectinload(QuestionEvent.actor))
        )
        return (await session.scalars(statement)).all()

    @staticmethod
    async def import_existing_questions(session: AsyncSession) -> None:
        """Reconstructs the history of `Question`s created before it was recorded.

        Creation and revisions keep their real timestamps and editors. The current tags and catalogue placement
        are imported at `IMPORTED_AT` (or right after the latest known event) without an actor.
        """
        questions = (
            await session.scalars(
                select(Question)
                .where(Question.id.not_in(select(QuestionEvent.question_id)))
                .options(
                    selectinload(Question.versions),
                    selectinload(Question.tags),
                    selectinload(Question.topic),
                )
                .execution_options(**{INCLUDE_DELETED: True})
            )
        ).all()

        for question in questions:
            versions = sorted(question.versions, key=lambda version: version.version_number)
            session.add(
                QuestionEvent(
                    question_id=question.id,
                    actor_id=question.author_id,
                    event_type=QuestionEventType.CREATED.value,
                    version_number=versions[0].version_number if versions else question.version_number,
                    created_at=question.created_at,
                )
            )
            # A `Version` is the snapshot of a revision, written when the next revision replaced it.
            for version, next_version in zip(versions, [*versions[1:], None]):
                session.add(
                    QuestionEvent(
                        question_id=question.id,
                        actor_id=next_version.editor_id if next_version else question.editor_id,
                        event_type=QuestionEventType.REVISED.value,
                        version_number=version.version_number + 1,
                        created_at=version.created_at,
                    )
                )

            imported_at = max([IMPORTED_AT, question.created_at, *(version.created_at for version in versions)])
            imported: list[tuple[QuestionEventType, dict[str, object]]] = [
                (QuestionEventType.TAG_ADDED, {"tag_id": tag.id, "tag_name": tag.name}) for tag in question.tags
            ]
            if question.topic is not None and question.catalogue_index is not None:
                imported.append(
                    (
                        QuestionEventType.CATALOGUE_ASSIGNED,
                        {
                            "topic_id": question.topic.id,
                            "catalogue_identifier": question.cq_catalogue_identifier,
                        },
                    )
                )
            for event_type, details in imported:
                HistoryService.record(session, question, event_type, None, created_at=imported_at, **details)

        await session.commit()
