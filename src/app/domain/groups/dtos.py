from datetime import datetime
from uuid import UUID

from lib.dto import BaseModel, NonEmptyString
from litestar.contrib.pydantic.pydantic_dto_factory import PydanticDTO
from litestar.dto import DTOConfig
from pydantic import EmailStr, Field


class GroupProject(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class GroupUser(BaseModel):
    id: UUID
    email: EmailStr
    name: str


class GroupQuestion(BaseModel):
    question: str
    type: str | None = None
    sparql_query: str | None = None
    aggregated_rating: int = 0
    author: GroupUser


class GroupRead(BaseModel):
    id: UUID
    name: str
    comment: str | None = None
    no_members: int = 0
    no_questions: int = 0
    created_at: datetime
    updated_at: datetime
    project: GroupProject | None = None


class GroupDetail(GroupRead):
    members: list[GroupUser] = Field(default_factory=list)
    questions: list[GroupQuestion] = Field(default_factory=list)


class GroupDTO(PydanticDTO[GroupRead]):
    config = DTOConfig(rename_strategy="camel")


class GroupDetailDTO(PydanticDTO[GroupDetail]):
    config = DTOConfig(rename_strategy="camel")


class GroupCreateDTO(BaseModel):
    name: NonEmptyString
    comment: str | None = None
    members: list[EmailStr] | None = None


class GroupUsersAddDTO(BaseModel):
    emails: list[EmailStr]


class GroupUsersRemoveDTO(BaseModel):
    ids: list[UUID]


class GroupUpdateDTO(BaseModel):
    name: NonEmptyString | None = None
    comment: str | None = None
