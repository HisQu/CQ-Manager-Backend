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
            "name",
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


class ConsolidationCreate(BaseModel):
    name: str
    ids: list[UUID] | None = None


class ConsolidationCreateDTO(PydanticDTO[ConsolidationCreate]):
    config = DTOConfig(rename_strategy="camel")


class ConsolidationUpdate(BaseModel):
    name: str | None


class ConsolidationUpdateDTO(PydanticDTO[ConsolidationUpdate]):
    config = DTOConfig(rename_strategy="camel")


class MoveQuestion(BaseModel):
    ids: list[UUID]


class MoveQuestionDTO(PydanticDTO[MoveQuestion]):
    config = DTOConfig(rename_strategy="camel")
