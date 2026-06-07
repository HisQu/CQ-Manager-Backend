from typing import Annotated, Any, Sequence, TypeVar
from uuid import UUID

from domain.accounts.models import User
from domain.comments.models import Comment
from domain.consolidations.models import Consolidation
from domain.groups.middleware import UserGroupPermissionsMiddleware
from domain.groups.models import Group
from domain.projects.middleware import UserProjectPermissionsMiddleware
from domain.questions.middleware import UserQuestionGroupPermissionsMiddleware
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
    QuestionCatalogueResolution,
    QuestionCatalogueResolutionDTO,
    QuestionCreate,
    QuestionCreateDTO,
    QuestionDetail,
    QuestionDetailDTO,
    QuestionOverview,
    QuestionOverviewDTO,
    QuestionUpdate,
    QuestionUpdateDTO,
    UnifiedQuestionOverview,
    UnifiedQuestionOverviewDTO,
)
from .models import Question, QuestionCatalogueReservation
from domain.terms.services import AnnotationService
from domain.terms.models import Passage

T = TypeVar("T")
JsonEncoded = Annotated[T, Body(media_type=RequestEncodingType.JSON)]


class QuestionController(Controller):
    path = "/questions/"
    tags = ["Questions"]
    middleware = [
        UserGroupPermissionsMiddleware,
        UserQuestionGroupPermissionsMiddleware,
        UserProjectPermissionsMiddleware,
    ]

    default_options = [
        selectinload(Question.author),
        selectinload(Question.ratings),
        selectinload(Question.comments),
        selectinload(Question.consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.target_consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.topic),
        selectinload(Question.group).options(selectinload(Group.project)),
    ]
    unified_options = [
        selectinload(Question.author),
        selectinload(Question.ratings),
        selectinload(Question.comments),
        selectinload(Question.topic),
        selectinload(Question.consolidations).options(
            selectinload(Consolidation.engineer),
            selectinload(Consolidation.questions),
            selectinload(Consolidation.result_question).options(
                selectinload(Question.author),
                selectinload(Question.ratings),
                selectinload(Question.comments),
                selectinload(Question.consolidations),
                selectinload(Question.topic),
                selectinload(Question.group),
            ),
        ),
        selectinload(Question.target_consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.group).options(selectinload(Group.project)),
    ]
    detail_options = [
        selectinload(Question.author),
        selectinload(Question.editor),
        selectinload(Question.ratings).options(selectinload(Rating.author)),
        selectinload(Question.topic),
        selectinload(Question.consolidations).options(
            selectinload(Consolidation.questions).options(
                selectinload(Question.author),
                selectinload(Question.ratings),
                selectinload(Question.topic),
                selectinload(Question.group),
            ),
            selectinload(Consolidation.result_question).options(
                selectinload(Question.author),
                selectinload(Question.ratings),
                selectinload(Question.topic),
                selectinload(Question.group),
            ),
            selectinload(Consolidation.engineer),
            selectinload(Consolidation.project),
        ),
        selectinload(Question.target_consolidations).options(
            selectinload(Consolidation.questions).options(
                selectinload(Question.author),
                selectinload(Question.ratings),
                selectinload(Question.topic),
                selectinload(Question.group),
            ),
            selectinload(Consolidation.result_question).options(
                selectinload(Question.author),
                selectinload(Question.ratings),
                selectinload(Question.topic),
                selectinload(Question.group),
            ),
            selectinload(Consolidation.engineer),
            selectinload(Consolidation.project),
        ),
        selectinload(Question.group).options(selectinload(Group.project)),
        selectinload(Question.versions).options(selectinload(Version.editor)),
        selectinload(Question.annotations).options(selectinload(Passage.term)),
        selectinload(Question.comments).options(selectinload(Comment.author)),
    ]

    @post(
        "/by_group/{group_id:uuid}",
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
    ) -> QuestionDetail:
        """
        Creates a new `Question`

        :param group_id:
        :param request: Request[User, Any, Any]
        :param session: The session object to use for database operations.
        :param data: The question data to be created.
        :return: The created question data.
        """
        try:
            statement = select(Group).where(Group.id == group_id).options(selectinload(Group.project))
            if not (group := await session.scalar(statement)):
                raise HTTPException(status_code=404, detail="Group not found.")

            passages: Sequence[Passage] = []
            if data.annotations:
                for annotation in data.annotations:
                    term = await AnnotationService.get_or_create_term(session, group.project_id, annotation.term)
                    passage = await AnnotationService.get_or_create_passage(session, term.id, annotation.passage)
                    passages += [passage]

            question = Question(
                question=data.question,
                comment=data.comment,
                reference=data.reference,
                anchor=data.anchor,
                example_answer=data.example_answer,
                type=data.type,
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
                select(Question).where(Question.id == question.id).options(*self.detail_options)
            )
            if question:
                return QuestionService.to_question_detail(question)
            else:
                raise HTTPException(status_code=404, detail="Question not found.")
        except IntegrityError:
            raise HTTPException(status_code=400, detail="Integrity violated.")

    @get("/", return_dto=QuestionOverviewDTO, status_code=HTTP_200_OK)
    async def get_questions(self, session: AsyncSession) -> Sequence[QuestionOverview]:
        """
        :param session: AsyncSession object used to execute the database query and retrieve questions.
        :return: A list of QuestionDTO objects representing the retrieved questions.
        """
        questions = (await session.scalars(select(Question).options(*self.default_options))).all()
        return QuestionService.to_question_overviews(questions)

    @get("/by_group/{group_id:uuid}", return_dto=QuestionOverviewDTO, status_code=HTTP_200_OK)
    async def get_group_questions(self, session: AsyncSession, group_id: UUID) -> Sequence[QuestionOverview]:
        """Gets all `Question`s belonging to a given `Group`."""
        questions = await QuestionService.get_questions_by_group(session, group_id, self.default_options)
        return QuestionService.to_question_overviews(questions)

    @get(
        "/by_group/{group_id:uuid}/unified",
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
        return await QuestionService.get_unified_questions_by_group(session, group_id, self.unified_options)

    @get(
        "/{question_id:uuid}",
        return_dto=QuestionDetailDTO,
        status_code=HTTP_200_OK,
    )
    async def get_question(self, session: AsyncSession, question_id: UUID) -> QuestionDetail:
        """
        Retrieves a question by its ID.

        :param session: An `AsyncSession` object representing the database session.
        :param question_id: A `UUID` object representing the ID of the question to retrieve.
        :return: A `QuestionDTO` object containing the retrieved question.
        :raises HTTPException: If the question with the specified ID is not found.
        """

        question = await session.scalar(
            select(Question)
            .where(Question.id == question_id)
            .options(*self.detail_options)
        )

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        return QuestionService.to_question_detail(question)

    @put(
        "/{question_id:uuid}",
        dto=QuestionUpdateDTO,
        return_dto=QuestionDetailDTO,
        status_code=HTTP_200_OK,
    )
    async def update_question(
        self,
        session: AsyncSession,
        data: JsonEncoded[QuestionUpdate],
        question_id: UUID,
        request: Request[User, Any, Any],
    ) -> QuestionDetail:
        question = await session.scalar(select(Question).where(Question.id == question_id))

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
            if data.question is not None:
                question.question = data.question
            if "comment" in data.model_fields_set:
                question.comment = data.comment
            if "reference" in data.model_fields_set:
                question.reference = data.reference
            if "anchor" in data.model_fields_set:
                question.anchor = data.anchor
            if "example_answer" in data.model_fields_set:
                question.example_answer = data.example_answer
            if "type" in data.model_fields_set:
                question.type = data.type
            if "sparql_query" in data.model_fields_set:
                question.sparql_query = data.sparql_query
            question.version_number = question.version_number + 1
            session.add(question)
            await session.commit()
            await session.refresh(question)
            await session.refresh(version)

            if updated_question := await session.scalar(
                select(Question).where(Question.id == question.id).options(*self.detail_options)
            ):
                return QuestionService.to_question_detail(updated_question)
            else:
                raise HTTPException(status_code=404, detail="Question not found.")

        except IntegrityError:
            raise HTTPException(status_code=400, detail="Integrity violated.")

    @delete("/{question_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    async def delete_question(self, session: AsyncSession, question_id: UUID) -> None:
        """
        Deletes a question from the database.

        :param session: The async session used to interact with the database.
        :param question_id: The UUID of the question to be deleted.
        :return: None

        :raises HTTPException: If the question with the specified ID is not found.
        """

        question = await session.scalar(select(Question).where(Question.id == question_id))

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        if question.topic_id is not None and question.catalogue_index is not None:
            reservation = await session.scalar(
                select(QuestionCatalogueReservation).where(
                    QuestionCatalogueReservation.topic_id == question.topic_id,
                    QuestionCatalogueReservation.catalogue_index == question.catalogue_index,
                    QuestionCatalogueReservation.question_id == question.id,
                )
            )
            if reservation:
                reservation.question_id = None

        await session.delete(question)
        return

    @get(
        "/by_project/{project_id:uuid}",
        summary="Gets all Questions that are part of a Project",
        return_dto=QuestionOverviewDTO,
    )
    async def by_project(self, session: AsyncSession, project_id: UUID) -> Sequence[QuestionOverview]:
        """Gets all `Question`s that are part of a `Project`."""
        questions = await QuestionService.get_questions_by_project(session, project_id, self.detail_options)
        return QuestionService.to_question_overviews(questions)

    @get(
        "/by_project/{project_id:uuid}/unified",
        summary="Gets unified Questions that are part of a Project",
        return_dto=UnifiedQuestionOverviewDTO,
    )
    async def by_project_unified(self, session: AsyncSession, project_id: UUID) -> Sequence[UnifiedQuestionOverview]:
        """Gets all `Question`s of a `Project` with consolidated sets collapsed to one representative each."""
        return await QuestionService.get_unified_questions_by_project(session, project_id, self.unified_options)

    @get(
        "/by_project/{project_id:uuid}/catalogue/{catalogue_identifier:str}",
        summary="Resolves a CQ catalogue identifier to the real Question id and Group id",
        return_dto=QuestionCatalogueResolutionDTO,
        status_code=HTTP_200_OK,
    )
    async def resolve_catalogue_identifier(
        self,
        session: AsyncSession,
        project_id: UUID,
        catalogue_identifier: str,
    ) -> QuestionCatalogueResolution:
        question = await QuestionService.resolve_cq_catalogue_identifier(
            session,
            project_id,
            catalogue_identifier,
            [selectinload(Question.topic)],
        )
        return QuestionCatalogueResolution(
            id=question.id,
            group_id=question.group_id,
            cq_catalogue_identifier=question.cq_catalogue_identifier or catalogue_identifier,
        )
