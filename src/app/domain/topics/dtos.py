from uuid import UUID

from lib.dto import BaseModel, NonEmptyString
from litestar.contrib.pydantic import PydanticDTO
from litestar.contrib.sqlalchemy.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig
from litestar.dto import DTOConfig
from pydantic import Field, field_validator

from .models import Topic
from .services import normalize_topic_identifier


class TopicQuestion(BaseModel):
    id: UUID
    question: str
    type: str | None = None


class TopicCreate(BaseModel):
    model_config = {"from_attributes": True, "extra": "forbid"}

    name: NonEmptyString
    identifier: str | None = None

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str | None) -> str | None:
        return normalize_topic_identifier(value)


class TopicUpdate(BaseModel):
    model_config = {"from_attributes": True, "extra": "forbid"}

    name: NonEmptyString


class TopicCreateDTO(PydanticDTO[TopicCreate]):
    config = DTOConfig(rename_strategy="camel")


class TopicUpdateDTO(PydanticDTO[TopicUpdate]):
    config = DTOConfig(rename_strategy="camel")


class TopicDTO(SQLAlchemyDTO[Topic]):
    config = SQLAlchemyDTOConfig(
        include={"id", "identifier", "name", "project_id"},
        rename_strategy="camel",
    )


class TopicDetail(BaseModel):
    id: UUID
    identifier: str
    name: str
    project_id: UUID
    questions: list[TopicQuestion] = Field(default_factory=list)


class TopicDetailDTO(PydanticDTO[TopicDetail]):
    config = DTOConfig(rename_strategy="camel")
