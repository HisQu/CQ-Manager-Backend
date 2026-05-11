from typing import Any
from uuid import UUID

from domain.accounts.models import User
from lib.orm import session
from lib.utils import get_path_param
from litestar.connection.base import ASGIConnection
from litestar.exceptions.http_exceptions import ImproperlyConfiguredException
from litestar.handlers.base import BaseRouteHandler

from .exceptions import (
    ProjectEngineerRequiredException,
    ProjectManagerRequiredException,
    ProjectMembershipRequiredException,
)
from .services import ProjectService


async def project_manager_guard(connection: ASGIConnection[Any, User, Any, Any], _: BaseRouteHandler) -> None:
    """Limit route access to project managers only.

    Requires a `project_id: UUID` path parameter to be set.
    """
    if connection.user.is_system_admin:
        return

    if project_id := get_path_param(UUID, "project_id", connection):
        async with session() as session_:
            if await ProjectService.is_manager(session_, project_id, connection.user.id):
                return

        raise ProjectManagerRequiredException()
    raise ImproperlyConfiguredException()


async def ontology_engineer_guard(connection: ASGIConnection[Any, User, Any, Any], _: BaseRouteHandler) -> None:
    """Limit route access to ontology engineers only.

    Requires a `project_id: UUID` path parameter to be set.
    """
    if connection.user.is_system_admin:
        return

    if project_id := get_path_param(UUID, "project_id", connection):
        async with session() as session_:
            if await ProjectService.is_engineer(session_, project_id, connection.user.id):
                return

        raise ProjectEngineerRequiredException()
    raise ImproperlyConfiguredException()


async def project_member_guard(connection: ASGIConnection[Any, User, Any, Any], _: BaseRouteHandler) -> None:
    """Limit route access to project members (i.e. members of groups within a project) only.

    Requires a `project_id: UUID` path parameter to be set.
    """
    if connection.user.is_system_admin:
        return

    if project_id := get_path_param(UUID, "project_id", connection):
        async with session() as session_:
            if await ProjectService.is_member(session_, project_id, connection.user.id):
                return

        raise ProjectMembershipRequiredException()
    raise ImproperlyConfiguredException()
