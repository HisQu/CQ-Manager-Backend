from functools import partial
from typing import Coroutine, Iterable, Sequence
from itertools import chain
from uuid import UUID

from domain.accounts.authentication.services import EncryptionService
from domain.accounts.mails import UserMailService
from domain.accounts.models import User
from domain.accounts.services import UserService
from domain.projects.models import Project
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from .dtos import GroupCreateDTO, GroupUpdateDTO, GroupUsersAddDTO, GroupUsersRemoveDTO
from .mails import GroupMailService
from .models import Group
from .exceptions import EmptyNameException

AsyncCallable = Coroutine[None, None, None]


class GroupService:
    @staticmethod
    async def get_group(
        session: AsyncSession,
        id: UUID,
        project_id: UUID | None = None,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Group:
        if project_id:
            statement = select(Group).where(Group.id == id, Group.project_id == project_id)
        else:
            statement = select(Group).where(Group.id == id)

        if options:
            statement = statement.options(*options)

        group = await session.scalar(statement)
        if not group:
            raise HTTPException(status_code=HTTP_404_NOT_FOUND)  # TODO: raise explicit exception
        return group

    @staticmethod
    async def get_groups(
        session: AsyncSession,
        project_id: UUID | None = None,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Group]:
        if project_id:
            statement = select(Group).where(Group.project_id == project_id)
        else:
            statement = select(Group)

        if options:
            statement = statement.options(*options)
        return (await session.scalars(statement)).all()

    @staticmethod
    async def create(
        session: AsyncSession,
        encryption: EncryptionService,
        data: GroupCreateDTO,
        project_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> tuple[Group, partial[AsyncCallable] | None, partial[AsyncCallable] | None]:
        if not data.name:
            raise EmptyNameException()
        options = options or []
        members: list[User] = []
        members_ = None
        if data.members:
            members_ = await UserService.get_or_create_users(session, encryption, data.members)
            members.extend([*members_.existing, *map(lambda u: u[0], members_.created)])
        group = Group(name=data.name, project_id=project_id, members=members)
        session.add(group)
        await session.commit()
        await session.refresh(group)
        group = await GroupService.get_group(session, group.id, project_id, [*options, selectinload(Group.project)])
        invite_task = partial(UserMailService.send_invitation_mail, users=members_) if members_ else None
        message_task = partial(GroupMailService.send_invitation_mail, users=members_, group=group) if members_ else None
        return group, invite_task, message_task

    @staticmethod
    async def add_members(
        session: AsyncSession,
        encryption: EncryptionService,
        id: UUID,
        project_id: UUID | None,
        data: GroupUsersAddDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> tuple[Group, partial[AsyncCallable] | None, partial[AsyncCallable] | None]:
        if not data.emails:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST)  # TODO: raise explicit exception

        members = await UserService.get_or_create_users(session, encryption, data.emails)
        group = await GroupService.get_group(
            session,
            id,
            project_id,
            [
                selectinload(Group.members),
                selectinload(Group.project),
            ],
        )

        existing_member_ids = {member.id for member in group.members}
        new_members = [
            member
            for member in chain(
                members.existing,
                map(lambda user: user[0], members.created),
            )
            if member.id not in existing_member_ids
        ]
        group.members.extend(new_members)

        await session.commit()
        await session.refresh(group)
        group = await GroupService.get_group(session, group.id, project_id, options)

        invite_task = (
            partial(UserMailService.send_invitation_mail, users=members)
            if members.created
            else None
        )
        message_task = partial(
            GroupMailService.send_invitation_mail, users=members, group=group
        )

        return group, invite_task, message_task

    @staticmethod
    async def remove_members(
        session: AsyncSession,
        id: UUID,
        project_id: UUID,
        data: GroupUsersRemoveDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Group:
        if not data.ids:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST)  # TODO: raise explicit exception

        group = await GroupService.get_group(session, id, project_id, [selectinload(Group.members)])

        ids = set(data.ids)
        ex_members = filter(lambda user: user.id in ids, group.members)
        _ = [group.members.remove(user) for user in ex_members]

        await session.commit()
        await session.refresh(group)
        return await GroupService.get_group(session, group.id, project_id, options)

    @staticmethod
    async def update(
        session: AsyncSession,
        id: UUID,
        project_id: UUID,
        data: GroupUpdateDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Group:
        group = await GroupService.get_group(session, id, project_id)
        group.name = data.name if data.name else group.name

        await session.commit()
        await session.refresh(group)
        return await GroupService.get_group(session, group.id, project_id, options)

    @staticmethod
    async def delete(
        session: AsyncSession,
        id: UUID,
        project_id: UUID,
    ) -> bool:
        result = await session.execute(delete(Group).where(Group.id == id, Group.project_id == project_id))
        return True if result.rowcount > 0 else False

    @staticmethod
    async def my_groups(
        session: AsyncSession,
        user_id: UUID,
        project_id: UUID | None = None,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Group]:
        """Returns all `Groups`s a given `User` is a member of."""
        options = [] if not options else options
        statement = select(Group) if not project_id else select(Group).where(Group.project_id == project_id)
        statement = statement.filter(Group.members.any(User.id == user_id))
        statement = statement.options(*options)
        return (await session.scalars(statement)).all()

    @staticmethod
    async def is_member(session: AsyncSession, id: UUID, user_id: UUID) -> bool:
        """Checks wether a given `User` is a member of the given `Group`, (Internal use only)."""
        statement = select(Group).where(Group.id == id)
        statement = statement.join(User, Group.members)
        statement = statement.filter(User.id == user_id)

        return True if await session.scalar(statement) else False

    @staticmethod
    async def is_manager(session: AsyncSession, id: UUID, user_id: UUID) -> bool:
        """Checks wether a given `User` is a manager of the `Project` a given `Group` belongs to, (Internal use only)."""
        statement = (
            select(Group)
            .where(Group.id == id)
            .options(selectinload(Group.project).options(selectinload(Project.managers)))
        )
        # i think this could be done on the db as well but im not sure how without warnings,
        # this should be fine given the expected result size
        if group := await session.scalar(statement):
            return any(user_id == manager.id for manager in group.project.managers)
        return False
