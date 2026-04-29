from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from domain.accounts.models import User
    from domain.comments.models import Comment
    from domain.consolidations.models import Consolidation
    from domain.groups.models import Group
    from domain.ratings.models import Rating
    from domain.versions.models import Version
    from domain.terms.models import Passage


class Question(UUIDAuditBase):
    version_number: Mapped[int]
    question: Mapped[str]
    sparql_query: Mapped[str | None]
    author_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    editor_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"))
    group_id: Mapped[UUID] = mapped_column(ForeignKey("group.id"))

    author: Mapped[User] = relationship(foreign_keys=[author_id], back_populates="questions")
    editor: Mapped[User] = relationship(foreign_keys=[editor_id], back_populates="edited_questions")
    group: Mapped[Group] = relationship(back_populates="questions")
    ratings: Mapped[list[Rating]] = relationship(back_populates="question", cascade="all, delete-orphan")
    comments: Mapped[list[Comment]] = relationship(back_populates="question", cascade="all, delete-orphan")
    consolidations: Mapped[list[Consolidation]] = relationship(
        secondary="consolidated_questions", back_populates="questions"
    )
    versions: Mapped[list[Version]] = relationship(back_populates="question", cascade="all, delete-orphan")
    annotations: Mapped[list[Passage]] = relationship(secondary="annotated_passages", back_populates="questions")

    @hybrid_property
    def no_consolidations(self) -> int:
        return len(self.consolidations)

    @hybrid_property
    def aggregated_rating(self) -> int:
        return sum(map(lambda r: r.rating, self.ratings)) // len(self.ratings) if len(self.ratings) > 0 else 0
