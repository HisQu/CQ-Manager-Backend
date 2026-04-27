from uuid import UUID

from lib.dto import BaseModel, NonEmptyString
from litestar.contrib.pydantic import PydanticDTO
from litestar.contrib.sqlalchemy.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig
from litestar.dto import DTOConfig

from .models import Passage, Term


class TermDTO(SQLAlchemyDTO[Term]):
    config = SQLAlchemyDTOConfig(
        include={"id", "project_id", "content"},
        rename_strategy="camel",
    )


class PassageDTO(SQLAlchemyDTO[Passage]):
    config = SQLAlchemyDTOConfig(
        include={"id", "term_id", "content"},
        rename_strategy="camel",
    )


class AnnotationDTO(BaseModel):
    passage: NonEmptyString
    term: NonEmptyString


class AnnotationAddDTO(BaseModel):
    annotations: list[AnnotationDTO]


class AnnotationRemove(BaseModel):
    term_ids: list[UUID] | None = None
    passage_ids: list[UUID] | None = None


class AnnotationRemoveDTO(PydanticDTO[AnnotationRemove]):
    config = DTOConfig(rename_strategy="camel")


class TermUpdate(BaseModel):
    content: NonEmptyString


class TermUpdateDTO(PydanticDTO[TermUpdate]):
    config = DTOConfig(rename_strategy="camel")


class AnnotationUpdate(BaseModel):
    term: NonEmptyString
    passage: NonEmptyString


class AnnotationUpdateDTO(PydanticDTO[AnnotationUpdate]):
    config = DTOConfig(rename_strategy="camel")
