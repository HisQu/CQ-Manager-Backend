from uuid import UUID

from lib.dto import BaseModel, NonEmptyString
from litestar.contrib.sqlalchemy.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig
from pydantic import EmailStr

from .models import Group


class GroupDTO(SQLAlchemyDTO[Group]):
    config = SQLAlchemyDTOConfig(
        rename_strategy="camel",
        include={
            "id",
            "name",
            "no_members",
            "no_questions",
            "created_at",
            "updated_at",
            "project.id",
            "project.name",
            "project.description",
            "project.created_at",
            "project.updated_at",
        },
    )


class GroupDetailDTO(SQLAlchemyDTO[Group]):
    config = SQLAlchemyDTOConfig(
        rename_strategy="camel",
        max_nested_depth=2,
        include={
            "id",
            "name",
            "no_members",
            "no_questions",
            "created_at",
            "updated_at",
            "project.id",
            "project.name",
            "project.description",
            "project.created_at",
            "project.updated_at",
            "members.0.id",
            "members.0.email",
            "members.0.name",
            "questions.0.question",
            "questions.0.sparql_query",
            "questions.0.aggregated_rating",
            "questions.0.author.id",
            "questions.0.author.email",
            "questions.0.author.name",
        },
    )


class GroupCreateDTO(BaseModel):
    name: NonEmptyString
    members: list[EmailStr] | None = None


class GroupUsersAddDTO(BaseModel):
    emails: list[EmailStr]


class GroupUsersRemoveDTO(BaseModel):
    ids: list[UUID]


class GroupUpdateDTO(BaseModel):
    emails: list[EmailStr]
