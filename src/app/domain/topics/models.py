from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from domain.projects.models import Project
    from domain.questions.models import Question


class Topic(UUIDAuditBase):
    __table_args__ = (UniqueConstraint("identifier", "project_id"),)

    identifier: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))

    project: Mapped[Project] = relationship(back_populates="topics")
    questions: Mapped[list[Question]] = relationship(back_populates="topic")
