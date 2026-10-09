from uuid import UUID

from lib.dto import BaseModel, NonEmptyString
from litestar.contrib.pydantic import PydanticDTO
from litestar.contrib.sqlalchemy.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig
from litestar.dto import DTOConfig
from pydantic import Field

from .models import Passage, Term


class TermDTO(SQLAlchemyDTO[Term]):
    config = SQLAlchemyDTOConfig(
        include={"id", "project_id", "content", "definition", "concept_iri"},
        rename_strategy="camel",
    )


class PassageDTO(SQLAlchemyDTO[Passage]):
    config = SQLAlchemyDTOConfig(
        include={"id", "question_id", "term_id", "content", "start", "end"},
        rename_strategy="camel",
    )


class AnnotationDTO(BaseModel):
    model_config = {"from_attributes": True, "populate_by_name": True}

    passage: NonEmptyString
    term: NonEmptyString
    definition: NonEmptyString | None = None
    concept_iri: NonEmptyString | None = Field(default=None, alias="conceptIri")
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)


class AnnotationAddDTO(BaseModel):
    annotations: list[AnnotationDTO]


class AnnotationRemove(BaseModel):
    passage_ids: list[UUID] | None = None


class AnnotationRemoveDTO(PydanticDTO[AnnotationRemove]):
    config = DTOConfig(rename_strategy="camel")


class TermUpdate(BaseModel):
    content: NonEmptyString | None = None
    definition: NonEmptyString | None = None
    concept_iri: NonEmptyString | None = None


class TermUpdateDTO(PydanticDTO[TermUpdate]):
    config = DTOConfig(rename_strategy="camel")


class AnnotationUpdate(BaseModel):
    term: NonEmptyString
    passage: NonEmptyString
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    definition: str | None = None
    concept_iri: str | None = Field(default=None, alias="conceptIri")


class AnnotationUpdateDTO(PydanticDTO[AnnotationUpdate]):
    config = DTOConfig(rename_strategy="camel")
