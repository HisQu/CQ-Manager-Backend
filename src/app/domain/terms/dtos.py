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
        include={"id", "annotation_version_id", "term_id", "content", "start", "end"},
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


class AnnotationSetSaveDTO(BaseModel):
    base_annotation_version_id: UUID | None = None
    annotations: list[AnnotationDTO]


class AnnotationSetSavePydanticDTO(PydanticDTO[AnnotationSetSaveDTO]):
    config = DTOConfig(rename_strategy="camel")


class AnnotationTermRead(BaseModel):
    id: UUID
    content: str
    definition: str | None = None
    concept_iri: str | None = None


class PassageRead(BaseModel):
    id: UUID
    content: str
    start: int
    end: int
    term: AnnotationTermRead


class AnnotationVersionRead(BaseModel):
    id: UUID
    question_version_id: UUID
    version_number: int
    retained_from_annotation_version_id: UUID | None = None
    editor_id: UUID
    annotations: list[PassageRead]


class AnnotationVersionReadDTO(PydanticDTO[AnnotationVersionRead]):
    config = DTOConfig(rename_strategy="camel")


class TermUpdate(BaseModel):
    content: NonEmptyString | None = None
    definition: NonEmptyString | None = None
    concept_iri: NonEmptyString | None = None


class TermCreate(BaseModel):
    content: NonEmptyString
    definition: NonEmptyString | None = None
    concept_iri: NonEmptyString | None = Field(default=None, alias="conceptIri")


class TermCreateDTO(PydanticDTO[TermCreate]):
    config = DTOConfig(rename_strategy="camel")


class TermUpdateDTO(PydanticDTO[TermUpdate]):
    config = DTOConfig(rename_strategy="camel")
