from typing import Annotated, Any, Sequence, TypeVar
from uuid import UUID

from domain.accounts.models import User
from domain.consolidations.services import ConsolidationService
from domain.projects.middleware import UserProjectPermissionsMiddleware
from domain.questions.models import Question
from litestar import Controller, Request, delete, get, post, put
from litestar.enums import RequestEncodingType
from litestar.params import Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .dtos import (
    ConsolidationCreate,
    ConsolidationCreateDTO,
    ConsolidationDTO,
    ConsolidationUpdate,
    ConsolidationUpdateDTO,
    MoveQuestion,
    MoveQuestionDTO,
)
from .models import Consolidation

T = TypeVar("T")
JsonEncoded = Annotated[T, Body(media_type=RequestEncodingType.JSON)]


class ConsolidationController(Controller):
    path = "/consolidations"
    tags = ["Consolidations"]
    middleware = [UserProjectPermissionsMiddleware]

    default_options = [
        selectinload(Consolidation.project),
        selectinload(Consolidation.engineer),
        selectinload(Consolidation.questions).options(selectinload(Question.author), selectinload(Question.ratings), selectinload(Question.group)),
        selectinload(Consolidation.result_question).options(
            selectinload(Question.author),
            selectinload(Question.ratings),
            selectinload(Question.group),
        ),
    ]

    @get("/", return_dto=ConsolidationDTO)
    async def get_consolidations_handler(self, session: AsyncSession) -> Sequence[Consolidation]:
        """Gets a all `Consolidations`."""
        return await ConsolidationService.get_consolidations(session, options=self.default_options)

    @get("/{project_id:uuid}", return_dto=ConsolidationDTO)
    async def get_project_consolidations_handler(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> Sequence[Consolidation]:
        """Gets a all `Consolidations` belonging to a specific `Project`."""
        return await ConsolidationService.get_consolidations(session, project_id, self.default_options)

    @get("/{project_id:uuid}/{consolidation_id:uuid}", return_dto=ConsolidationDTO)
    async def get_project_consolidation_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        project_id: UUID,
    ) -> Consolidation:
        """Gets a single `Consolidation` belonging to a specific `Project`."""
        return await ConsolidationService.get_consolidation(
            session, consolidation_id, project_id, self.default_options
        )

    @post("/{project_id:uuid}", dto=ConsolidationCreateDTO, return_dto=ConsolidationDTO)
    async def create_consolidation_handler(
        self,
        request: Request[User, Any, Any],
        session: AsyncSession,
        data: JsonEncoded[ConsolidationCreate],
        project_id: UUID,
    ) -> Consolidation:
        """Creates a new `Consolidation` within a given `Project`."""
        return await ConsolidationService.create_consolidation(
            session, request.user.id, project_id, data, self.default_options
        )

    @put("/{project_id:uuid}/{consolidation_id:uuid}", dto=ConsolidationUpdateDTO, return_dto=ConsolidationDTO)
    async def update_consolidation_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        data: JsonEncoded[ConsolidationUpdate],
        project_id: UUID,
    ) -> Consolidation:
        """Updates an existing `Consolidation` within a given `Project`."""
        return await ConsolidationService.update_consolidation(
            session, consolidation_id, project_id, data, self.default_options
        )

    @delete("/{project_id:uuid}/{consolidation_id:uuid}")
    async def delete_consolidation_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        project_id: UUID,
    ) -> None:
        """Deletes an existing `Consolidation`."""
        await ConsolidationService.delete_consolidation(session, consolidation_id, project_id)

    @put("/{project_id:uuid}/{consolidation_id:uuid}/questions/add", dto=MoveQuestionDTO, return_dto=ConsolidationDTO)
    async def add_question_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        project_id: UUID,
        data: JsonEncoded[MoveQuestion],
    ) -> Consolidation:
        """Add `Questions` to an existing `Consolidation`."""
        return await ConsolidationService.add_questions(session, consolidation_id, project_id, data, self.default_options)

    @put("/{project_id:uuid}/{consolidation_id:uuid}/questions/remove", dto=MoveQuestionDTO, return_dto=ConsolidationDTO)
    async def remove_question_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        project_id: UUID,
        data: JsonEncoded[MoveQuestion],
    ) -> Consolidation:
        """Removes `Questions` from an existing `Consolidation`."""
        return await ConsolidationService.remove_questions(session, consolidation_id, project_id,data, self.default_options)
