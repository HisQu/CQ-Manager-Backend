from uuid import UUID

from domain.projects.guards import project_participant_guard
from domain.projects.middleware import UserProjectPermissionsMiddleware
from litestar import Controller, post
from litestar.status_codes import HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from .dtos import (
    AnnotationProposalRequest,
    AnnotationProposalRequestDTO,
    AnnotationProposalResponse,
    AnnotationProposalResponseDTO,
)
from .services import AnnotationProposalService


class AnnotationProposalController(Controller):
    path = "/annotation-proposals"
    tags = ["Annotation Proposals"]
    middleware = [UserProjectPermissionsMiddleware]

    @post(
        "/project/{project_id:uuid}/questions/{question_id:uuid}",
        summary="Propose annotations for a question",
        dto=AnnotationProposalRequestDTO,
        return_dto=AnnotationProposalResponseDTO,
        guards=[project_participant_guard],
        status_code=HTTP_200_OK,
    )
    async def propose(
        self,
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        data: AnnotationProposalRequest,
    ) -> AnnotationProposalResponse:
        """Generate read-only span and glossary-term suggestions for the supplied question text."""
        return await AnnotationProposalService.propose(session, project_id, question_id, data)
