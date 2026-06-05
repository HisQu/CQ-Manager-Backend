from typing import Any
from uuid import UUID

from domain.accounts.models import User
from domain.groups.services import GroupService
from lib.orm import session
from lib.utils import get_path_param
from litestar import HttpMethod, Request
from litestar.connection.base import ASGIConnection
from litestar.datastructures import MutableScopeHeaders
from litestar.enums import ScopeType
from litestar.middleware.base import AbstractMiddleware
from litestar.types import Message, Receive, Scope, Send
from sqlalchemy import select

from .models import Question


class UserQuestionGroupPermissionsMiddleware(AbstractMiddleware):
    """Adds group permission headers for routes addressed by question_id."""

    scopes = {ScopeType.HTTP}
    exclude = ["/users/register", "/users/login", "/schema"]
    exclude_http_methods = {HttpMethod.HEAD, HttpMethod.OPTIONS}
    _headers = ["Permissions-Group-Member", "Permissions-Project-Manager"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        permission_values: tuple[str, str] | None = None
        request = Request(scope)

        if request.method not in self.exclude_http_methods:
            connection: ASGIConnection[Any, User, Any, Any] = ASGIConnection(scope)
            if question_id := get_path_param(UUID, "question_id", connection):
                async with session() as session_:
                    group_id = await session_.scalar(select(Question.group_id).where(Question.id == question_id))
                    if group_id:
                        permission_values = (
                            str(await GroupService.is_member(session_, group_id, connection.user.id)),
                            str(await GroupService.is_manager(session_, group_id, connection.user.id)),
                        )

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start" and permission_values is not None:
                headers = MutableScopeHeaders.from_message(message)
                headers[self._headers[0]] = permission_values[0]
                headers[self._headers[1]] = permission_values[1]

            return await send(message)

        await self.app(scope, receive, send_wrapper)
