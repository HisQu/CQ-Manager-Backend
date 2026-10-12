import hashlib

from litestar.datastructures import Headers, MutableScopeHeaders
from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware
from litestar.status_codes import HTTP_200_OK, HTTP_304_NOT_MODIFIED
from litestar.types import ASGIApp, Message, Receive, Scope, Send


class ETagMiddleware(ASGIMiddleware):
    """Conditional `GET` requests for JSON responses.

    Tags every successful JSON `GET` response with an `ETag` (a hash of the body and the permission headers)
    and answers a request whose `If-None-Match` carries that tag with an empty `304 Not Modified`.
    The response is still built, but an unchanged one is neither transferred nor parsed by the client.

    Notes:
        * buffers the body of the affected responses, so it is not meant for streamed downloads
        * tags are per user, as the permission headers and fields like unread comments are
    """

    scopes = (ScopeType.HTTP,)

    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        if scope["method"] != "GET":
            await next_app(scope, receive, send)
            return

        start: Message | None = None
        chunks: list[bytes] = []

        async def send_wrapper(message: Message) -> None:
            nonlocal start

            if message["type"] == "http.response.start":
                headers = MutableScopeHeaders.from_message(message)
                is_json = (headers.get("content-type") or "").startswith("application/json")
                if message["status"] == HTTP_200_OK and is_json:
                    start = message
                    return
            elif message["type"] == "http.response.body" and start is not None:
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    await self._send_tagged(scope, start, b"".join(chunks), send)
                return

            await send(message)

        await next_app(scope, receive, send_wrapper)

    @staticmethod
    async def _send_tagged(scope: Scope, start: Message, body: bytes, send: Send) -> None:
        digest = hashlib.blake2b(body, digest_size=16)
        for name, value in sorted(start["headers"]):
            if name.lower().startswith(b"permissions-"):
                digest.update(b"\n" + name.lower() + b":" + value)
        etag = f'"{digest.hexdigest()}"'

        headers = MutableScopeHeaders.from_message(start)
        headers["ETag"] = etag
        headers["Cache-Control"] = "private, no-cache"

        if_none_match = Headers.from_scope(scope).get("if-none-match", "")
        if etag in {tag.strip().removeprefix("W/") for tag in if_none_match.split(",")}:
            start["status"] = HTTP_304_NOT_MODIFIED
            del headers["content-length"]
            del headers["content-type"]
            body = b""

        await send(start)
        await send({"type": "http.response.body", "body": body, "more_body": False})
