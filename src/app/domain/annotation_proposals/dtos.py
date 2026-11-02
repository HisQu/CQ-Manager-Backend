from typing import Any
from uuid import UUID

from lib.dto import BaseModel
from litestar.contrib.pydantic import PydanticDTO
from litestar.dto import DTOConfig

class AnnotationProposalRequest(BaseModel):
    revision_id: UUID
    exclude_annotated: bool = True


class AnnotationProposalRequestDTO(PydanticDTO[AnnotationProposalRequest]):
    config = DTOConfig(rename_strategy="camel")


class AnnotationProposalReviewRequest(BaseModel):
    reject: bool = False


class AnnotationProposalReviewRequestDTO(PydanticDTO[AnnotationProposalReviewRequest]):
    config = DTOConfig(rename_strategy="camel")


class AnnotationCandidate(BaseModel):
    proposal_id: UUID
    text: str
    start: int
    end: int
    lemma: str
    rule: str
    tokens: list[dict[str, str]]
    match_status: str
    matches: list[dict[str, Any]]
    suggested_term: dict[str, Any]


class AnnotationProposalResponse(BaseModel):
    question_id: UUID
    revision_id: UUID
    proposal_run_id: UUID | None
    candidates: list[AnnotationCandidate]
    matcher: dict[str, Any]
    context_matcher: dict[str, Any]


class AnnotationProposalResponseDTO(PydanticDTO[AnnotationProposalResponse]):
    config = DTOConfig(rename_strategy="camel")
