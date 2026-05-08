from datetime import datetime
from uuid import UUID

from lib.dto import BaseModel, NonEmptyString
from litestar.contrib.pydantic.pydantic_dto_factory import PydanticDTO
from litestar.dto import DTOConfig
from pydantic import EmailStr, Field


class ProjectUser(BaseModel):
    id: UUID
    email: EmailStr
    name: str


class ProjectGroup(BaseModel):
    id: UUID
    name: str
    comments: str | None = None
    no_members: int = 0
    no_questions: int = 0
    created_at: datetime
    updated_at: datetime
    members: list[ProjectUser] = Field(default_factory=list)


class ProjectConsolidation(BaseModel):
    id: UUID
    no_questions: int = 0
    engineer: ProjectUser


class ProjectRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    no_managers: int = 0
    no_engineers: int = 0
    no_groups: int = 0
    no_consolidations: int = 0
    total_members: int = 0


class ProjectDetail(ProjectRead):
    created_at: datetime
    updated_at: datetime
    managers: list[ProjectUser] = Field(default_factory=list)
    engineers: list[ProjectUser] = Field(default_factory=list)
    groups: list[ProjectGroup] = Field(default_factory=list)
    consolidations: list[ProjectConsolidation] = Field(default_factory=list)


class ProjectDTO(PydanticDTO[ProjectRead]):
    config = DTOConfig(rename_strategy="camel")


class ProjectDetailDTO(PydanticDTO[ProjectDetail]):
    config = DTOConfig(rename_strategy="camel")


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
