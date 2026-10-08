from uuid import UUID

from lib.dto import BaseModel
from litestar.contrib.pydantic import PydanticDTO
from litestar.dto import DTOConfig
from pydantic import Field, field_validator

from .services import normalize_tag_name


class TagWrite(BaseModel):
    model_config = {"from_attributes": True, "extra": "forbid"}

    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_tag_name(value)


class TagWriteDTO(PydanticDTO[TagWrite]):
    config = DTOConfig(rename_strategy="camel")


class TagRead(BaseModel):
    id: UUID
    name: str
    project_id: UUID
    no_questions: int = 0


class TagReadDTO(PydanticDTO[TagRead]):
    config = DTOConfig(rename_strategy="camel")


class QuestionTagsUpdate(BaseModel):
    model_config = {"from_attributes": True, "extra": "forbid"}

    tag_ids: list[UUID] = Field(default_factory=list)


class QuestionTagsUpdateDTO(PydanticDTO[QuestionTagsUpdate]):
    config = DTOConfig(rename_strategy="camel")
