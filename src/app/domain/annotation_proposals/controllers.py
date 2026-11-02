from uuid import UUID
from typing import Any

from domain.accounts.models import User
from domain.projects.guards import project_participant_guard
from domain.projects.middleware import UserProjectPermissionsMiddleware
from litestar import Controller, Request, post, put
from litestar.status_codes import HTTP_200_OK, HTTP_204_NO_CONTENT
from sqlalchemy.ext.asyncio import AsyncSession

from .dtos import (
    AnnotationProposalRequest,
    AnnotationProposalRequestDTO,
    AnnotationProposalReviewRequest,
    AnnotationProposalReviewRequestDTO,
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
        request: Request[User, Any, Any],
    ) -> AnnotationProposalResponse:
        """Generate read-only span and glossary-term suggestions for the supplied question text."""
        return await AnnotationProposalService.propose(session, project_id, question_id, data, request.user.id)

    @put(
        "/project/{project_id:uuid}/questions/{question_id:uuid}/runs/{run_id:uuid}/review",
        summary="Record annotation proposal review",
        dto=AnnotationProposalReviewRequestDTO,
        guards=[project_participant_guard],
        status_code=HTTP_204_NO_CONTENT,
    )
    async def review(
        self,
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        run_id: UUID,
        data: AnnotationProposalReviewRequest,
        request: Request[User, Any, Any],
    ) -> None:
        """Record whether proposed spans and terms were retained in the final staged annotation set."""
        await AnnotationProposalService.review(
            session, project_id, question_id, run_id, data.reject, request.user.id
        )
