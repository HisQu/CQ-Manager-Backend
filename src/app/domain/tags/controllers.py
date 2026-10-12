from typing import Annotated, Any, Sequence, TypeVar
from uuid import UUID

from domain.accounts.models import User
from domain.comments.models import Comment
from domain.comments.services import CommentsService
from domain.consolidations.models import Consolidation
from domain.projects.guards import project_curator_guard, project_participant_guard
from domain.projects.middleware import UserProjectPermissionsMiddleware
from domain.questions.dtos import QuestionOverview, QuestionOverviewDTO
from domain.questions.models import Question
from domain.questions.services import QuestionService
from litestar import Controller, Request, delete, get, post, put
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .dtos import QuestionTagsUpdate, QuestionTagsUpdateDTO, TagRead, TagReadDTO, TagWrite, TagWriteDTO
from .models import Tag
from .services import TagService

T = TypeVar("T")
JsonEncoded = Annotated[T, Body(media_type=RequestEncodingType.JSON)]


def to_tag_read(tag: Tag, no_questions: int) -> TagRead:
    return TagRead(id=tag.id, name=tag.name, project_id=tag.project_id, no_questions=no_questions)


class TagController(Controller):
    path = "/tags"
    tags = ["Tags"]
    middleware = [UserProjectPermissionsMiddleware]

    question_options = [
        selectinload(Question.author),
        selectinload(Question.ratings),
        selectinload(Question.comments).options(selectinload(Comment.author)),
        selectinload(Question.consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.target_consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.group),
        selectinload(Question.topic),
        selectinload(Question.tags),
    ]

    @get("/{project_id:uuid}", return_dto=TagReadDTO, status_code=HTTP_200_OK)
    async def list_tags(self, session: AsyncSession, project_id: UUID) -> Sequence[TagRead]:
        """Lists all `Tag`s of a `Project` with the number of tagged `Question`s, ordered by name."""
        return [to_tag_read(tag, count) for tag, count in await TagService.list_tags(session, project_id)]

    @post(
        "/{project_id:uuid}",
        dto=TagWriteDTO,
        return_dto=TagReadDTO,
        status_code=HTTP_201_CREATED,
        guards=[project_participant_guard],
    )
    async def create_tag(self, session: AsyncSession, project_id: UUID, data: JsonEncoded[TagWrite]) -> TagRead:
        """Creates a `Tag` within a `Project`. Tag names are unique per project (case-insensitive)."""
        tag = await TagService.create_tag(session, project_id, data.name)
        return to_tag_read(tag, 0)

    @put(
        "/{project_id:uuid}/{tag_id:uuid}",
        dto=TagWriteDTO,
        return_dto=TagReadDTO,
        status_code=HTTP_200_OK,
        guards=[project_curator_guard],
    )
    async def rename_tag(
        self,
        session: AsyncSession,
        project_id: UUID,
        tag_id: UUID,
        data: JsonEncoded[TagWrite],
    ) -> TagRead:
        """Renames a `Tag`."""
        await TagService.rename_tag(session, project_id, tag_id, data.name)
        return to_tag_read(*await TagService.get_tag_with_count(session, project_id, tag_id))

    @delete(
        "/{project_id:uuid}/{tag_id:uuid}",
        status_code=HTTP_204_NO_CONTENT,
        guards=[project_curator_guard],
    )
    async def delete_tag(
        self,
        session: AsyncSession,
        project_id: UUID,
        tag_id: UUID,
        request: Request[User, Any, Any],
    ) -> None:
        """Deletes a `Tag` and removes it from all `Question`s."""
        await TagService.delete_tag(session, project_id, tag_id, request.user.id)

    @put(
        "/{project_id:uuid}/questions/{question_id:uuid}",
        dto=QuestionTagsUpdateDTO,
        return_dto=QuestionOverviewDTO,
        status_code=HTTP_200_OK,
        guards=[project_participant_guard],
    )
    async def set_question_tags(
        self,
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        data: JsonEncoded[QuestionTagsUpdate],
        request: Request[User, Any, Any],
    ) -> QuestionOverview:
        """Replaces the `Tag`s of a `Question`. An empty list removes all tags."""
        question = await TagService.set_question_tags(
            session,
            project_id,
            question_id,
            data.tag_ids,
            request.user.id,
            self.question_options,
        )
        reader = await CommentsService.get_reader(session, request.user.id)
        return QuestionService.to_question_overview(question, reader)
