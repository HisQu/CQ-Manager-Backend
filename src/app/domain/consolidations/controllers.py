from typing import Annotated, Any, Sequence, TypeVar
from uuid import UUID

from domain.accounts.models import User
from domain.consolidations.services import ConsolidationService
from domain.groups.models import Group
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
    ConsolidationRead,
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
        selectinload(Consolidation.questions).options(
            selectinload(Question.author),
            selectinload(Question.editor),
            selectinload(Question.ratings),
            selectinload(Question.group).options(
                selectinload(Group.members),
                selectinload(Group.questions),
            ),
        ),
        selectinload(Consolidation.result_question).options(
            selectinload(Question.author),
            selectinload(Question.editor),
            selectinload(Question.ratings),
            selectinload(Question.group).options(
                selectinload(Group.members),
                selectinload(Group.questions),
            ),
        ),
    ]

    @staticmethod
    def _to_response(consolidation: Consolidation) -> ConsolidationRead:
        return ConsolidationRead.model_validate(consolidation)

    @staticmethod
    def _to_response_list(
        consolidations: Sequence[Consolidation],
    ) -> list[ConsolidationRead]:
        return [
            ConsolidationController._to_response(consolidation)
            for consolidation in consolidations
        ]

    @get("/", return_dto=ConsolidationDTO)
    async def get_consolidations_handler(
        self, session: AsyncSession
    ) -> Sequence[ConsolidationRead]:
        """Gets a all `Consolidations`."""
        consolidations = await ConsolidationService.get_consolidations(
            session, options=self.default_options
        )
        return self._to_response_list(consolidations)

    @get("/{project_id:uuid}", return_dto=ConsolidationDTO)
    async def get_project_consolidations_handler(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> Sequence[ConsolidationRead]:
        """Gets a all `Consolidations` belonging to a specific `Project`."""
        consolidations = await ConsolidationService.get_consolidations(
            session, project_id, self.default_options
        )
        return self._to_response_list(consolidations)

    @get("/{project_id:uuid}/{consolidation_id:uuid}", return_dto=ConsolidationDTO)
    async def get_project_consolidation_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        project_id: UUID,
    ) -> ConsolidationRead:
        """Gets a single `Consolidation` belonging to a specific `Project`."""
        consolidation = await ConsolidationService.get_consolidation(
            session, consolidation_id, project_id, self.default_options
        )
        return self._to_response(consolidation)

    @post(
        "/{project_id:uuid}",
        dto=ConsolidationCreateDTO,
        return_dto=ConsolidationDTO,
    )
    async def create_consolidation_handler(
        self,
        request: Request[User, Any, Any],
        session: AsyncSession,
        data: JsonEncoded[ConsolidationCreate],
        project_id: UUID,
    ) -> ConsolidationRead:
        """Creates a new `Consolidation` within a given `Project`."""
        consolidation = await ConsolidationService.create_consolidation(
            session, request.user.id, project_id, data, self.default_options
        )
        return self._to_response(consolidation)

    @put(
        "/{project_id:uuid}/{consolidation_id:uuid}",
        dto=ConsolidationUpdateDTO,
        return_dto=ConsolidationDTO,
    )
    async def update_consolidation_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        data: JsonEncoded[ConsolidationUpdate],
        project_id: UUID,
    ) -> ConsolidationRead:
        """Updates an existing `Consolidation` within a given `Project`."""
        consolidation = await ConsolidationService.update_consolidation(
            session, consolidation_id, project_id, data, self.default_options
        )
        return self._to_response(consolidation)

    @delete("/{project_id:uuid}/{consolidation_id:uuid}")
    async def delete_consolidation_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        project_id: UUID,
    ) -> None:
        """Deletes an existing `Consolidation`."""
        await ConsolidationService.delete_consolidation(session, consolidation_id, project_id)

    @put(
        "/{project_id:uuid}/{consolidation_id:uuid}/questions/add",
        dto=MoveQuestionDTO,
        return_dto=ConsolidationDTO,
    )
    async def add_question_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        project_id: UUID,
        data: JsonEncoded[MoveQuestion],
    ) -> ConsolidationRead:
        """Add `Questions` to an existing `Consolidation`."""
        consolidation = await ConsolidationService.add_questions(
            session, consolidation_id, project_id, data, self.default_options
        )
        return self._to_response(consolidation)

    @put(
        "/{project_id:uuid}/{consolidation_id:uuid}/questions/remove",
        dto=MoveQuestionDTO,
        return_dto=ConsolidationDTO,
    )
    async def remove_question_handler(
        self,
        session: AsyncSession,
        consolidation_id: UUID,
        project_id: UUID,
        data: JsonEncoded[MoveQuestion],
    ) -> ConsolidationRead:
        """Removes `Questions` from an existing `Consolidation`."""
        consolidation = await ConsolidationService.remove_questions(
            session, consolidation_id, project_id, data, self.default_options
        )
        return self._to_response(consolidation)
