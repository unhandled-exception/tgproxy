import tgproxy.utils as utils
from tgproxy.queue import MemoryQueue

CHANNELS_TYPES = dict()


def register_channel_type(type, class_):
    CHANNELS_TYPES[type] = class_


def build_channel(url, **kwargs):
    parsed_url, _ = utils.parse_url(url)
    return CHANNELS_TYPES[parsed_url.scheme.lower()].from_url(url)


class Message:
    def __init__(self, text, request_id=None, **options):
        self.text = text
        self.request_id = request_id
        self.options = dict(options)


class BaseChannel:
    @classmethod
    def from_url(cls, url, **kwargs):
        raise NotImplementedError()

    def __init__(self, name, queue=None, **kwargs):
        self.name = name
        self._queue = queue or MemoryQueue()

    async def enqueue(self, message):
        await self._queue.put(message)

    async def dequeue(self):
        return await self._queue.get()


class TelegramChannel(BaseChannel):
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

    def __init__(self, name, bot_token, chat_id, queue=None, **kwargs):
        super().__init__(name, queue)
        self._bot_token = bot_token
        self.bot_name = self._bot_token[:self._bot_token.find(":")]
        self.chat_id = chat_id

    def __str__(self):
        return f'telegram://{self.bot_name}:***@{self.chat_id}/{self.name}'


register_channel_type('telegram', TelegramChannel)
