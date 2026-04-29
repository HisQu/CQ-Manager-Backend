from uuid import UUID

from lib.dto import BaseModel
from litestar.contrib.pydantic.pydantic_dto_factory import PydanticDTO
from litestar.dto import DTOConfig
from pydantic import model_validator


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


class ConsolidationQuestion(BaseModel):
    id: UUID
    group: ConsolidationQuestionGroup
    question: str
    sparql_query: str | None = None
    aggregated_rating: int = 0
    author: ConsolidationUser


class ConsolidationRead(BaseModel):
    id: UUID
    result_question_id: UUID | None = None
    result_question: ConsolidationQuestion | None = None
    no_questions: int = 0
    engineer: ConsolidationUser
    questions: list[ConsolidationQuestion]
    project: ConsolidationProject


class ConsolidationDTO(PydanticDTO[ConsolidationRead]):
    config = DTOConfig(rename_strategy="camel", max_nested_depth=2)


class ConsolidationResultQuestionCreate(BaseModel):
    id: UUID | None = None
    question: str | None = None
    group_id: UUID | None = None
    sparql_query: str | None = None

    @model_validator(mode="after")
    def validate_payload_shape(self) -> "ConsolidationResultQuestionCreate":
        has_reference = self.id is not None
        has_create = self.question is not None or self.group_id is not None
        if has_reference == has_create:
            raise ValueError(
                "Provide either id or question/groupId for resultQuestion."
            )
        if has_create and self.question is None:
            raise ValueError("question is required for new resultQuestion.")
        return self


class ConsolidationCreate(BaseModel):
    result_question: ConsolidationResultQuestionCreate | None = None
    result_question_id: UUID | None = None
    ids: list[UUID] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_existing_result_question_reference(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        result_question = data.get("result_question", data.get("resultQuestion"))
        if isinstance(result_question, dict):
            question_id = result_question.get("id")
            has_create_fields = (
                result_question.get("question") is not None
                or result_question.get("group_id") is not None
                or result_question.get("groupId") is not None
            )
            if question_id is not None and not has_create_fields:
                data = dict(data)
                data["result_question_id"] = data.get(
                    "result_question_id",
                    data.get("resultQuestionId", question_id),
                )
                data.pop("result_question", None)
                data.pop("resultQuestion", None)

        return data

    @model_validator(mode="after")
    def validate_result_question_source(self) -> "ConsolidationCreate":
        if (
            self.result_question is not None
            and self.result_question.id is not None
            and self.result_question_id is None
        ):
            self.result_question_id = self.result_question.id

        has_new_result = (
            self.result_question is not None
            and self.result_question.question is not None
        )
        has_existing_result = self.result_question_id is not None
        if has_new_result == has_existing_result:
            raise ValueError(
                "Provide exactly one of resultQuestion or resultQuestionId."
            )
        return self


class ConsolidationCreateDTO(PydanticDTO[ConsolidationCreate]):
    config = DTOConfig(rename_strategy="camel")


class ConsolidationUpdate(BaseModel):
    result_question_id: UUID | None = None


class ConsolidationUpdateDTO(PydanticDTO[ConsolidationUpdate]):
    config = DTOConfig(rename_strategy="camel")


class MoveQuestion(BaseModel):
    ids: list[UUID]


class MoveQuestionDTO(PydanticDTO[MoveQuestion]):
    config = DTOConfig(rename_strategy="camel")
