"""Deployment identity for the maintained relay patch stack."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

RELAY_VERSION = "custom-v1.25.0-beta.7.1"


class RelayBuildMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_version(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [*message.get("headers", []), (b"x-relay-version", RELAY_VERSION.encode())],
                }
            await send(message)

        await self.app(scope, receive, send_version)
