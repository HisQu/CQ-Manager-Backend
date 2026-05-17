from uuid import UUID

from lib.dto import BaseModel
from domain.questions.dtos import QuestionMetadataMixin
from litestar.contrib.pydantic.pydantic_dto_factory import PydanticDTO
from litestar.dto import DTOConfig
from pydantic import Field, model_validator


class ConsolidationUser(BaseModel):
    id: UUID
    email: str
    name: str


class ConsolidationProject(BaseModel):
    id: UUID
    name: str


class ConsolidationQuestionGroup(BaseModel):
    id: UUID
    name: str


class ConsolidationQuestion(QuestionMetadataMixin):
    id: UUID
    group: ConsolidationQuestionGroup | None = None
    question: str
    comment: str | None = None
    sparql_query: str | None = None
    aggregated_rating: int = 0
    author: ConsolidationUser


class ConsolidationRead(BaseModel):
    id: UUID
    target_question: ConsolidationQuestion | None = Field(
        default=None,
        validation_alias="result_question",
    )
    no_source_questions: int = Field(default=0, validation_alias="no_questions")
    engineer: ConsolidationUser
    source_questions: list[ConsolidationQuestion] = Field(validation_alias="questions")
    project: ConsolidationProject


class ConsolidationDTO(PydanticDTO[ConsolidationRead]):
    config = DTOConfig(rename_strategy="camel")


class ConsolidationTargetQuestionCreate(QuestionMetadataMixin):
    id: UUID | None = None
    question: str | None = None
    comment: str | None = None
    group_id: UUID | None = None
    sparql_query: str | None = None

    @model_validator(mode="after")
    def validate_payload_shape(self) -> "ConsolidationTargetQuestionCreate":
        has_reference = self.id is not None
        has_create = self.question is not None or self.group_id is not None
        if has_reference == has_create:
            raise ValueError("Provide either id or question/groupId for targetQuestion.")
        if has_create and self.question is None:
            raise ValueError("question is required for new targetQuestion.")
        return self


class ConsolidationTargetQuestionReference(BaseModel):
    id: UUID


class ConsolidationCreate(BaseModel):
    target_question: ConsolidationTargetQuestionCreate
    source_question_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def validate_target_question_source(self) -> "ConsolidationCreate":
        has_new_target = self.target_question.question is not None
        has_existing_target = self.target_question.id is not None
        if has_new_target == has_existing_target:
            raise ValueError("Provide either an id or question/groupId for targetQuestion.")
        return self


class ConsolidationCreateDTO(PydanticDTO[ConsolidationCreate]):
    config = DTOConfig(rename_strategy="camel")


class ConsolidationUpdate(BaseModel):
    target_question: ConsolidationTargetQuestionReference | None = None


class ConsolidationUpdateDTO(PydanticDTO[ConsolidationUpdate]):
    config = DTOConfig(rename_strategy="camel")


class MoveQuestion(BaseModel):
    source_question_ids: list[UUID]


class MoveQuestionDTO(PydanticDTO[MoveQuestion]):
    config = DTOConfig(rename_strategy="camel")
