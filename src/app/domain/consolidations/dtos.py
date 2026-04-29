from uuid import UUID

from lib.dto import BaseModel
from litestar.contrib.pydantic.pydantic_dto_factory import PydanticDTO
from litestar.contrib.sqlalchemy.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig
from litestar.dto import DTOConfig

from .models import Consolidation


class ConsolidationDTO(SQLAlchemyDTO[Consolidation]):
    config = SQLAlchemyDTOConfig(
        rename_strategy="camel",
        max_nested_depth=3,
        include={
            "id",
            "result_question_id",
            "result_question.id",
            "result_question.group.id",
            "result_question.group.name",
            "result_question.question",
            "result_question.sparql_query",
            "result_question.aggregated_rating",
            "result_question.author.id",
            "result_question.author.email",
            "result_question.author.name",
            "no_questions."
            "engineer.id",
            "engineer.email",
            "engineer.name",
            "questions.0.id",
            "questions.0.group.id",
            "questions.0.group.name",
            "questions.0.question",
            "questions.0.sparql_query",
            "questions.0.aggregated_rating",
            "questions.0.author.id",
            "questions.0.author.email",
            "questions.0.author.name",
            "project.id",
            "project.name",
        },
    )


class ConsolidationResultQuestionCreate(BaseModel):
    question: str
    group_id: UUID
    sparql_query: str | None = None


class ConsolidationCreate(BaseModel):
    result_question: ConsolidationResultQuestionCreate
    ids: list[UUID] | None = None


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
