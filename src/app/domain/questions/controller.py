from datetime import datetime, timezone
from typing import Annotated, Any, Sequence, TypeVar
from uuid import UUID

from domain.accounts.guards import system_admin_guard
from domain.accounts.models import User
from domain.comments.models import Comment
from domain.comments.services import CommentsService
from domain.consolidations.models import Consolidation
from domain.groups.middleware import UserGroupPermissionsMiddleware
from domain.groups.models import Group
from domain.history.dtos import QuestionEventRead, QuestionEventReadDTO
from domain.history.models import QuestionEventType
from domain.history.services import HistoryService
from domain.projects.middleware import UserProjectPermissionsMiddleware
from domain.questions.middleware import UserQuestionGroupPermissionsMiddleware
from domain.questions.services import QuestionService
from domain.ratings.models import Rating
from domain.tags.services import TagService
from domain.topics.services import TopicService
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
from .models import Question
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
        selectinload(Question.comments).options(selectinload(Comment.author)),
        selectinload(Question.consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.target_consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.topic),
        selectinload(Question.tags),
        selectinload(Question.group).options(selectinload(Group.project)),
    ]
    unified_options = [
        selectinload(Question.author),
        selectinload(Question.ratings),
        selectinload(Question.comments).options(selectinload(Comment.author)),
        selectinload(Question.topic),
        selectinload(Question.tags),
        selectinload(Question.consolidations).options(
            selectinload(Consolidation.engineer),
            selectinload(Consolidation.questions),
            selectinload(Consolidation.result_question).options(
                selectinload(Question.author),
                selectinload(Question.ratings),
                selectinload(Question.comments).options(selectinload(Comment.author)),
                selectinload(Question.consolidations),
                selectinload(Question.topic),
                selectinload(Question.tags),
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
        selectinload(Question.tags),
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
                    term = await AnnotationService.get_or_create_term(
                        session,
                        group.project_id,
                        annotation.term,
                        annotation.definition,
                        annotation.concept_iri,
                    )
                    passage = await AnnotationService.get_or_create_passage(session, term.id, annotation.passage)
                    passages += [passage]

            tags = await TagService.resolve_tags(session, group.project_id, data.tag_ids)

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
                tags=tags,
            )

            session.add(question)
            await session.flush()
            HistoryService.record(session, question, QuestionEventType.CREATED, request.user.id)
            HistoryService.record_tag_changes(session, question, [], tags, request.user.id)
            await TopicService.assign_uncatalogued(session, group.project_id, question, request.user.id)
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
    async def get_questions(
        self, session: AsyncSession, request: Request[User, Any, Any]
    ) -> Sequence[QuestionOverview]:
        """
        :param session: AsyncSession object used to execute the database query and retrieve questions.
        :return: A list of QuestionDTO objects representing the retrieved questions.
        """
        questions = (await session.scalars(select(Question).options(*self.default_options))).all()
        reader = await CommentsService.get_reader(session, request.user.id)
        return QuestionService.to_question_overviews(questions, reader)

    @get("/by_group/{group_id:uuid}", return_dto=QuestionOverviewDTO, status_code=HTTP_200_OK)
    async def get_group_questions(
        self, session: AsyncSession, group_id: UUID, request: Request[User, Any, Any]
    ) -> Sequence[QuestionOverview]:
        """Gets all `Question`s belonging to a given `Group`."""
        questions = await QuestionService.get_questions_by_group(session, group_id, self.default_options)
        reader = await CommentsService.get_reader(session, request.user.id)
        return QuestionService.to_question_overviews(questions, reader)

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
        request: Request[User, Any, Any],
    ) -> Sequence[UnifiedQuestionOverview]:
        """Gets all `Question`s of a `Group` with consolidated sets collapsed to one representative each."""
        reader = await CommentsService.get_reader(session, request.user.id)
        return await QuestionService.get_unified_questions_by_group(session, group_id, self.unified_options, reader)

    @get(
        "/{question_id:uuid}",
        return_dto=QuestionDetailDTO,
        status_code=HTTP_200_OK,
    )
    async def get_question(
        self, session: AsyncSession, question_id: UUID, request: Request[User, Any, Any]
    ) -> QuestionDetail:
        """
        Retrieves a question by its ID. System admins can retrieve deleted questions, too.

        :param session: An `AsyncSession` object representing the database session.
        :param question_id: A `UUID` object representing the ID of the question to retrieve.
        :return: A `QuestionDTO` object containing the retrieved question.
        :raises HTTPException: If the question with the specified ID is not found.
        """

        question = await session.scalar(
            QuestionService.visible_to(
                select(Question).where(Question.id == question_id).options(*self.detail_options),
                request.user,
            )
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
            snapshot = Version(
                question_string=question.question,
                sparql_query=question.sparql_query,
                example_answer=question.example_answer,
                version_number=question.version_number,
                question_id=question.id,
                editor_id=question.editor_id,
            )
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
            # Only changes to the question, its SPARQL query or its example answer make a new revision.
            if (question.question, question.sparql_query, question.example_answer) != (
                snapshot.question_string,
                snapshot.sparql_query,
                snapshot.example_answer,
            ):
                session.add(snapshot)
                question.editor_id = request.user.id
                question.version_number = question.version_number + 1
                HistoryService.record(session, question, QuestionEventType.REVISED, request.user.id)
            await session.commit()

            if updated_question := await session.scalar(
                select(Question).where(Question.id == question_id).options(*self.detail_options)
            ):
                return QuestionService.to_question_detail(updated_question)
            else:
                raise HTTPException(status_code=404, detail="Question not found.")

        except IntegrityError:
            raise HTTPException(status_code=400, detail="Integrity violated.")

    @delete("/{question_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    async def delete_question(
        self, session: AsyncSession, question_id: UUID, request: Request[User, Any, Any]
    ) -> None:
        """
        Marks a question as deleted. It keeps its catalogue identifier and history and stays visible to system admins.

        :param session: The async session used to interact with the database.
        :param question_id: The UUID of the question to be deleted.
        :return: None

        :raises HTTPException: If the question with the specified ID is not found.
        """

        question = await session.scalar(select(Question).where(Question.id == question_id))

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        question.deleted_at = datetime.now(timezone.utc)
        HistoryService.record(session, question, QuestionEventType.DELETED, request.user.id)

    @get(
        "/{question_id:uuid}/history",
        summary="Gets the provenance log of a Question",
        return_dto=QuestionEventReadDTO,
        status_code=HTTP_200_OK,
    )
    async def get_question_history(
        self, session: AsyncSession, question_id: UUID, request: Request[User, Any, Any]
    ) -> Sequence[QuestionEventRead]:
        """Gets every recorded change of a `Question` (creation, revisions, tags, catalogue, deletion), oldest first."""
        if not await session.scalar(
            QuestionService.visible_to(select(Question.id).where(Question.id == question_id), request.user)
        ):
            raise HTTPException(status_code=404, detail="Question not found.")
        return [QuestionEventRead.model_validate(event) for event in await HistoryService.list_events(session, question_id)]

    @get(
        "/by_project/{project_id:uuid}",
        summary="Gets all Questions that are part of a Project",
        return_dto=QuestionOverviewDTO,
    )
    async def by_project(
        self, session: AsyncSession, project_id: UUID, request: Request[User, Any, Any]
    ) -> Sequence[QuestionOverview]:
        """Gets all `Question`s that are part of a `Project`."""
        questions = await QuestionService.get_questions_by_project(session, project_id, self.detail_options)
        reader = await CommentsService.get_reader(session, request.user.id)
        return QuestionService.to_question_overviews(questions, reader)

    @get(
        "/by_project/{project_id:uuid}/deleted",
        summary="Gets all deleted Questions of a Project",
        return_dto=QuestionOverviewDTO,
        guards=[system_admin_guard],
    )
    async def deleted_by_project(self, session: AsyncSession, project_id: UUID) -> Sequence[QuestionOverview]:
        """Gets all soft deleted `Question`s of a `Project`, most recently deleted first. System admins only."""
        questions = await QuestionService.get_deleted_questions_by_project(session, project_id, self.default_options)
        return QuestionService.to_question_overviews(questions)

    @get(
        "/by_project/{project_id:uuid}/unified",
        summary="Gets unified Questions that are part of a Project",
        return_dto=UnifiedQuestionOverviewDTO,
    )
    async def by_project_unified(
        self, session: AsyncSession, project_id: UUID, request: Request[User, Any, Any]
    ) -> Sequence[UnifiedQuestionOverview]:
        """Gets all `Question`s of a `Project` with consolidated sets collapsed to one representative each."""
        reader = await CommentsService.get_reader(session, request.user.id)
        return await QuestionService.get_unified_questions_by_project(session, project_id, self.unified_options, reader)

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
