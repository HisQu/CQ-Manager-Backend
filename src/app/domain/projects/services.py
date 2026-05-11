from functools import partial
from typing import Coroutine, Iterable, Sequence
from uuid import UUID

from domain.accounts.authentication.services import EncryptionService
from domain.accounts.mails import UserMailService
from domain.accounts.models import User
from domain.accounts.services import UserService
from domain.comments.models import Comment
from domain.consolidations.models import ConsolidatedQuestions, Consolidation
from domain.groups.models import Group, GroupMembers
from domain.questions.models import Question
from domain.ratings.models import Rating
from domain.terms.models import AnnotatedPassages, Passage, Term
from domain.topics.models import Topic
from domain.versions.models import Version
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from .dtos import ProjectCreateDTO, ProjectUpdateDTO, ProjectUsersAddDTO, ProjectUsersRemoveDTO
from .mails import ProjectMailService
from .models import Project, ProjectEngineers, ProjectManagers

AsyncCallable = Coroutine[None, None, None]


class ProjectService:
    @staticmethod
    async def get_project(
        session: AsyncSession,
        id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Project:
        statement = select(Project).where(Project.id == id)
        if options:
            statement = statement.options(*options)

        project = await session.scalar(statement)
        if not project:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND)  # TODO: raise explicit exception
        return project

    @staticmethod
    async def get_projects(
        session: AsyncSession, options: Iterable[ExecutableOption] | None = None
    ) -> Sequence[Project]:
        statement = select(Project)
        if options:
            statement = statement.options(*options)
        return (await session.scalars(statement)).all()

    @staticmethod
    async def create(
        session: AsyncSession,
        encryption: EncryptionService,
        data: ProjectCreateDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> tuple[
        Project,
        partial[AsyncCallable] | None,
        partial[AsyncCallable] | None,
        partial[AsyncCallable] | None,
        partial[AsyncCallable] | None,
    ]:
        managers: list[User] = []
        managers_ = None
        if data.managers:
            managers_ = await UserService.get_or_create_users(session, encryption, data.managers)
            managers.extend([*managers_.existing, *map(lambda u: u[0], managers_.created)])

        engineers: list[User] = []
        engineers_ = None
        if data.engineers:
            engineers_ = await UserService.get_or_create_users(session, encryption, data.engineers)
            engineers.extend([*engineers_.existing, *map(lambda u: u[0], engineers_.created)])

        project = Project(name=data.name, description=data.description, managers=managers, engineers=engineers)
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project = await ProjectService.get_project(session, project.id, options)

        invite_task1, invite_task2 = None, None
        if managers_ and managers_.created:
            invite_task1 = partial(UserMailService.send_invitation_mail, users=managers_)
        if engineers_ and engineers_.created:
            invite_task2 = partial(UserMailService.send_invitation_mail, users=engineers_)

        manager_task = None
        if managers_:
            manager_task = partial(
                ProjectMailService.send_invitation_mail, users=managers_, project=project, role="manager"
            )

        engineers_task = None
        if engineers_:
            engineers_task = partial(
                ProjectMailService.send_invitation_mail, users=engineers_, project=project, role="ontology engineer"
            )

        return project, invite_task1, invite_task2, manager_task, engineers_task

    @staticmethod
    async def add_managers(
        session: AsyncSession,
        encryption: EncryptionService,
        id: UUID,
        data: ProjectUsersAddDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> tuple[Project, partial[AsyncCallable] | None, partial[AsyncCallable] | None]:
        if not data.emails:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST)  # TODO: raise explicit exception

        managers = await UserService.get_or_create_users(session, encryption, data.emails)
        project = await ProjectService.get_project(session, id, [selectinload(Project.managers)])

        project.managers.extend(
            filter(
                lambda x: x not in project.managers,
                [*managers.existing, *map(lambda u: u[0], managers.created)],
            ),
        )

        initiation_task = None
        if managers:
            initiation_task = partial(UserMailService.send_invitation_mail, users=managers)

        manager_task = None
        if managers:
            manager_task = partial(
                ProjectMailService.send_invitation_mail, users=managers, project=project, role="manager"
            )

        await session.commit()
        await session.refresh(project)
        return await ProjectService.get_project(session, project.id, options), initiation_task, manager_task

    @staticmethod
    async def remove_managers(
        session: AsyncSession,
        id: UUID,
        data: ProjectUsersRemoveDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Project:
        if not data.ids:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST)  # TODO: raise explicit exception

        project = await ProjectService.get_project(session, id, [selectinload(Project.managers)])

        ids = set(data.ids)
        ex_managers = filter(lambda user: user.id in ids, project.managers)
        _ = [project.managers.remove(user) for user in ex_managers]

        await session.commit()
        await session.refresh(project)
        return await ProjectService.get_project(session, project.id, options)

    @staticmethod
    async def add_engineers(
        session: AsyncSession,
        encryption: EncryptionService,
        id: UUID,
        data: ProjectUsersAddDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> tuple[Project, partial[AsyncCallable] | None, partial[AsyncCallable] | None]:
        if not data.emails:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST)  # TODO: raise explicit exception

        engineers = await UserService.get_or_create_users(session, encryption, data.emails)
        project = await ProjectService.get_project(session, id, [selectinload(Project.engineers)])

        project.engineers.extend(
            filter(
                lambda x: x not in project.engineers,
                [*engineers.existing, *map(lambda u: u[0], engineers.created)],
            ),
        )

        initiation_task = None
        if engineers:
            initiation_task = partial(UserMailService.send_invitation_mail, users=engineers)

        engineers_task = None
        if engineers:
            engineers_task = partial(
                ProjectMailService.send_invitation_mail, users=engineers, project=project, role="ontology engineer"
            )

        await session.commit()
        await session.refresh(project)
        return await ProjectService.get_project(session, project.id, options), initiation_task, engineers_task

    @staticmethod
    async def remove_engineers(
        session: AsyncSession,
        id: UUID,
        data: ProjectUsersRemoveDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Project:
        if not data.ids:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST)  # TODO: raise explicit exception

        project = await ProjectService.get_project(session, id, [selectinload(Project.engineers)])

        ids = set(data.ids)
        ex_engineers = filter(lambda user: user.id in ids, project.engineers)
        _ = [project.engineers.remove(user) for user in ex_engineers]

        await session.commit()
        await session.refresh(project)
        return await ProjectService.get_project(session, project.id, options)

    @staticmethod
    async def update(
        session: AsyncSession,
        id: UUID,
        data: ProjectUpdateDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Project:
        project = await ProjectService.get_project(session, id)
        project.name = data.name if data.name else project.name
        project.description = data.description if data.description else project.description

        await session.commit()
        await session.refresh(project)
        return await ProjectService.get_project(session, project.id, options)

    @staticmethod
    async def delete(session: AsyncSession, id: UUID) -> bool:
        if not await session.scalar(select(Project.id).where(Project.id == id)):
            return False

        group_ids = select(Group.id).where(Group.project_id == id)
        question_ids = select(Question.id).where(Question.group_id.in_(group_ids))
        consolidation_ids = select(Consolidation.id).where(Consolidation.project_id == id)
        term_ids = select(Term.id).where(Term.project_id == id)
        passage_ids = select(Passage.id).where(Passage.term_id.in_(term_ids))

        statements = [
            delete(ConsolidatedQuestions).where(
                or_(
                    ConsolidatedQuestions.c.consolidation_id.in_(consolidation_ids),
                    ConsolidatedQuestions.c.question_id.in_(question_ids),
                )
            ),
            delete(AnnotatedPassages).where(
                or_(
                    AnnotatedPassages.c.question_id.in_(question_ids),
                    AnnotatedPassages.c.passage_id.in_(passage_ids),
                )
            ),
            delete(Comment).where(Comment.question_id.in_(question_ids)),
            delete(Rating).where(Rating.question_id.in_(question_ids)),
            delete(Version).where(Version.question_id.in_(question_ids)),
            delete(Consolidation).where(Consolidation.project_id == id),
            delete(Question).where(Question.group_id.in_(group_ids)),
            delete(GroupMembers).where(GroupMembers.c.group_id.in_(group_ids)),
            delete(Group).where(Group.project_id == id),
            delete(Passage).where(Passage.term_id.in_(term_ids)),
            delete(Term).where(Term.project_id == id),
            delete(Topic).where(Topic.project_id == id),
            delete(ProjectManagers).where(ProjectManagers.c.project_id == id),
            delete(ProjectEngineers).where(ProjectEngineers.c.project_id == id),
            delete(Project).where(Project.id == id),
        ]
        for statement in statements:
            await session.execute(statement)

        await session.flush()
        return True

    @staticmethod
    async def my_projects(
        session: AsyncSession,
        user_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Project]:
        """Returns all `Project`s a given `User` is a member of."""
        options = [] if not options else options
        statement = select(Project).join(Group).filter(Group.members.any(User.id == user_id))
        statement = statement.options(*options)
        return (await session.scalars(statement)).all()

    @staticmethod
    async def is_manager(session: AsyncSession, id: UUID, user_id: UUID) -> bool:
        """Checks wether a given `User` is a manager of the given `Project`."""
        statement = select(Project).where(Project.id == id)
        statement = statement.join(User, Project.managers)
        statement = statement.filter(User.id == user_id)

        return True if await session.scalar(statement) else False

    @staticmethod
    async def is_engineer(session: AsyncSession, id: UUID, user_id: UUID) -> bool:
        """Checks wether a given `User` is an engineer of the given `Project`."""
        statement = select(Project).where(Project.id == id)
        statement = statement.join(User, Project.engineers)
        statement = statement.filter(User.id == user_id)

        return True if await session.scalar(statement) else False

    @staticmethod
    async def is_member(session: AsyncSession, id: UUID, user_id: UUID) -> bool:
        """Checks wether a given `User` is a member of the given `Project`."""
        statement = select(Project).where(Project.id == id)
        statement = statement.join(Group, Project.groups)
        statement = statement.join(User, Group.members)
        statement = statement.filter(User.id == user_id)

        return True if await session.scalar(statement) else False
