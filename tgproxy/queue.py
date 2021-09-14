import asyncio

import tgproxy.errors as errors

DEFAULT_QUEUE_MAXSIZE = 1000


class BaseQueue:
    async def enqueue(self, message):
        raise NotImplementedError()

    async def dequeue(self):
        raise NotImplementedError()

    async def regain(self, message):
        raise NotImplementedError()


class MemoryQueue(BaseQueue):
    def __init__(self, maxsize=DEFAULT_QUEUE_MAXSIZE):
        self._queue = asyncio.Queue(maxsize)

    async def enqueue(self, message):
        try:
            # Кладем очередь без блокировок на ожидании особождения места в очереди
            return self._queue.put_nowait(message)
        except asyncio.QueueFull:
            raise errors.QueueFull('Queue is full. Max size is {self.maxsize}')

    async def dequeue(self):
        # Ждем сообщение из очереди и сразу сообщаем очереди, что задача выполнена
        message = await self._queue.get()
        self._queue.task_done()
        return message

    async def regain(self, message):
        # Восстанавливаем сообщение в очереди
        # TODO: нужна вторая очередь. Если заполнена основная, то класть в резервную.
        # и пытаться брать задачу в dequeue сначала из резервной, а потом из основной
        # Но этого пока не требуется совсем, потому что мы можем терять месаги
        raise NotImplementedError()
