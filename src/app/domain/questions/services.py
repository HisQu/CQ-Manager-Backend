from typing import Iterable, Sequence
from uuid import UUID

from domain.groups.models import Group
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption

from .models import Question


class QuestionService:
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
    def _unify_consolidated_questions(questions: Sequence[Question]) -> list[Question]:
        unified: list[Question] = []
        seen_consolidation_ids: set[UUID] = set()

        for question in questions:
            consolidation_ids = {
                consolidation.id for consolidation in question.consolidations
            }

            if not consolidation_ids:
                unified.append(question)
                continue

            if consolidation_ids.intersection(seen_consolidation_ids):
                continue

            unified.append(question)
            seen_consolidation_ids.update(consolidation_ids)

        return unified

    @staticmethod
    async def get_unified_questions_by_group(
        session: AsyncSession,
        group_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Question]:
        questions = await QuestionService.get_questions_by_group(
            session, group_id, options
        )
        return QuestionService._unify_consolidated_questions(questions)

    @staticmethod
    async def get_unified_questions_by_project(
        session: AsyncSession,
        project_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Question]:
        questions = await QuestionService.get_questions_by_project(
            session, project_id, options
        )
        return QuestionService._unify_consolidated_questions(questions)
