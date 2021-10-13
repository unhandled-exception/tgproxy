import asyncio
import functools
import logging
import socket
import sys
import uuid

import tgproxy.providers as providers
import tgproxy.utils as utils
from tgproxy.queue import MemoryQueue

DEFAULT_LOGGER_NAME = 'tgproxy.channel'
CHANNELS_TYPES = dict()


def register_channel_type(type, class_):
    CHANNELS_TYPES[type] = class_


def build_channel(url, **kwargs):
    parsed_url, channel_options = utils.parse_url(url)
    return CHANNELS_TYPES[parsed_url.scheme.lower()].from_url(
        url,
        channel_options=channel_options,
        **kwargs,
    )


class Message:
    def __init__(self, text, request_id=None, **options):
        self.text = text
        self.request_id = request_id or str(uuid.uuid1())
        self.options = dict(options)

    @functools.cache
    def __repr__(self):
        return f'Message(text="{self.text}", request_id="{self.request_id}", options={self.options})'


class BaseChannel:
    # dict: name: {default: value}
    request_fields = {
        'text': {'default': '<Empty message>'},
        'request_id': {},
    }

    @classmethod
    def from_url(cls, url, **kwargs):  # pragma: no cover
        raise NotImplementedError()

    def __init__(self, name, queue=None, logger_name=DEFAULT_LOGGER_NAME, channel_options=None, **kwargs):
        self.name = name
        self._queue = queue or MemoryQueue()
        self._log = logging.getLogger(f'{logger_name}.{name}')
        self._stat = dict(
            queued=0,
            sended=0,
            errors=0,
            last_error=None,
        )

    def qsize(self):
        return self._queue.qsize()

    def get_stat(self):
        return self._stat

    async def enqueue(self, message):
        self._log.info(f'Enque message: {message}')
        await self._queue.enqueue(message)
        self._stat['queued'] += 1

    async def dequeue(self):
        message = await self._queue.dequeue()
        self._log.info(f'Deque message: {message}')
        return message

    def request_to_message(self, request):
        message = Message(
            **{
                f: request.get(f, v.get('default'))
                for f, v in self.request_fields.items()
                if request.get(f, v.get('default')) is not None
            }
        )
        return message

    async def process_queue(self):  # pragma: no cover
        raise NotImplementedError()


class TelegramChannel(BaseChannel):
    request_fields = {
        'text': {'default': '<Empty message>'},
        'request_id': {},
        'parse_mode': {},
        'disable_web_page_preview': {'default': 0},
        'disable_notifications': {'default': 0},
        'reply_to_message_id': {},
    }

    @classmethod
    def from_url(cls, url, **kwargs):
        parsed_url, options = utils.parse_url(url)
        return cls(
            name=parsed_url.path.strip('/'),
            bot_token=f'{parsed_url.username}:{parsed_url.password}',
            chat_id=parsed_url.hostname,
            **options,
            **kwargs
        )

    def __init__(self, name, bot_token, chat_id, queue=None, provider=None, channel_options=None, send_banner_on_startup=True, **kwargs):
        super().__init__(name, queue)
        self._bot_token = bot_token
        self._bot_name = self._bot_token[:self._bot_token.find(":")]
        self._chat_id = chat_id

        self.channel_options = dict(channel_options)
        self.provider = provider
        if not self.provider:
            self.provider = providers.TelegramChat(
                chat_id=self._chat_id,
                bot_token=self._bot_token,
                **self.channel_options,
            )
        self.send_banner_on_startup = bool(
            int(self.channel_options['send_banner_on_startup']) if 'send_banner_on_startup' in self.channel_options else send_banner_on_startup,
        )
        self._log.info(f'self.send_banner_on_startup == {self.send_banner_on_startup}')

    def __str__(self):
        co = [f'{k}={v}' for k, v in self.channel_options.items()]
        co = f'{"&".join(co)}'
        if co:
            co = f'?{co}'
        return f'telegram://{self._bot_name}:***@{self._chat_id}/{self.name}{co}'

    def _get_banner(self):
        return self.request_to_message(
            dict(text=f'Start tgproxy on {socket.gethostname()}'),
        )

    async def process_queue(self):
        self._log.info(f'Start queue processor for {self}')
        if self.send_banner_on_startup:
            await self.enqueue(self._get_banner())

        async with self.provider.session() as provider:
            try:
                while True:
                    message = await self.dequeue()
                    self._log.info(f'Send message: {message}')
                    await self._send_message(provider, message)
            except asyncio.CancelledError:
                self._log.info(f'Finish queue processor. Queue size: {self._queue.qsize()}')
            except Exception as e:
                self._log.error(str(e), exc_info=sys.exc_info())
                self._log.info(f'Failed queue processor. Queue size: {self._queue.qsize()}')
                raise

    async def _send_message(self, provider, message):
        try:
            await provider.send_message(message)
            self._log.info(f'Message sended: {message}')
            self._stat['sended'] += 1
        except providers.errors.ProviderError as e:
            self._stat['errors'] += 1
            self._stat['last_error'] = str(e)
            self._log.error(f'Message: {e} Error: {message}')


register_channel_type('telegram', TelegramChannel)
