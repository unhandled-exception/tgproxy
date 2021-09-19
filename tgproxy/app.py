import asyncio
import logging

from aiohttp import web

import tgproxy.errors as errors

DEFAULT_LOGGER_NAME = 'tgproxy.app'


class BaseApp:
    def __init__(self, logger_name=DEFAULT_LOGGER_NAME):
        self._log = logging.getLogger(logger_name)

        self._app = web.Application(
            middlewares=[
               self.error_middleware,
            ],
        )
        self._app.add_routes([
            web.get('/ping.html', self.on_ping),
        ])

    def serving_app(self):
        return self._app

    def success_response(self, status=200, **kwargs):
        return web.json_response(
            data=dict(
                status='success',
                **kwargs
            ),
            status=status,
        )

    def error_response(self, message, status=500, **kwargs):
        return web.json_response(
            dict(
                status='error',
                message=message or 'Unknown error',
                **kwargs
            ),
            status=status,
        )

    @web.middleware
    async def error_middleware(self, request, handler):
        try:
            response = await handler(request)
        except errors.BaseError as e:
            response = self.error_response(
                message=str(e),
                status=e.http_status,
            )

        return response

    async def on_ping(self, request):
        return web.Response(
            text='OK',
        )


class APIApp(BaseApp):
    def __init__(self, channels):
        super().__init__()

        self.channels = dict(channels)
        self._app.add_routes([
            web.get('/', self.on_index),
            web.get('/{channel_name}', self.on_channel_stat),
            web.post('/{channel_name}', self.on_channel_send),
        ])
        self._app.on_startup.append(self.start_background_channels_tasks)
        self._app.on_shutdown.append(self.stop_background_channels_tasks)

        self.background_tasks = list()

    async def start_background_channels_tasks(self, app):
        for ch in self.channels.values():
            self.background_tasks.append(
                asyncio.create_task(
                    ch.process_queue(),
                    name=ch,
                ),
            )

    async def stop_background_channels_tasks(self, app):
        for task in self.background_tasks:
            task.cancel()
            await task

    def _get_task_state(self, task):
        if task.cancelled():
            return 'cancelled'
        if task.done():
            return 'done'
        return 'active'

    def _has_failed_workers(self):
        return any(map(lambda x: x.cancelled() or x.done(), self.background_tasks))

    async def on_ping(self, request):
        workers = {
            task.get_name(): self._get_task_state(task) for task in self.background_tasks
        }

        if self._has_failed_workers():
            return self.error_response(
                status=502,
                message='Background workers canceled',
                workers=workers,
            )

        return self.success_response(
            workers=workers,
        )

    async def on_index(self, request):
        return self.success_response(
            channels={
                name: str(ch) for name, ch in self.channels.items()
            },
        )

    def _get_channel(self, request):
        channel_name = request.match_info['channel_name']
        channel = self.channels.get(channel_name)
        if not channel:
            raise errors.ChannelNotFound(f'Channel "{channel_name}" not found')
        return channel

    async def on_channel_send(self, request):
        channel = self._get_channel(request)
        message = channel.request_to_message(
            await request.post(),
        )
        await channel.enqueue(message)
        return self.success_response(
            status=201,
            request_id=message.request_id,
        )

    async def on_channel_stat(self, request):
        channel = self._get_channel(request)
        return self.success_response(
            **channel.get_stat(),
        )
