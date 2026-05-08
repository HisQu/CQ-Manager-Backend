from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from domain.accounts.models import User
    from domain.projects.models import Project
    from domain.questions.models import Question



GroupMembers = Table(
    "group_members",
    UUIDAuditBase.metadata,
    Column[UUID]("user_id", ForeignKey("user.id"), primary_key=True),
    Column[UUID]("group_id", ForeignKey("group.id"), primary_key=True),
)


class Group(UUIDAuditBase):
    name: Mapped[str] = mapped_column()
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))

    project: Mapped[Project] = relationship(back_populates="groups")
    members: Mapped[list[User]] = relationship(secondary="group_members", back_populates="joined_groups")
    questions: Mapped[list[Question]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )

    @hybrid_property
    def no_members(self) -> int:
        return len(self.members)

    @hybrid_property
    def no_questions(self) -> int:
        return len(self.questions)
