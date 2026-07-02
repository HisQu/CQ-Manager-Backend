from datetime import datetime
from enum import Enum
from typing import Literal, TypeAlias, get_args
from uuid import UUID

from lib.dto import BaseModel
from litestar.contrib.pydantic.pydantic_dto_factory import PydanticDTO
from litestar.dto import DTOConfig
from pydantic import Field, field_validator

from domain.terms.dtos import AnnotationDTO

CQType: TypeAlias = Literal["LCQ", "SCQ", "VCQ", "FCQ", "RCQ", "aRCQ", "efRCQ", "drRCQ", "rpRCQ", "MpCQ"]
CQ_TYPES = frozenset(get_args(CQType))


class QuestionMetadataMixin(BaseModel):
    reference: str | None = None
    anchor: str | None = None
    example_answer: str | None = None
    type: CQType | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: CQType | None) -> CQType | None:
        if value is not None and value not in CQ_TYPES:
            allowed = ", ".join(sorted(CQ_TYPES))
            raise ValueError(f"type must be one of: {allowed}.")
        return value


class QuestionUser(BaseModel):
    id: UUID
    email: str
    name: str


class QuestionProject(BaseModel):
    id: UUID
    name: str


class QuestionGroup(BaseModel):
    id: UUID
    name: str
    project: QuestionProject | None = None


class QuestionTopic(BaseModel):
    id: UUID
    identifier: str
    name: str


class QuestionConsolidationRole(str, Enum):
    SOURCE = "source"
    TARGET = "target"


class QuestionConsolidationContext(BaseModel):
    id: UUID
    role: QuestionConsolidationRole
    source_question_ids: list[UUID] = Field(default_factory=list)
    target_question_id: UUID | None = None


class QuestionOverview(QuestionMetadataMixin):
    id: UUID
    question: str
    comment: str | None = None
    cq_catalogue_identifier: str | None = None
    sparql_query: str | None = None
    rating: int = 0
    no_consolidations: int = 0
    no_comments: int = 0
    group: QuestionGroup | None = None
    topic: QuestionTopic | None = None
    author: QuestionUser | None = None
    consolidations: list[QuestionConsolidationContext] = Field(default_factory=list)


class QuestionOverviewDTO(PydanticDTO[QuestionOverview]):
    config = DTOConfig(rename_strategy="camel", max_nested_depth=2)


class QuestionRating(BaseModel):
    rating: int
    author: QuestionUser


class QuestionComment(BaseModel):
    comment: str
    created_at: datetime
    author: QuestionUser


class QuestionVersion(BaseModel):
    question_string: str
    version_number: int
    editor: QuestionUser


class QuestionAnnotationTerm(BaseModel):
    id: UUID
    content: str
    definition: str | None = None
    concept_iri: str | None = None


class QuestionAnnotation(BaseModel):
    id: UUID
    content: str
    term: QuestionAnnotationTerm


class QuestionDetailConsolidationQuestionGroup(BaseModel):
    id: UUID
    name: str


class QuestionDetailConsolidationQuestion(QuestionMetadataMixin):
    id: UUID
    group: QuestionDetailConsolidationQuestionGroup | None = None
    question: str
    comment: str | None = None
    cq_catalogue_identifier: str | None = None
    sparql_query: str | None = None
    aggregated_rating: int = 0
    author: QuestionUser


class QuestionDetailConsolidation(BaseModel):
    id: UUID
    target_question: QuestionDetailConsolidationQuestion | None = None
    no_source_questions: int = 0
    project: QuestionProject
    engineer: QuestionUser
    source_questions: list[QuestionDetailConsolidationQuestion] = Field(default_factory=list)


class QuestionDetail(QuestionMetadataMixin):
    id: UUID
    question: str
    comment: str | None = None
    cq_catalogue_identifier: str | None = None
    sparql_query: str | None = None
    group_id: UUID
    version_number: int
    ratings: list[QuestionRating] = Field(default_factory=list)
    aggregated_rating: int = 0
    author: QuestionUser
    editor: QuestionUser
    group: QuestionGroup
    topic: QuestionTopic | None = None
    comments: list[QuestionComment] = Field(default_factory=list)
    no_consolidations: int = 0
    consolidations: list[QuestionDetailConsolidation] = Field(default_factory=list)
    versions: list[QuestionVersion] = Field(default_factory=list)
    annotations: list[QuestionAnnotation] = Field(default_factory=list)


class QuestionDetailDTO(PydanticDTO[QuestionDetail]):
    config = DTOConfig(rename_strategy="camel", max_nested_depth=3)


class QuestionCreate(QuestionMetadataMixin):
    question: str
    comment: str | None = None
    sparql_query: str | None = None
    annotations: list[AnnotationDTO] = []


class QuestionCreateDTO(PydanticDTO[QuestionCreate]):
    config = DTOConfig(rename_strategy="camel")


class QuestionUpdate(QuestionMetadataMixin):
    question: str | None = None
    comment: str | None = None
    sparql_query: str | None = None


class QuestionUpdateDTO(PydanticDTO[QuestionUpdate]):
    config = DTOConfig(rename_strategy="camel")


class QuestionUpdated(QuestionMetadataMixin):
    id: UUID
    question: str
    comment: str | None = None
    sparql_query: str | None = None
    author_id: UUID


class QuestionUpdatedDTO(PydanticDTO[QuestionUpdated]):
    config = DTOConfig(rename_strategy="camel")


class UnifiedQuestionEntryKind(str, Enum):
    QUESTION = "question"
    CONSOLIDATION_RESULT = "consolidation_result"


class UnifiedQuestionGroup(BaseModel):
    id: UUID
    name: str


class UnifiedQuestionAuthor(BaseModel):
    id: UUID
    email: str
    name: str


class UnifiedQuestionTopic(BaseModel):
    id: UUID
    identifier: str
    name: str


class UnifiedQuestionOverview(QuestionMetadataMixin):
    id: UUID
    question: str
    comment: str | None = None
    cq_catalogue_identifier: str | None = None
    sparql_query: str | None = None
    rating: int = 0
    no_consolidations: int = 0
    no_comments: int = 0
    group: UnifiedQuestionGroup | None = None
    topic: UnifiedQuestionTopic | None = None
    author: UnifiedQuestionAuthor | None = None
    unified_entry_kind: UnifiedQuestionEntryKind
    consolidation: QuestionConsolidationContext | None = None


class UnifiedQuestionOverviewDTO(PydanticDTO[UnifiedQuestionOverview]):
    config = DTOConfig(rename_strategy="camel")


class QuestionCatalogueResolution(BaseModel):
    id: UUID
    group_id: UUID
    cq_catalogue_identifier: str


class QuestionCatalogueResolutionDTO(PydanticDTO[QuestionCatalogueResolution]):
    config = DTOConfig(rename_strategy="camel")
