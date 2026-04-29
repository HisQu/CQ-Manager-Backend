from typing import Iterable, Sequence
from uuid import UUID

from domain.groups.models import Group
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption

from .dtos import (
    UnifiedQuestionAuthor,
    UnifiedQuestionEntryKind,
    UnifiedQuestionGroup,
    UnifiedQuestionOverview,
)
from .models import Question


class QuestionService:
    @staticmethod
    def _to_unified_question_entry(question: Question) -> UnifiedQuestionOverview:
        return UnifiedQuestionOverview(
            id=question.id,
            question=question.question,
            sparql_query=question.sparql_query,
            rating=question.aggregated_rating,
            no_consolidations=question.no_consolidations,
            group=UnifiedQuestionGroup(id=question.group.id, name=question.group.name),
            author=UnifiedQuestionAuthor(
                id=question.author.id,
                email=question.author.email,
                name=question.author.name,
            ),
            unified_entry_kind=UnifiedQuestionEntryKind.QUESTION,
        )

    @staticmethod
    def _to_unified_consolidation_entry(
        question: Question, consolidation_id: UUID
    ) -> UnifiedQuestionOverview:
        consolidation = next(
            (
                consolidation
                for consolidation in question.consolidations
                if consolidation.id == consolidation_id
            ),
            None,
        )
        if consolidation is None:
            return QuestionService._to_unified_question_entry(question)

        consolidated_question_ids = sorted(
            (
                consolidated_question.id
                for consolidated_question in consolidation.questions
            ),
            key=str,
        )

        return UnifiedQuestionOverview(
            id=consolidation.id,
            question=consolidation.name,
            sparql_query=None,
            rating=0,
            no_consolidations=0,
            group=UnifiedQuestionGroup(id=question.group.id, name=question.group.name),
            author=UnifiedQuestionAuthor(
                id=consolidation.engineer.id,
                email=consolidation.engineer.email,
                name=consolidation.engineer.name,
            ),
            unified_entry_kind=UnifiedQuestionEntryKind.CONSOLIDATION_RESULT,
            consolidation_id=consolidation.id,
            consolidated_question_ids=consolidated_question_ids,
        )

    @staticmethod
    async def get_questions_by_group(
        session: AsyncSession,
        group_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Question]:
        options = [] if not options else options
        statement = (
            select(Question).where(Question.group_id == group_id).options(*options)
        )
        return (await session.scalars(statement)).all()

    @staticmethod
    async def get_questions_by_project(
        session: AsyncSession,
        project_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Question]:
        options = [] if not options else options
        statement = (
            select(Question)
            .join(Group)
            .filter(Group.project_id == project_id)
            .options(*options)
        )
        return (await session.scalars(statement)).all()

    @staticmethod
    def _unify_consolidated_questions(
        questions: Sequence[Question],
    ) -> list[UnifiedQuestionOverview]:
        unified: list[UnifiedQuestionOverview] = []
        seen_consolidation_ids: set[UUID] = set()

        for question in questions:
            consolidation_ids = sorted(
                (
                    consolidation.id
                    for consolidation in question.consolidations
                ),
                key=str,
            )

            if not consolidation_ids:
                unified.append(QuestionService._to_unified_question_entry(question))
                continue

            unconsolidated_ids = [
                consolidation_id
                for consolidation_id in consolidation_ids
                if consolidation_id not in seen_consolidation_ids
            ]
            if not unconsolidated_ids:
                continue

            # One consolidation result entry is emitted per unseen consolidation.
            for consolidation_id in unconsolidated_ids:
                unified.append(
                    QuestionService._to_unified_consolidation_entry(
                        question, consolidation_id
                    )
                )
            seen_consolidation_ids.update(unconsolidated_ids)

        return unified

    @staticmethod
    async def get_unified_questions_by_group(
        session: AsyncSession,
        group_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[UnifiedQuestionOverview]:
        questions = await QuestionService.get_questions_by_group(
            session, group_id, options
        )
        return QuestionService._unify_consolidated_questions(questions)

    @staticmethod
    async def get_unified_questions_by_project(
        session: AsyncSession,
        project_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[UnifiedQuestionOverview]:
        questions = await QuestionService.get_questions_by_project(
            session, project_id, options
        )
        return QuestionService._unify_consolidated_questions(questions)
