import asyncio
import functools
import logging
import socket
import sys
import time
import uuid

import tgproxy.errors as errors
import tgproxy.providers as providers
import tgproxy.utils as utils
from tgproxy.queue import MemoryQueue

DEFAULT_LOGGER_NAME = 'tgproxy.channel'
CHANNELS_TYPES = dict()


def register_channel_type(cls):
    CHANNELS_TYPES[cls.schema] = cls


def build_channel(url, **kwargs):
    parsed_url, channel_options = utils.parse_url(url)

    channel_type = CHANNELS_TYPES.get(parsed_url.scheme.lower())
    if not channel_type:
        raise errors.UnknownChannelType(f'"{parsed_url.scheme}" is an unknown channel type. URL: {url}')

    return channel_type.from_url(
        url,
        **(channel_options | kwargs),
    )


class Message:
    # dict: name: {default: value}
    request_fields = {
        'text': {'default': '<Empty message>'},
        'request_id': {},
    }

    @classmethod
    def from_request(cls, request):
        message = cls(
            **{
                f: request.get(f, v.get('default'))
                for f, v in cls.request_fields.items()
                if request.get(f, v.get('default')) is not None
            }
        )
        return message

    def __init__(self, text, request_id=None, **options):
        self.text = text
        self.request_id = request_id or str(uuid.uuid1())
        self.options = dict(options)

    @functools.cache
    def __repr__(self):
        return f'{self.__class__.__name__}(text="{self.text}", request_id="{self.request_id}", options={self.options})'


class BaseChannel:
    schema = '-'
    message_class = Message

    @classmethod
    def from_url(cls, url, queue=None, **kwargs):  # pragma: no cover
        raise NotImplementedError()

    def __init__(self, name, queue, provider, send_banner_on_startup=False, logger_name=DEFAULT_LOGGER_NAME, **kwargs):
        self.name = name
        self.provider = provider
        self.send_banner_on_startup = send_banner_on_startup

        self._queue = queue or MemoryQueue()
        self._log = logging.getLogger(f'{logger_name}.{name}')
        self._stat = dict(
            queued=0,
            sended=0,
            last_sended_at=None,
            errors=0,
            last_error=None,
            last_error_at=None,
        )

        self._log.info(f'self.send_banner_on_startup == {self.send_banner_on_startup}')

    def qsize(self):
        return self._queue.qsize()

    def stat(self):
        return dict(
            filter(
                lambda x: x[1] is not None,
                self._stat.items(),
            ),
        )

    async def put(self, message):
        await self._enqueue(message)

    async def process(self):
        self._log.info(f'Start queue processor for {self}')
        if self.send_banner_on_startup:
            await self.put(self._get_banner())

        async with self.provider.session() as provider:
            try:
                while True:
                    message = await self._dequeue()
                    self._log.info(f'Send message: {message}')
                    await self._send_message(provider, message)
            except asyncio.CancelledError:
                self._log.info(f'Finish queue processor. Queue size: {self._queue.qsize()}')
            except Exception as e:
                self._log.error(str(e), exc_info=sys.exc_info())
                self._log.info(f'Failed queue processor. Queue size: {self._queue.qsize()}')
                raise

    async def _enqueue(self, message):
        self._log.info(f'Enque message: {message}')
        await self._queue.enqueue(message)
        self._stat['queued'] += 1

    async def _dequeue(self):
        message = await self._queue.dequeue()
        self._log.info(f'Deque message: {message}')
        return message

    def _get_banner(self):
        return self.message_class.from_request(
            dict(text=f'Start tgproxy on {socket.gethostname()}'),
        )

    async def _send_message(self, provider, message):
        try:
            await provider.send_message(message)
            self._log.info(f'Message sended: {message}')
            self._stat['sended'] += 1
            self._stat['last_sended_at'] = round(time.time())
        except providers.errors.ProviderError as e:
            self._stat['errors'] += 1
            self._stat['last_error'] = str(e)
            self._stat['last_error_at'] = round(time.time())
            self._log.error(f'Message: {e} Error: {message}')


class TelegramMessage(Message):
    request_fields = {
        'text': {'default': '<Empty message>'},
        'request_id': {},
        'parse_mode': {},
        'disable_web_page_preview': {'default': 0},
        'disable_notifications': {'default': 0},
        'reply_to_message_id': {},
    }


class TelegramChannel(BaseChannel):
    schema = 'telegram'
    message_class = TelegramMessage

    @classmethod
    def from_url(cls, url, queue=None, **kwargs):
        parsed_url, options = utils.parse_url(url)
        return cls(
            name=parsed_url.path.strip('/'),
            queue=queue,
            provider=providers.TelegramChat(
                chat_id=parsed_url.hostname,
                bot_token=f'{parsed_url.username}:{parsed_url.password}',
                **(options | kwargs)
            ),
            **(options | kwargs)
        )

    def __init__(self, name, queue, provider, send_banner_on_startup=True, **kwargs):
        super().__init__(
            name,
            queue,
            provider,
            send_banner_on_startup=bool(int(send_banner_on_startup)),
            **kwargs
        )
        self._bot_token = provider.bot_token
        self._bot_name = self._bot_token[:self._bot_token.find(":")]
        self._chat_id = provider.chat_id
        self._channel_options = dict(kwargs)

    def __str__(self):
        co = [f'{k}={v}' for k, v in self._channel_options.items()]
        co = f'{"&".join(co)}'
        if co:
            co = f'?{co}'
        return f'{self.schema}://{self._bot_name}:***@{self._chat_id}/{self.name}{co}'


register_channel_type(TelegramChannel)
