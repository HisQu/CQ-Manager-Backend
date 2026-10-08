from datetime import datetime
from uuid import UUID

from domain.questions.dtos import QuestionUser
from lib.dto import BaseModel
from litestar.contrib.pydantic import PydanticDTO
from litestar.dto import DTOConfig

from .models import QuestionEventType


class QuestionEventRead(BaseModel):
    id: UUID
    event_type: QuestionEventType
    created_at: datetime
    version_number: int
    actor: QuestionUser | None = None
    tag_id: UUID | None = None
    tag_name: str | None = None
    topic_id: UUID | None = None
    catalogue_identifier: str | None = None


class QuestionEventReadDTO(PydanticDTO[QuestionEventRead]):
    config = DTOConfig(rename_strategy="camel", max_nested_depth=1)
