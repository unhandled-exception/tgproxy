import asyncio
import functools
import logging
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
    parsed_url, _ = utils.parse_url(url)
    return CHANNELS_TYPES[parsed_url.scheme.lower()].from_url(url, **kwargs)


class Message:
    def __init__(self, text, request_id=None, **options):
        self.text = text
        self.request_id = request_id or str(uuid.uuid1())
        self.options = dict(options)

    @functools.cache
    def __repr__(self):
        return f'Message(text="{self.text}, request_id={self.request_id}", options={self.options})'


class BaseChannel:
    # dict: name: {default: value}
    request_fields = {
        'text': {'default': '<Empty message>'},
        'request_id': {},
    }

    @classmethod
    def from_url(cls, url, **kwargs):
        raise NotImplementedError()

    def __init__(self, name, queue=None, logger_name=DEFAULT_LOGGER_NAME, **kwargs):
        self.name = name
        self._queue = queue or MemoryQueue()
        self._log = logging.getLogger(f'{logger_name}.{name}')

    def qsize(self):
        return self._queue.qsize()

    async def enqueue(self, message):
        self._log.info(f'Enque message: {message}')
        await self._queue.enqueue(message)

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

    async def process_queue(self):
        raise NotImplementedError()


class TelegramChannel(BaseChannel):
    request_fields = {
        'text': {'default': '<Empty message>'},
        'request_id': {},
        'parse_mode': {},
        'disable_web_page_preview': {'default': 0},
        'disable_notifications': {'default': 0},
        'repy_to_message_id': {},
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

    def __init__(self, name, bot_token, chat_id, queue=None, provider=None, **kwargs):
        super().__init__(name, queue)
        self._bot_token = bot_token
        self._bot_name = self._bot_token[:self._bot_token.find(":")]
        self._chat_id = chat_id

        self._provider = provider
        if not self._provider:
            self._provider = providers.TelegramChat(
                chat_id=self._chat_id,
                bot_token=self._bot_token,
            )

    def __str__(self):
        return f'telegram://{self._bot_name}:***@{self._chat_id}/{self.name}'

    async def process_queue(self):
        self._log.info('Start queue processor')

        async with self._provider.session() as provider:
            try:
                while True:
                    message = await self.dequeue()
                    self._log.info(f'Send message: {message}')
                    await self._send_message(provider, message)
                    self._log.info(f'Message sended: {message}')
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self._log.error(str(e), exc_info=sys.exc_info())
                raise
            finally:
                self._log.info('Finish queue processor')

    async def _send_message(self, provider, message):
        try:
            await provider.send_message(message)
        except providers.errors.ProviderError as e:
            self._log.error(f'Message: {e} Error: {message}')


register_channel_type('telegram', TelegramChannel)
