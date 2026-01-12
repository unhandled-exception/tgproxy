import asyncio
import logging

from aiohttp import web

import tgproxy.errors as errors

DEFAULT_LOGGER_NAME = "tgproxy.app"


class BaseApp:
    def __init__(self, logger_name=DEFAULT_LOGGER_NAME):
        self.app = web.Application(
            middlewares=[
                self._error_middleware,
            ],
        )
        self._log = logging.getLogger(logger_name)

        self.app.add_routes(
            [
                web.get("/ping.html", self._on_ping),
            ]
        )

    def _success_response(self, status=200, **kwargs):
        return web.json_response(
            data=dict(status="success", **kwargs),
            status=status,
        )

    def _error_response(self, message, status=500, **kwargs):
        return web.json_response(
            dict(status="error", message=message or "Unknown error", **kwargs),
            status=status,
        )

    @web.middleware
    async def _error_middleware(self, request, handler):
        try:
            response = await handler(request)
        except errors.BaseError as e:
            response = self._error_response(
                message=str(e),
                status=e.http_status,
            )

        return response

    async def _on_ping(self, request):
        return web.Response(
            text="OK",
        )


class HttpAPI(BaseApp):
    def __init__(self, channels):
        super().__init__()

        self.channels = dict(channels)
        self.app.add_routes(
            [
                web.get("/", self._on_index),
                web.get("/{channel_name}", self._on_channel_stat),
                web.post("/{channel_name}", self._on_channel_send),
            ]
        )
        self.app.on_startup.append(self.start_background_channels_tasks)
        self.app.on_shutdown.append(self.stop_background_channels_tasks)

        self.background_tasks = list()

    async def start_background_channels_tasks(self, app):
        self._log.info("Start background tasks")
        for ch in self.channels.values():
            self.background_tasks.append(
                asyncio.create_task(
                    ch.process(),
                    name=ch,
                ),
            )

    async def stop_background_channels_tasks(self, app):
        self._log.info("Stop background tasks")
        for task in self.background_tasks:
            task.cancel()
            await task

    def _get_task_state(self, task):
        if task.cancelled():
            return "cancelled"
        if task.done():
            return "done"
        return "active"

    def _has_failed_workers(self):
        return any(map(lambda x: x.cancelled() or x.done(), self.background_tasks))

    def _workers(self):
        return {task.get_name(): self._get_task_state(task) for task in self.background_tasks}

    async def _on_ping(self, request):
        if self._has_failed_workers():
            return self._error_response(
                status=502,
                message="Background workers canceled",
                workers=self._workers(),
            )

        return self._success_response(
            workers=self._workers(),
        )

    async def _on_index(self, request):
        return self._success_response(
            channels={name: str(ch) for name, ch in self.channels.items()},
        )

    def _get_channel(self, request):
        channel_name = request.match_info["channel_name"]
        channel = self.channels.get(channel_name)
        if not channel:
            raise errors.ChannelNotFound(f'Channel "{channel_name}" not found')
        return channel

    async def _on_channel_send(self, request):
        channel = self._get_channel(request)
        message = channel.message_class.from_request(
            await request.post(),
        )
        await channel.put(message)
        return self._success_response(
            status=201,
            request_id=message.request_id,
        )

    async def _on_channel_stat(self, request):
        channel = self._get_channel(request)
        return self._success_response(
            **channel.stat(),
        )
