from uuid import UUID

from lib.dto import BaseModel, NonEmptyString
from litestar.contrib.sqlalchemy.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig
from pydantic import EmailStr

from .models import Project


class ProjectDTO(SQLAlchemyDTO[Project]):
    config = SQLAlchemyDTOConfig(
        rename_strategy="camel",
        include={
            "id",
            "name",
            "description",
            "no_managers",
            "no_engineers",
            "no_groups",
            "no_consolidations",
            "total_members",
        },
    )


class ProjectDetailDTO(SQLAlchemyDTO[Project]):
    config = SQLAlchemyDTOConfig(
        rename_strategy="camel",
        max_nested_depth=2,
        include={
            "id",
            "name",
            "description",
            "no_managers",
            "no_engineers",
            "no_groups",
            "no_consolidations",
            "total_members",
            "created_at",
            "updated_at",
            "managers.0.id",
            "managers.0.email",
            "managers.0.name",
            "engineers.0.id",
            "engineers.0.email",
            "engineers.0.name",
            "groups.0.id",
            "groups.0.name",
            "groups.0.no_members",
            "groups.0.no_questions",
            "groups.0.created_at",
            "groups.0.updated_at",
            "groups.0.members.0.id",
            "groups.0.members.0.email",
            "groups.0.members.0.name",
            "consolidations.0.id",
            "consolidations.0.no_questions",
            "consolidations.0.engineer.id",
            "consolidations.0.engineer.email",
            "consolidations.0.engineer.name",
        },
    )


class ProjectCreateDTO(BaseModel):
    name: NonEmptyString
    description: NonEmptyString | None = None
    managers: list[EmailStr] | None = None
    engineers: list[EmailStr] | None = None


class ProjectUsersAddDTO(BaseModel):
    emails: list[EmailStr]


class ProjectUsersRemoveDTO(BaseModel):
    ids: list[UUID]


class ProjectUpdateDTO(BaseModel):
    name: NonEmptyString | None
    description: NonEmptyString | None = None
