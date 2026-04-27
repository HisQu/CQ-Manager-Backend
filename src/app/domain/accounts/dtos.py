from uuid import UUID

from lib.dto import BaseModel
from pydantic import EmailStr


class UserGetDTO(BaseModel):
    email: EmailStr
    name: str
    is_system_admin: bool
    is_verified: bool


class UserRegisterDTO(BaseModel):
    email: EmailStr
    name: str
    password: str


class UserUpdateDTO(BaseModel):
    email: EmailStr | None = None
    name: str | None = None
    password: str | None = None
    is_system_admin: bool | None = None
    is_verified: bool | None = None


class UserChangePasswordDTO(BaseModel):
    current_password: str
    new_password: str


class UserLoginDTO(BaseModel):
    email: str
    password: str


class UserAccessDTO(UserGetDTO):
    token: str | None = None
