from itertools import chain
from typing import Iterable, Sequence
from uuid import UUID

from domain.groups.models import Group
from domain.questions.models import Question
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption

from .dtos import ConsolidationCreate, ConsolidationUpdate, MoveQuestion
from .models import Consolidation


class ConsolidationService:
    @staticmethod
    async def _get_project_question(
        session: AsyncSession, project_id: UUID, question_id: UUID
    ) -> Question:
        statement = (
            select(Question)
            .join(Group)
            .where(Question.id == question_id, Group.project_id == project_id)
        )
        if question := await session.scalar(statement):
            return question
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Result question is invalid for this project.",
        )

    @staticmethod
    async def _create_result_question(
        session: AsyncSession,
        project_id: UUID,
        user_id: UUID,
        group_id: UUID,
        question: str,
        sparql_query: str | None,
    ) -> Question:
        group = await session.scalar(
            select(Group).where(Group.id == group_id, Group.project_id == project_id)
        )
        if group is None:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Result question group is invalid for this project.",
            )

        result_question = Question(
            question=question,
            sparql_query=sparql_query,
            author_id=user_id,
            editor_id=user_id,
            group_id=group.id,
            version_number=1,
        )
        session.add(result_question)
        await session.flush()
        return result_question

    @staticmethod
    async def get_consolidation(
        session: AsyncSession,
        id: UUID,
        project_id: UUID | None = None,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Consolidation:
        """Gets a single `Consolidation`.

        :param session: An active database session.
        :param id: Id of the `Consolidation`.
        :param project_id: Id of the `Consolidation`s `Project`..
        :param options: Additional loading options, defaults to None.
        :raises HTTPException: If no `Consolidation` was found.
        :return: A `Consolidation`.
        """
        if project_id:
            statement = select(Consolidation).where(Consolidation.id == id, Consolidation.project_id == project_id)
        else:
            statement = select(Consolidation).where(Consolidation.id == id)

        if options:
            statement = statement.options(*options)

        if consolidation := await session.scalar(statement):
            return consolidation
        raise HTTPException(status_code=HTTP_404_NOT_FOUND)

    @staticmethod
    async def get_consolidations(
        session: AsyncSession,
        project_id: UUID | None = None,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Consolidation]:
        """Gets a all `Consolidations`.

        :param session: An active database session.
        :param options: Additional loading options, defaults to None.
        :return: A sequence of all `Consolidations`.
        """
        if project_id:
            statement = select(Consolidation).where(Consolidation.project_id == project_id)
        else:
            statement = select(Consolidation)

        if options:
            statement = statement.options(*options)
        return (await session.scalars(statement)).all()

    @staticmethod
    async def create_consolidation(
        session: AsyncSession,
        user_id: UUID,
        project_id: UUID,
        data: ConsolidationCreate,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Consolidation:
        """Creates a new `Consolidation`.

        :param session: An active database session.
        :param user_id: The authors id.
        :param project_id: The `Project`s id this `Consolidation` belongs to.
        :param data: Contents of the `Consolidation`.
        :param options: Additional loading options, defaults to None.
        :raises HTTPException: If database integrity was violated.
        :return: The created `Consolidation`.
        """
        questions: Sequence[Question] = []
        if data.ids:
            questions_ = await session.scalars(select(Question).where(Question.id.in_(data.ids)))
            questions = questions_.all()

        try:
            if data.result_question_id is not None:
                result_question = await ConsolidationService._get_project_question(
                    session=session,
                    project_id=project_id,
                    question_id=data.result_question_id,
                )
            elif data.result_question is not None:
                result_question = await ConsolidationService._create_result_question(
                    session=session,
                    project_id=project_id,
                    user_id=user_id,
                    group_id=data.result_question.group_id,
                    question=data.result_question.question,
                    sparql_query=data.result_question.sparql_query,
                )
            else:
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Provide exactly one of resultQuestion or resultQuestionId.",
                )
            consolidation = Consolidation(
                questions=questions,
                result_question=result_question,
                engineer_id=user_id,
                project_id=project_id,
            )
            session.add(consolidation)
            await session.commit()
        except IntegrityError as error:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST) from error

        await session.refresh(consolidation)
        return await ConsolidationService.get_consolidation(session, consolidation.id, options=options)

    @staticmethod
    async def delete_consolidation(session: AsyncSession, id: UUID, project_id: UUID) -> bool:
        """Deletes an existing `Consolidation`.

        :param session: An active database session.
        :param id: Id of the `Consolidation`.
        :param project_id: The `Project`s id this `Consolidation` belongs to.
        :return: `True` if successfully deleted.
        """
        consolidation = await ConsolidationService.get_consolidation(session, id, project_id)
        await session.delete(consolidation)
        return True

    @staticmethod
    async def update_consolidation(
        session: AsyncSession,
        id: UUID,
        project_id: UUID,
        data: ConsolidationUpdate,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Consolidation:
        """Updates an existing `Consolidation`.

        :param session: An active database session.
        :param id: Id of the `Consolidation`.
        :param project_id: The `Project`s id this `Consolidation` belongs to.
        :param data: Contents of the `Consolidation`.
        :param options: Additional loading options, defaults to None.
        :raises HTTPException: If database integrity was violated.
        :raises HTTPException: If no `Consolidation` was found.
        :return: The updated `Consolidation`.
        """
        consolidation = await ConsolidationService.get_consolidation(
            session, id, project_id, options=options
        )
        if data.result_question_id is not None:
            consolidation.result_question = await ConsolidationService._get_project_question(
                session, project_id, data.result_question_id
            )

        try:
            await session.commit()
        except IntegrityError as error:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST) from error
        return consolidation

    @staticmethod
    async def add_questions(
        session: AsyncSession,
        id: UUID,
        project_id: UUID,
        data: MoveQuestion,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Consolidation:
        """Add `Questions` to an existing `Consolidation`.

        :param session: An active database session.
        :param id: Id of the `Consolidation`.
        :param project_id: The `Project`s id this `Consolidation` belongs to.
        :param data: A list of `Question` ids.
        :param options: Additional loading options, defaults to None.
        :raises HTTPException: If no `Consolidation` was found.
        :return: The updated `Consolidation`.
        """
        if not data.ids:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="No Ids were given.")

        consolidation = await ConsolidationService.get_consolidation(session, id, project_id, options=options)
        questions = await session.scalars(select(Question).where(Question.id.in_(data.ids)))

        consolidation.questions = [*set(chain(consolidation.questions, questions))]
        await session.commit()
        return await ConsolidationService.get_consolidation(session, id, project_id, options=options)

    @staticmethod
    async def remove_questions(
        session: AsyncSession,
        id: UUID,
        project_id: UUID,
        data: MoveQuestion,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Consolidation:
        """Removes `Questions` from an existing `Consolidation`.

        :param session: An active database session.
        :param id: Id of the `Consolidation`.
        :param project_id: The `Project`s id this `Consolidation` belongs to.
        :param data: A list of `Question` ids.
        :param options: Additional loading options, defaults to None.
        :raises HTTPException: If no `Consolidation` was found.
        :return: The updated `Consolidation`.
        """
        if not data.ids:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="No Ids were given.")

        consolidation = await ConsolidationService.get_consolidation(session, id, project_id, options=options)
        questions = await session.scalars(select(Question).where(Question.id.in_(data.ids)))
        for question in questions:
            if question in consolidation.questions:
                consolidation.questions.remove(question)
        await session.commit()
        return await ConsolidationService.get_consolidation(session, id, project_id, options=options)
