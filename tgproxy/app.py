from aiohttp import web

import tgproxy.errors as errors


class BaseApp:
    def __init__(self, host='localhost', port='5000'):
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

    def on_ping(self, request):
        return web.Response(
            text='OK',
        )


class APIApp(BaseApp):
    def __init__(self, channels, host, port):
        super().__init__(host=host, port=port)
        self._channels = dict(channels)
        self._app.add_routes([
            web.get('/', self.on_index),
            web.post('/{channel}', self.on_channel),
        ])

    def on_index(self, request):
        return self.success_response(
            channels={
                name: str(ch) for name, ch in self._channels.items()
            },
        )

    def on_channel(self, request):
        raise errors.BaseError('Not implemented')
