from typing import Annotated, Any, Sequence, TypeVar
from uuid import UUID
from lib.mails import MailService
from domain.accounts.authentication.services import EncryptionService
from domain.accounts.models import User
from domain.groups.models import Group
from domain.projects.guards import project_manager_guard
from domain.projects.middleware import UserProjectPermissionsMiddleware
from domain.questions.models import Question
from litestar import Controller, delete, get, post, put
from litestar.connection.request import Request
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.params import Body
from litestar.status_codes import HTTP_404_NOT_FOUND
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from litestar.background_tasks import BackgroundTasks, BackgroundTask
from litestar import Response
from .dtos import (
    GroupCreateDTO,
    GroupDetail,
    GroupDetailDTO,
    GroupDTO,
    GroupRead,
    GroupUpdateDTO,
    GroupUsersAddDTO,
    GroupUsersRemoveDTO,
)
from .middleware import UserGroupPermissionsMiddleware
from .models import Group
from .services import GroupService

T = TypeVar("T")
JsonEncoded = Annotated[T, Body(media_type=RequestEncodingType.JSON)]


class GroupController(Controller):
    path = "/groups"
    tags = ["Groups"]
    middleware = [UserGroupPermissionsMiddleware, UserProjectPermissionsMiddleware]

    default_options = [
        selectinload(Group.members),
        selectinload(Group.project),
        selectinload(Group.questions).options(
            selectinload(Question.author),
            selectinload(Question.ratings),
            selectinload(Question.topic),
        ),
    ]

    @staticmethod
    def _to_response(group: Group) -> GroupRead:
        return GroupRead.model_validate(group)

    @staticmethod
    def _to_detail_response(group: Group) -> GroupDetail:
        return GroupDetail.model_validate(group)

    @staticmethod
    def _to_response_list(groups: Sequence[Group]) -> list[GroupRead]:
        return [GroupController._to_response(group) for group in groups]

    @get("/", return_dto=GroupDTO)
    async def get_groups_handler(self, session: AsyncSession) -> Sequence[GroupRead]:
        """Gets all `Group`s."""
        groups = await GroupService.get_groups(session, options=self.default_options)
        return self._to_response_list(groups)

    @get("/{project_id:uuid}", return_dto=GroupDTO)
    async def get_project_groups_handler(self, session: AsyncSession, project_id: UUID) -> Sequence[GroupRead]:
        """Gets all `Group`s. belonging to a given `Project`."""
        groups = await GroupService.get_groups(session, project_id, self.default_options)
        return self._to_response_list(groups)

    @get("/{project_id:uuid}/{group_id:uuid}", return_dto=GroupDetailDTO)
    async def get_group_handler(self, session: AsyncSession, group_id: UUID, project_id: UUID) -> GroupDetail:
        """Gets a single `Group` belonging to a given `Project`."""
        group = await GroupService.get_group(session, group_id, project_id, self.default_options)
        return self._to_detail_response(group)

    @get("/direct/{group_id:uuid}", summary="Gets a single Group by its UUID only", return_dto=GroupDetailDTO)
    async def get_direct_handler(self, session: AsyncSession, group_id: UUID) -> GroupDetail:
        """Gets a single `Group`."""
        group = await GroupService.get_group(session, group_id, None, self.default_options)
        return self._to_detail_response(group)

    @post("/{project_id:uuid}", return_dto=GroupDTO, guards=[project_manager_guard])
    async def create_group_handler(
        self,
        request: Request[User, Any, Any],
        session: AsyncSession,
        encryption: EncryptionService,
        data: JsonEncoded[GroupCreateDTO],
        project_id: UUID,
        mail_service: MailService,
    ) -> Response[GroupRead]:
        """Creates a `Group` under a given `Project`."""
        tasks: list[BackgroundTask] = []
        group, invite_task, message_task = await GroupService.create(
            session,
            encryption,
            request.user.id,
            data,
            project_id,
            self.default_options,
        )
        if invite_task:
            tasks.append(BackgroundTask(invite_task, mail_service))
        if message_task:
            tasks.append(BackgroundTask(message_task, mail_service))
        response_group = self._to_response(group)
        session.expunge_all()
        return Response(response_group, background=BackgroundTasks(tasks) if tasks else None)

    @put("/{project_id:uuid}/{group_id:uuid}", return_dto=GroupDTO)
    async def update_group_handler(
        self,
        session: AsyncSession,
        group_id: UUID,
        data: JsonEncoded[GroupUpdateDTO],
        project_id: UUID,
    ) -> GroupRead:
        """Updates a `Group` under a given `Project`."""
        group = await GroupService.update(session, group_id, project_id, data, self.default_options)
        return self._to_response(group)

    @delete("/{project_id:uuid}/{group_id:uuid}")
    async def delete_group_handler(self, session: AsyncSession, group_id: UUID, project_id: UUID) -> None:
        """Deletes a `Group` under a given `Project`."""
        if await GroupService.delete(session, group_id, project_id):
            return
        raise HTTPException(status_code=HTTP_404_NOT_FOUND)  # TODO: raise explicit exception

    @put("/{project_id:uuid}/{group_id:uuid}/members/add", return_dto=GroupDTO)
    async def add_members_handler(
        self,
        session: AsyncSession,
        encryption: EncryptionService,
        group_id: UUID,
        project_id: UUID,
        data: JsonEncoded[GroupUsersAddDTO],
        mail_service: MailService,
    ) -> Response[GroupRead]:
        """Adds members to a `Group` under a given `Project`, `User`s are created the do not exists yet."""
        tasks: list[BackgroundTask] = []
        group, invite_task, message_task = await GroupService.add_members(
            session,
            encryption,
            group_id,
            project_id,
            data,
            self.default_options,
        )
        if invite_task:
            tasks.append(BackgroundTask(invite_task, mail_service))
        if message_task:
            tasks.append(BackgroundTask(message_task, mail_service))
        response_group = self._to_response(group)
        session.expunge_all()
        return Response(response_group, background=BackgroundTasks(tasks) if tasks else None)

    @put("/{project_id:uuid}/{group_id:uuid}/members/remove", return_dto=GroupDTO)
    async def remove_members_handler(
        self,
        session: AsyncSession,
        group_id: UUID,
        project_id: UUID,
        data: JsonEncoded[GroupUsersRemoveDTO],
    ) -> GroupRead:
        """Removes members from a `Group` under a given `Project`."""
        group = await GroupService.remove_members(session, group_id, project_id, data, self.default_options)
        return self._to_response(group)

    @get("/my_groups", summary="Gets all Groups you are a member of", return_dto=GroupDTO)
    async def my_groups(self, request: Request[User, Any, Any], session: AsyncSession) -> Sequence[GroupRead]:
        """Gets all `Group`s you are a member of."""
        groups = await GroupService.my_groups(session, request.user.id, options=self.default_options)
        return self._to_response_list(groups)

    @get("/my_groups/{project_id:uuid}", summary="Gets all Groups you are a member of", return_dto=GroupDTO)
    async def my_groups_by_projects(
        self,
        request: Request[User, Any, Any],
        session: AsyncSession,
        project_id: UUID,
    ) -> Sequence[GroupRead]:
        """Gets all `Group`s you are a member of, filtered by a `Project`."""
        groups = await GroupService.my_groups(session, request.user.id, project_id, self.default_options)
        return self._to_response_list(groups)

    @post("/{group_id:uuid}/extend_members", return_dto=GroupDTO)
    async def extend_members_handler(
        self,
        session: AsyncSession,
        encryption: EncryptionService,
        group_id: UUID,
        data: JsonEncoded[GroupUsersAddDTO],
        mail_service: MailService,
    ) -> Response[GroupRead]:
        """Extends the list of members in a `Group`."""
        tasks: list[BackgroundTask] = []
        group, invite_task, message_task = await GroupService.add_members(
            session,
            encryption,
            group_id,
            None,
            data,
            self.default_options,
        )
        if invite_task:
            tasks.append(BackgroundTask(invite_task, mail_service))
        if message_task:
            tasks.append(BackgroundTask(message_task, mail_service))
        response_group = self._to_response(group)
        session.expunge_all()
        return Response(response_group, background=BackgroundTasks(tasks) if tasks else None)
