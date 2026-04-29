from typing import Annotated, Any, Sequence, TypeVar
from uuid import UUID

from domain.accounts.models import User
from domain.comments.models import Comment
from domain.consolidations.models import Consolidation
from domain.groups.middleware import UserGroupPermissionsMiddleware
from domain.groups.models import Group
from domain.projects.middleware import UserProjectPermissionsMiddleware
from domain.questions.services import QuestionService
from domain.ratings.models import Rating
from domain.versions.models import Version
from litestar import Controller, Request, delete, get, post, put
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.params import Body
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .dtos import (
    QuestionCreate,
    QuestionCreateDTO,
    QuestionDetailDTO,
    QuestionOverviewDTO,
    UnifiedQuestionOverview,
    UnifiedQuestionOverviewDTO,
)
from .models import Question
from domain.terms.services import AnnotationService
from domain.terms.models import Passage


T = TypeVar("T")
JsonEncoded = Annotated[T, Body(media_type=RequestEncodingType.JSON)]


class QuestionController(Controller):
    path = "/questions/"
    tags = ["Questions"]
    middleware = [UserGroupPermissionsMiddleware, UserProjectPermissionsMiddleware]

    default_options = [
        selectinload(Question.author),
        selectinload(Question.ratings),
        selectinload(Question.consolidations),
        selectinload(Question.group).options(selectinload(Group.project)),
    ]
    unified_options = [
        selectinload(Question.author),
        selectinload(Question.ratings),
        selectinload(Question.consolidations).options(
            selectinload(Consolidation.engineer),
            selectinload(Consolidation.questions),
            selectinload(Consolidation.result_question).options(
                selectinload(Question.author),
                selectinload(Question.ratings),
                selectinload(Question.consolidations),
                selectinload(Question.group),
            ),
        ),
        selectinload(Question.group).options(selectinload(Group.project)),
    ]
    detail_options = [
        selectinload(Question.author),
        selectinload(Question.editor),
        selectinload(Question.ratings).options(selectinload(Rating.author)),
        selectinload(Question.consolidations).options(
            selectinload(Consolidation.questions).options(
                selectinload(Question.author)
            ),
            selectinload(Consolidation.engineer),
        ),
        selectinload(Question.group).options(selectinload(Group.project)),
        selectinload(Question.versions),
        selectinload(Question.annotations).options(selectinload(Passage.term)),
        selectinload(Question.comments).options(selectinload(Comment.author)),
    ]

    @post(
        "/{group_id:uuid}",
        dto=QuestionCreateDTO,
        return_dto=QuestionDetailDTO,
        status_code=HTTP_201_CREATED,
    )
    async def create_question(
        self,
        session: AsyncSession,
        data: JsonEncoded[QuestionCreate],
        request: Request[User, Any, Any],
        group_id: UUID,
    ) -> Question:
        """
        Creates a new `Question`

        :param group_id:
        :param request: Request[User, Any, Any]
        :param session: The session object to use for database operations.
        :param data: The question data to be created.
        :return: The created question data.
        """
        try:
            statement = (
                select(Group)
                .where(Group.id == group_id)
                .options(selectinload(Group.project))
            )
            if not (group := await session.scalar(statement)):
                raise HTTPException(status_code=404, detail="Group not found.")

            passages: Sequence[Passage] = []
            if data.annotations:
                for annotation in data.annotations:
                    term = await AnnotationService.get_or_create_term(
                        session, group.project_id, annotation.term
                    )
                    passage = await AnnotationService.get_or_create_passage(
                        session, term.id, annotation.passage
                    )
                    passages += [passage]

            question = Question(
                question=data.question,
                sparql_query=data.sparql_query,
                author_id=request.user.id,
                editor_id=request.user.id,
                group_id=group_id,
                version_number=1,
                annotations=passages,
            )

            session.add(question)
            await session.commit()
            await session.refresh(question)

            question = await session.scalar(
                select(Question)
                .where(Question.id == question.id)
                .options(*self.detail_options)
            )
            if question:
                return question
            else:
                raise HTTPException(status_code=404, detail="Question not found.")
        except IntegrityError:
            raise HTTPException(status_code=400, detail="Integrity violated.")

    @get("/", return_dto=QuestionOverviewDTO, status_code=HTTP_200_OK)
    async def get_questions(self, session: AsyncSession) -> Sequence[Question]:
        """
        :param session: AsyncSession object used to execute the database query and retrieve questions.
        :return: A list of QuestionDTO objects representing the retrieved questions.
        """
        return (
            await session.scalars(select(Question).options(*self.default_options))
        ).all()

    @get("/{group_id:uuid}", return_dto=QuestionOverviewDTO, status_code=HTTP_200_OK)
    async def get_group_questions(
        self, session: AsyncSession, group_id: UUID
    ) -> Sequence[Question]:
        """Gets all `Question`s belonging to a given `Group`."""
        return await QuestionService.get_questions_by_group(
            session, group_id, self.default_options
        )

    @get(
        "/{group_id:uuid}/unified",
        summary="Gets unified Questions belonging to a Group",
        return_dto=UnifiedQuestionOverviewDTO,
        status_code=HTTP_200_OK,
    )
    async def get_group_questions_unified(
        self,
        session: AsyncSession,
        group_id: UUID,
    ) -> Sequence[UnifiedQuestionOverview]:
        """Gets all `Question`s of a `Group` with consolidated sets collapsed to one representative each."""
        return await QuestionService.get_unified_questions_by_group(
            session, group_id, self.unified_options
        )

    @get(
        "/{group_id:uuid}/{question_id:uuid}",
        return_dto=QuestionDetailDTO,
        status_code=HTTP_200_OK,
    )
    async def get_question(
        self, session: AsyncSession, question_id: UUID, group_id: UUID
    ) -> Question:
        """
        Retrieves a question by its ID.

        :param group_id:
        :param session: An `AsyncSession` object representing the database session.
        :param question_id: A `UUID` object representing the ID of the question to retrieve.
        :return: A `QuestionDTO` object containing the retrieved question.
        :raises HTTPException: If the question with the specified ID is not found.
        """

        question = await session.scalar(
            select(Question)
            .where(Question.id == question_id, Question.group_id == group_id)
            .options(*self.detail_options)
        )

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        return question

    @put(
        "/{group_id:uuid}/{question_id:uuid}",
        dto=QuestionCreateDTO,
        return_dto=QuestionDetailDTO,
        status_code=HTTP_200_OK,
    )
    async def update_question(
        self,
        session: AsyncSession,
        data: JsonEncoded[QuestionCreate],
        question_id: UUID,
        request: Request[User, Any, Any],
    ) -> Question:
        question = await session.scalar(
            select(Question).where(Question.id == question_id)
        )

        if not question:
            raise HTTPException(status_code=404, detail="Question not found.")

        try:
            version = Version(
                question_string=question.question,
                version_number=question.version_number,
                question_id=question.id,
                editor_id=question.editor_id,
            )
            session.add(version)
            question.editor_id = request.user.id
            question.question = data.question
            question.sparql_query = data.sparql_query
            question.version_number = question.version_number + 1
            session.add(question)
            await session.commit()
            await session.refresh(question)
            await session.refresh(version)

            if updated_question := await session.scalar(
                select(Question)
                .where(Question.id == question.id)
                .options(*self.detail_options)
            ):
                return updated_question
            else:
                raise HTTPException(status_code=404, detail="Question not found.")

        except IntegrityError:
            raise HTTPException(status_code=400, detail="Integrity violated.")

    @delete("/{group_id:uuid}/{question_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    async def delete_question(
        self, session: AsyncSession, question_id: UUID, group_id: UUID
    ) -> None:
        """
        Deletes a question from the database.

        :param session: The async session used to interact with the database.
        :param question_id: The UUID of the question to be deleted.
        :return: None

        :raises HTTPException: If the question with the specified ID is not found.
        """

        question = await session.scalar(
            select(Question).where(
                Question.id == question_id, Question.group_id == group_id
            )
        )

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        await session.delete(question)
        return

    @get(
        "/by_project/{project_id:uuid}",
        summary="Gets all Questions that are part of a Project",
        return_dto=QuestionOverviewDTO,
    )
    async def by_project(
        self, session: AsyncSession, project_id: UUID
    ) -> Sequence[Question]:
        """Gets all `Question`s that are part of a `Project`."""
        return await QuestionService.get_questions_by_project(
            session, project_id, self.detail_options
        )

    @get(
        "/by_project/{project_id:uuid}/unified",
        summary="Gets unified Questions that are part of a Project",
        return_dto=UnifiedQuestionOverviewDTO,
    )
    async def by_project_unified(
        self, session: AsyncSession, project_id: UUID
    ) -> Sequence[UnifiedQuestionOverview]:
        """Gets all `Question`s of a `Project` with consolidated sets collapsed to one representative each."""
        return await QuestionService.get_unified_questions_by_project(
            session, project_id, self.unified_options
        )
