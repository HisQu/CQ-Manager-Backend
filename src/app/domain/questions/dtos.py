from enum import Enum
from typing import Literal, TypeAlias, get_args
from uuid import UUID

from lib.dto import BaseModel
from litestar.contrib.pydantic.pydantic_dto_factory import PydanticDTO
from litestar.contrib.sqlalchemy.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig
from litestar.dto import DTOConfig
from pydantic import Field, field_validator

from .models import Question
from domain.terms.dtos import AnnotationDTO


CQType: TypeAlias = Literal["SCQ", "VCQ", "FCQ", "RCQ", "aRCQ", "efRCQ", "drRCQ", "rpRCQ", "MpCQ"]
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


class QuestionOverviewDTO(SQLAlchemyDTO[Question]):
    config = SQLAlchemyDTOConfig(
        include={
            "id",
            "group.id",
            "group.name",
            "question",
            "comment",
            "reference",
            "anchor",
            "example_answer",
            "type",
            "sparql_query",
            "rating",
            "author.id",
            "author.email",
            "author.name",
            "no_consolidations",
        },
        rename_strategy="camel",
    )


class QuestionDetailDTO(SQLAlchemyDTO[Question]):
    config = SQLAlchemyDTOConfig(
        max_nested_depth=3,
        include={
            "id",
            "question",
            "comment",
            "reference",
            "anchor",
            "example_answer",
            "type",
            "sparql_query",
            "group_id",
            "version_number",
            "ratings.0.rating",
            "ratings.0.author.id",
            "ratings.0.author.email",
            "ratings.0.author.name",
            "aggregated_rating",
            "author.id",
            "author.email",
            "author.name",
            "editor.id",
            "editor.email",
            "editor.name",
            "group.id",
            "group.name",
            "group.project.id",
            "group.project.name",
            "comments.0.author.id",
            "comments.0.author.email",
            "comments.0.author.name",
            "comments.0.comment",
            "comments.0.created_at",
            "no_consolidations",
            "consolidations.0.id",
            "consolidations.0.no_questions",
            "consolidations.0.project.id",
            "consolidations.0.project.name",
            "consolidations.0.engineer.id",
            "consolidations.0.engineer.email",
            "consolidations.0.engineer.name",
            "consolidations.0.questions.0.id",
            "consolidations.0.questions.0.group_id",
            "consolidations.0.questions.0.question",
            "consolidations.0.questions.0.comment",
            "consolidations.0.questions.0.reference",
            "consolidations.0.questions.0.anchor",
            "consolidations.0.questions.0.example_answer",
            "consolidations.0.questions.0.type",
            "consolidations.0.questions.0.sparql_query",
            "consolidations.0.questions.0.author.id",
            "consolidations.0.questions.0.author.email",
            "consolidations.0.questions.0.author.name",
            "versions.0.question_string",
            "versions.0.version_number",
            "versions.0.editor.id",
            "versions.0.editor.email",
            "versions.0.editor.name",
            "annotations.0.id",
            "annotations.0.content",
            "annotations.0.term.id",
            "annotations.0.term.content",

        },
        rename_strategy="camel",
    )


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


class UnifiedQuestionOverview(QuestionMetadataMixin):
    id: UUID
    question: str
    comment: str | None = None
    sparql_query: str | None = None
    rating: int = 0
    no_consolidations: int = 0
    group: UnifiedQuestionGroup | None = None
    author: UnifiedQuestionAuthor | None = None
    unified_entry_kind: UnifiedQuestionEntryKind
    consolidation_id: UUID | None = None
    consolidated_question_ids: list[UUID] = Field(default_factory=list)


class UnifiedQuestionOverviewDTO(PydanticDTO[UnifiedQuestionOverview]):
    config = DTOConfig(rename_strategy="camel")
