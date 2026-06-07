from typing import Annotated, Sequence, TypeVar
from uuid import UUID

from domain.projects.guards import ontology_engineer_guard
from domain.consolidations.models import Consolidation
from domain.questions.dtos import QuestionOverview, QuestionOverviewDTO
from domain.questions.models import Question
from domain.questions.services import QuestionService
from litestar import Controller, delete, get, post, put
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .dtos import (
    TopicCreate,
    TopicCreateDTO,
    TopicDTO,
    TopicDetail,
    TopicDetailDTO,
    TopicQuestion,
    TopicUpdate,
    TopicUpdateDTO,
)
from .models import Topic
from .services import TopicService

T = TypeVar("T")
JsonEncoded = Annotated[T, Body(media_type=RequestEncodingType.JSON)]


class TopicController(Controller):
    path = "/topics"
    tags = ["Topics"]

    detail_options = [selectinload(Topic.questions)]
    question_options = [
        selectinload(Question.author),
        selectinload(Question.editor),
        selectinload(Question.ratings),
        selectinload(Question.comments),
        selectinload(Question.consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.target_consolidations).options(selectinload(Consolidation.questions)),
        selectinload(Question.group),
        selectinload(Question.topic),
    ]

    @post(
        "/{project_id:uuid}",
        dto=TopicCreateDTO,
        return_dto=TopicDTO,
        status_code=HTTP_201_CREATED,
        guards=[ontology_engineer_guard],
    )
    async def create_topic(self, session: AsyncSession, project_id: UUID, data: JsonEncoded[TopicCreate]) -> Topic:
        """Creates a `Topic` within a `Project`."""
        return await TopicService.create_topic(session, project_id, data.name, data.identifier)

    @get("/{project_id:uuid}", return_dto=TopicDTO, status_code=HTTP_200_OK)
    async def list_topics(self, session: AsyncSession, project_id: UUID) -> Sequence[Topic]:
        """Lists all `Topic`s for a `Project`, ordered by topic identifier."""
        return await TopicService.list_topics(session, project_id)

    @get(
        "/{project_id:uuid}/{topic_id:uuid}",
        return_dto=TopicDetailDTO,
        status_code=HTTP_200_OK,
    )
    async def get_topic(self, session: AsyncSession, project_id: UUID, topic_id: UUID) -> TopicDetail:
        """Gets a `Topic` and its linked `Question`s."""
        topic = await TopicService.get_topic(session, project_id, topic_id, self.detail_options)
        return TopicDetail(
            id=topic.id,
            identifier=topic.identifier,
            name=topic.name,
            project_id=topic.project_id,
            questions=[
                TopicQuestion(
                    id=question.id,
                    question=question.question,
                    type=question.type,
                )
                for question in topic.questions
            ],
        )

    @put(
        "/{project_id:uuid}/{topic_id:uuid}",
        dto=TopicUpdateDTO,
        return_dto=TopicDTO,
        status_code=HTTP_200_OK,
        guards=[ontology_engineer_guard],
    )
    async def update_topic(
        self,
        session: AsyncSession,
        project_id: UUID,
        topic_id: UUID,
        data: JsonEncoded[TopicUpdate],
    ) -> Topic:
        """Updates a `Topic` name. Topic identifiers are immutable."""
        return await TopicService.update_topic(session, project_id, topic_id, data.name)

    @post(
        "/{project_id:uuid}/{topic_id:uuid}/questions/{question_id:uuid}",
        return_dto=QuestionOverviewDTO,
        status_code=HTTP_200_OK,
        guards=[ontology_engineer_guard],
    )
    async def assign_question_topic(
        self,
        session: AsyncSession,
        project_id: UUID,
        topic_id: UUID,
        question_id: UUID,
    ) -> QuestionOverview:
        """Assigns a `Question` to a `Topic` if it does not already have one."""
        question = await TopicService.assign_question(
            session,
            project_id,
            topic_id,
            question_id,
            self.question_options,
        )
        return QuestionService.to_question_overview(question)

    @put(
        "/{project_id:uuid}/{topic_id:uuid}/questions/{question_id:uuid}",
        return_dto=QuestionOverviewDTO,
        status_code=HTTP_200_OK,
        guards=[ontology_engineer_guard],
    )
    async def change_question_topic(
        self,
        session: AsyncSession,
        project_id: UUID,
        topic_id: UUID,
        question_id: UUID,
    ) -> QuestionOverview:
        """Changes a `Question` topic assignment."""
        question = await TopicService.change_question_topic(
            session,
            project_id,
            topic_id,
            question_id,
            self.question_options,
        )
        return QuestionService.to_question_overview(question)

    @delete(
        "/{project_id:uuid}/questions/{question_id:uuid}",
        return_dto=QuestionOverviewDTO,
        status_code=HTTP_200_OK,
        guards=[ontology_engineer_guard],
    )
    async def remove_question_topic(
        self,
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
    ) -> QuestionOverview:
        """Removes a `Question` topic assignment."""
        question = await TopicService.remove_question_topic(
            session,
            project_id,
            question_id,
            self.question_options,
        )
        return QuestionService.to_question_overview(question)
