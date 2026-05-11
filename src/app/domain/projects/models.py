from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from domain.accounts.models import User
    from domain.consolidations.models import Consolidation
    from domain.groups.models import Group
    from domain.terms.models import Term
    from domain.topics.models import Topic

ProjectManagers = Table(
    "project_managers",
    UUIDAuditBase.metadata,
    Column[UUID]("user_id", ForeignKey("user.id"), primary_key=True),
    Column[UUID]("project_id", ForeignKey("project.id"), primary_key=True),
)


ProjectEngineers = Table(
    "project_engineers",
    UUIDAuditBase.metadata,
    Column[UUID]("user_id", ForeignKey("user.id"), primary_key=True),
    Column[UUID]("project_id", ForeignKey("project.id"), primary_key=True),
)


class Project(UUIDAuditBase):
    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)

    managers: Mapped[list[User]] = relationship(secondary="project_managers", back_populates="managed_projects")
    engineers: Mapped[list[User]] = relationship(secondary="project_engineers", back_populates="engineered_projects")
    groups: Mapped[list[Group]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    consolidations: Mapped[list[Consolidation]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    terms: Mapped[list[Term]] = relationship(back_populates="project")
    topics: Mapped[list[Topic]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    @hybrid_property
    def no_managers(self) -> int:
        return len(self.managers)

    @hybrid_property
    def no_engineers(self) -> int:
        return len(self.engineers)

    @hybrid_property
    def no_groups(self) -> int:
        return len(self.groups)

    @hybrid_property
    def no_consolidations(self) -> int:
        return len(self.consolidations)

    @hybrid_property
    def total_members(self) -> int:
        return sum([group.no_members for group in self.groups])
