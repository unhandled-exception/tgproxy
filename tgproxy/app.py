import asyncio
import logging

from aiohttp import web

import tgproxy.errors as errors


class BaseApp:
    def __init__(self, host='localhost', port='5000'):
        self._log = logging.getLogger('tgproxy.app')
        self._host = host
        self._port = port

        self._app = web.Application(
            middlewares=[
               self.error_middleware,
            ],
        )
        self._app.add_routes([
            web.get('/ping.html', self.on_ping),
        ])

    def run(self):
        web.run_app(
            self._app,
            host=self._host,
            port=self._port,
        )

    def success_response(self, status=200, **kwargs):
        return web.json_response(
            data=dict(
                status='OK',
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
    def __init__(self, channels, host, port):
        super().__init__(host=host, port=port)
        self._channels = dict(channels)
        self._app.add_routes([
            web.get('/', self.on_index),
            web.post('/{channel_name}', self.on_channel),
        ])
        self._app.on_startup.append(self.start_background_channels_tasks)
        self._app.on_shutdown.append(self.stop_background_channels_tasks)

        self._background_tasks = list()

    async def start_background_channels_tasks(self, app):
        for ch in self._channels.values():
            self._background_tasks.append(
                asyncio.create_task(
                    ch.process_queue(),
                ),
            )

    async def stop_background_channels_tasks(self, app):
        for task in self._background_tasks:
            task.cancel()
            await task

    async def on_index(self, request):
        return self.success_response(
            channels={
                name: str(ch) for name, ch in self._channels.items()
            },
        )

    def get_channel(self, request):
        channel_name = request.match_info['channel_name']
        channel = self._channels.get(channel_name)
        if not channel:
            raise errors.ChannelNotFound(f'Channel "{channel_name}" not found')
        return channel

    async def on_channel(self, request):
        channel = self.get_channel(request)
        message = channel.request_to_message(
            await request.post(),
        )
        await channel.enqueue(message)
        return self.success_response(
            status=201,
            request_id=message.request_id,
        )
