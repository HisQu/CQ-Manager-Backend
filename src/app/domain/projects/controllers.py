from typing import Annotated, Any, Sequence, TypeVar
from uuid import UUID

from domain.accounts.authentication.services import EncryptionService
from domain.accounts.models import User
from domain.consolidations.models import Consolidation
from domain.groups.models import Group
from domain.questions.models import Question
from litestar import Controller, delete, get, post, put
from litestar.connection.request import Request
from litestar.enums import RequestEncodingType
from litestar.exceptions import HTTPException
from litestar.params import Body
from litestar.status_codes import HTTP_404_NOT_FOUND
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from lib.mails import MailService
from .dtos import (
    ProjectCreateDTO,
    ProjectDetail,
    ProjectDetailDTO,
    ProjectDTO,
    ProjectRead,
    ProjectUpdateDTO,
    ProjectUsersAddDTO,
    ProjectUsersRemoveDTO,
)
from .middleware import UserProjectPermissionsMiddleware
from .models import Project
from .services import ProjectService
from litestar import Response
from litestar.background_tasks import BackgroundTasks, BackgroundTask


T = TypeVar("T")
JsonEncoded = Annotated[T, Body(media_type=RequestEncodingType.JSON)]


class ProjectController(Controller):
    path = "/projects"
    tags = ["Project"]
    middleware = [UserProjectPermissionsMiddleware]

    default_options = [
        selectinload(Project.managers),
        selectinload(Project.engineers),
        selectinload(Project.groups).options(
            selectinload(Group.members),
            selectinload(Group.questions),
        ),
        selectinload(Project.consolidations).options(
            selectinload(Consolidation.engineer),
            selectinload(Consolidation.questions).options(selectinload(Question.topic)),
        ),
    ]

    @staticmethod
    def _to_response(project: Project) -> ProjectRead:
        return ProjectRead.model_validate(project)

    @staticmethod
    def _to_detail_response(project: Project) -> ProjectDetail:
        return ProjectDetail.model_validate(project)

    @staticmethod
    def _to_response_list(projects: Sequence[Project]) -> list[ProjectRead]:
        return [ProjectController._to_response(project) for project in projects]

    @get("/", return_dto=ProjectDTO)
    async def get_projects_handler(self, session: AsyncSession) -> Sequence[ProjectRead]:
        projects = await ProjectService.get_projects(session, self.default_options)
        return self._to_response_list(projects)

    @get("/{project_id:uuid}", return_dto=ProjectDetailDTO)
    async def get_project_handler(self, session: AsyncSession, project_id: UUID) -> ProjectDetail:
        project = await ProjectService.get_project(session, project_id, self.default_options)
        return self._to_detail_response(project)

    @post("/", return_dto=ProjectDTO)
    async def create_project_handler(
        self,
        session: AsyncSession,
        encryption: EncryptionService,
        data: JsonEncoded[ProjectCreateDTO],
        mail_service: MailService,
    ) -> Response[ProjectRead]:
        tasks: list[BackgroundTask] = []
        project, invite_task1, invite_task2, manager_task, engineers_task = await ProjectService.create(
            session, encryption, data, self.default_options
        )
        if invite_task1:
            tasks.append(BackgroundTask(invite_task1, mail_service))
        if invite_task2:
            tasks.append(BackgroundTask(invite_task2, mail_service))
        if manager_task:
            tasks.append(BackgroundTask(manager_task, mail_service))
        if engineers_task:
            tasks.append(BackgroundTask(engineers_task, mail_service))
        response_project = self._to_response(project)
        session.expunge_all()
        return Response(response_project, background=BackgroundTasks(tasks))

    @put("/{project_id:uuid}", return_dto=ProjectDTO)
    async def update_project_handler(
        self,
        session: AsyncSession,
        project_id: UUID,
        data: JsonEncoded[ProjectUpdateDTO],
    ) -> ProjectRead:
        project = await ProjectService.update(session, project_id, data, self.default_options)
        return self._to_response(project)

    @delete("/{project_id:uuid}")
    async def delete_project_handler(self, session: AsyncSession, project_id: UUID) -> None:
        if await ProjectService.delete(session, project_id):
            return
        raise HTTPException(status_code=HTTP_404_NOT_FOUND)  # TODO: raise explicit exception

    @put("/{project_id:uuid}/managers/add", return_dto=ProjectDTO)
    async def add_managers_handler(
        self,
        session: AsyncSession,
        encryption: EncryptionService,
        project_id: UUID,
        data: JsonEncoded[ProjectUsersAddDTO],
        mail_service: MailService,
    ) -> Response[ProjectRead]:
        tasks: list[BackgroundTask] = []
        project, invite_task, manager_task = await ProjectService.add_managers(
            session, encryption, project_id, data, self.default_options
        )
        if invite_task:
            tasks.append(BackgroundTask(invite_task, mail_service))
        if manager_task:
            tasks.append(BackgroundTask(manager_task, mail_service))
        response_project = self._to_response(project)
        session.expunge_all()
        return Response(response_project, background=BackgroundTasks(tasks))

    @put("/{project_id:uuid}/managers/remove", return_dto=ProjectDTO)
    async def remove_managers_handler(
        self,
        session: AsyncSession,
        project_id: UUID,
        data: JsonEncoded[ProjectUsersRemoveDTO],
    ) -> ProjectRead:
        project = await ProjectService.remove_managers(session, project_id, data, self.default_options)
        return self._to_response(project)

    @put("/{project_id:uuid}/engineers/add", return_dto=ProjectDTO)
    async def add_engineers_handler(
        self,
        session: AsyncSession,
        encryption: EncryptionService,
        project_id: UUID,
        data: JsonEncoded[ProjectUsersAddDTO],
        mail_service: MailService,
    ) -> Response[ProjectRead]:
        tasks: list[BackgroundTask] = []
        project, invite_task, engineer_task = await ProjectService.add_engineers(session, encryption, project_id, data, self.default_options)
        if invite_task:
            tasks.append(BackgroundTask(invite_task, mail_service))
        if engineer_task:
            tasks.append(BackgroundTask(engineer_task, mail_service))
        response_project = self._to_response(project)
        session.expunge_all()
        return Response(response_project, background=BackgroundTasks(tasks))

    @put("/{project_id:uuid}/engineers/remove", return_dto=ProjectDTO)
    async def remove_engineers_handler(
        self,
        session: AsyncSession,
        project_id: UUID,
        data: JsonEncoded[ProjectUsersRemoveDTO],
    ) -> ProjectRead:
        project = await ProjectService.remove_engineers(session, project_id, data, self.default_options)
        return self._to_response(project)

    @get("/my_projects", summary="Gets all Projects you are a part of", return_dto=ProjectDTO)
    async def my_projects(self, request: Request[User, Any, Any], session: AsyncSession) -> Sequence[ProjectRead]:
        """Get all projects you are part of, meaning you are a member of any `Group` within one of these `Project`s."""
        projects = await ProjectService.my_projects(session, request.user.id, self.default_options)
        return self._to_response_list(projects)
