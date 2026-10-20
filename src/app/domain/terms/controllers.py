from collections.abc import Sequence
from typing import Any
from uuid import UUID

from domain.accounts.models import User
from domain.projects.guards import ontology_engineer_guard
from domain.questions.controller import QuestionController
from domain.projects.middleware import UserProjectPermissionsMiddleware
from domain.questions.dtos import QuestionOverview, QuestionOverviewDTO
from domain.questions.services import QuestionService
from litestar import Controller, Request, delete, get, post, put
from litestar.exceptions import NotFoundException
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from sqlalchemy.ext.asyncio import AsyncSession

from .dtos import (
    AnnotationSetSaveDTO,
    AnnotationSetSavePydanticDTO,
    AnnotationVersionRead,
    AnnotationVersionReadDTO,
    PassageDTO,
    TermCreate,
    TermCreateDTO,
    TermDTO,
    TermOverview,
    TermOverviewDTO,
    TermUpdate,
    TermUpdateDTO,
)
from .models import Passage, Term
from .services import AnnotationService


class TermController(Controller):
    tags = ["Terms"]
    path = "/terms"
    middleware = [UserProjectPermissionsMiddleware]

    @get("/", summary="Get All", return_dto=TermDTO)
    async def get_all(self, session: AsyncSession) -> Sequence[Term]:
        """Gets all `Terms` within the system."""
        return await AnnotationService.list(session)

    @get(
        "/project/{project_id:uuid}", summary="Get Terms by Project", return_dto=TermOverviewDTO
    )
    async def get_all_project(
        self, session: AsyncSession, project_id: UUID
    ) -> Sequence[TermOverview]:
        """Gets all `Term`s within a `Project` with the number of `Question`s currently annotating each."""
        terms = await AnnotationService.list(session, (Term.project_id == project_id,))
        counts = await AnnotationService.count_questions_per_term(session, project_id)
        return [
            TermOverview(
                id=term.id,
                project_id=term.project_id,
                content=term.content,
                definition=term.definition,
                concept_iri=term.concept_iri,
                no_questions=counts.get(term.id, 0),
            )
            for term in terms
        ]

    @post(
        "/project/{project_id:uuid}",
        summary="Create or retrieve a project term",
        dto=TermCreateDTO,
        return_dto=TermDTO,
        status_code=HTTP_201_CREATED,
    )
    async def create_term(
        self, session: AsyncSession, project_id: UUID, data: TermCreate
    ) -> Term:
        """Writes a term to the shared project glossary independently of annotation snapshots."""
        return await AnnotationService.create_term(session, project_id, data)

    @get(
        "/question/{question_id:uuid}",
        summary="Get Passages by Question",
        return_dto=PassageDTO,
    )
    async def get_all_question_project(
        self, session: AsyncSession, question_id: UUID
    ) -> Sequence[Passage]:
        """Gets annotations for the current CQ and annotation versions."""
        return await AnnotationService.list_by_question(session, question_id)

    @put(
        "/question/{question_id:uuid}/revisions/{revision_id:uuid}/annotations",
        summary="Save an Annotation Version",
        dto=AnnotationSetSavePydanticDTO,
        return_dto=AnnotationVersionReadDTO,
    )
    async def save_annotation_version(
        self,
        session: AsyncSession,
        question_id: UUID,
        revision_id: UUID,
        data: AnnotationSetSaveDTO,
        request: Request[User, Any, Any],
    ) -> AnnotationVersionRead:
        """Stores the submitted annotation set as a new immutable snapshot."""
        return await AnnotationService.save_annotation_version(
            session, question_id, revision_id, data, request.user.id
        )

    @put(
        "/{project_id:uuid}/{term_id:uuid}",
        summary="Edit a Term",
        dto=TermUpdateDTO,
        return_dto=TermDTO,
        guards=[ontology_engineer_guard],
    )
    async def update_term(
        self, session: AsyncSession, project_id: UUID, term_id: UUID, data: TermUpdate
    ) -> Term:
        """Updates the content of a `Term` in a `Project`."""
        return await AnnotationService.update_term(session, project_id, term_id, data)

    @delete(
        "/{project_id:uuid}/{term_id:uuid}",
        guards=[ontology_engineer_guard],
        status_code=HTTP_204_NO_CONTENT,
    )
    async def delete_term(
        self, session: AsyncSession, project_id: UUID, term_id: UUID
    ) -> None:
        """Deletes a `Term` and unlinks/removes its associated `Passage`s."""
        if await AnnotationService.delete_term(session, project_id, term_id):
            return
        raise NotFoundException()

    @get(
        "/{project_id:uuid}/{term_id:uuid}",
        summary="Get Question by Term",
        return_dto=QuestionOverviewDTO,
    )
    async def get_by_term(
        self, session: AsyncSession, project_id: UUID, term_id: UUID
    ) -> Sequence[QuestionOverview]:
        """Gets all `Question`s within a given `Project` that share the given `Term`."""
        questions = await AnnotationService.list_questions_by_term(
            session, term_id, project_id, QuestionController.default_options
        )
        return QuestionService.to_question_overviews(questions)
