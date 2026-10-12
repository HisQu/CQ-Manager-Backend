from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from litestar.contrib.sqlalchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from domain.accounts.models import User


class QuestionEventType(str, Enum):
    CREATED = "created"
    REVISED = "revised"
    TAG_ADDED = "tag_added"
    TAG_REMOVED = "tag_removed"
    CATALOGUE_ASSIGNED = "catalogue_assigned"
    DELETED = "deleted"


class QuestionEvent(UUIDAuditBase):
    """An append-only provenance entry of a `Question`, `created_at` is when it happened.

    Every event records the revision (`version_number`) the `Question` had right after it, so the tags and
    catalogue placement of any revision can be reconstructed by replaying the events. Tag names and catalogue
    identifiers are snapshotted because tags can be renamed or deleted later on.
    """

    question_id: Mapped[UUID] = mapped_column(ForeignKey("question.id"), index=True)
    # `None` for events imported from data that predates the history.
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("user.id"), default=None)
    event_type: Mapped[str] = mapped_column()
    version_number: Mapped[int] = mapped_column()
    tag_id: Mapped[UUID | None] = mapped_column(ForeignKey("tag.id", ondelete="SET NULL"), default=None)
    tag_name: Mapped[str | None] = mapped_column(default=None)
    topic_id: Mapped[UUID | None] = mapped_column(ForeignKey("topic.id", ondelete="SET NULL"), default=None)
    catalogue_identifier: Mapped[str | None] = mapped_column(default=None)

    actor: Mapped[User | None] = relationship()
