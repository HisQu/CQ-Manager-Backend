from typing import Sequence
from uuid import UUID

from domain.projects.guards import ontology_engineer_guard
from domain.questions.dtos import QuestionOverviewDTO
from domain.questions.models import Question
from litestar import Controller, delete, get, put
from litestar.exceptions import NotFoundException
from litestar.status_codes import HTTP_204_NO_CONTENT
from sqlalchemy.ext.asyncio import AsyncSession

from .dtos import (
    AnnotationAddDTO,
    AnnotationRemove,
    AnnotationRemoveDTO,
    AnnotationUpdate,
    AnnotationUpdateDTO,
    PassageDTO,
    TermDTO,
    TermUpdate,
    TermUpdateDTO,
)
from .models import Passage, Term
from .services import AnnotationService

from domain.questions.controller import QuestionController


class TermController(Controller):
    tags = ["Terms"]
    path = "/terms"

    @get("/", summary="Get All", return_dto=TermDTO)
    async def get_all(self, session: AsyncSession) -> Sequence[Term]:
        """Gets all `Terms` within the system."""
        return await AnnotationService.list(session)

    @get(
        "/project/{project_id:uuid}", summary="Get Terms by Project", return_dto=TermDTO
    )
    async def get_all_project(
        self, session: AsyncSession, project_id: UUID
    ) -> Sequence[Term]:
        """Gets all `Term`s and  `Passage`s within a `Project`."""
        return await AnnotationService.list(session, (Term.project_id == project_id,))

    @get(
        "/question/{question_id:uuid}",
        summary="Get Passages by Question",
        return_dto=PassageDTO,
    )
    async def get_all_question_project(
        self, session: AsyncSession, question_id: UUID
    ) -> Sequence[Passage]:
        """Gets all `Passage`s associated with a `Question`."""
        return await AnnotationService.list_by_question(session, question_id)

    @put(
        "/add/{question_id:uuid}",
        summary="Add Annotations to Question",
        return_dto=PassageDTO,
    )
    async def add(
        self, session: AsyncSession, question_id: UUID, data: AnnotationAddDTO
    ) -> Sequence[Passage]:
        """Adds one or more `Passage`s and `Term`s to a `Question` or updates existing `Passage`s."""
        return await AnnotationService.annotate(session, question_id, data)

    @put(
        "/remove/{question_id:uuid}",
        summary="Remove Annotations from Question",
        dto=AnnotationRemoveDTO,
        return_dto=PassageDTO,
    )
    async def remove_annotations(
        self, session: AsyncSession, question_id: UUID, data: AnnotationRemove
    ) -> Sequence[Passage]:
        """Removes one or more `Passage`s and `Term`s from a `Question`, returns leftover `Passage`s."""
        return await AnnotationService.remove_annotations(session, question_id, data)

    @put(
        "/{project_id:uuid}/{question_id:uuid}/{passage_id:uuid}",
        summary="Edit an Annotation",
        dto=AnnotationUpdateDTO,
        return_dto=PassageDTO,
        guards=[ontology_engineer_guard],
    )
    async def update_annotation(
        self,
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        passage_id: UUID,
        data: AnnotationUpdate,
    ) -> Passage:
        """Updates a `Passage` and optionally reassigns it to another `Term` within a `Project`."""
        return await AnnotationService.update_annotation(
            session, project_id, question_id, passage_id, data
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
    ) -> Sequence[Question]:
        """Gets all `Question`s within a given `Project` that share the given `Term`."""
        return await AnnotationService.list_questions_by_term(
            session, term_id, project_id, QuestionController.default_options
        )
