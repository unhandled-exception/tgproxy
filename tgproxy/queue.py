import asyncio
import logging

import tgproxy.errors as errors

DEFAULT_LOGGER_NAME = "tgproxy.queue.memory"
DEFAULT_QUEUE_MAXSIZE = 10000


class BaseQueue:  # pragma: no cover
    def qsize(self):
        raise NotImplementedError()

    async def enqueue(self, message):
        raise NotImplementedError()

    async def dequeue(self):
        raise NotImplementedError()

    async def regain(self, message):
        raise NotImplementedError()


class MemoryQueue(BaseQueue):
    def __init__(self, maxsize=None, logger_name=DEFAULT_LOGGER_NAME):
        self._queue = asyncio.Queue(maxsize=maxsize or DEFAULT_QUEUE_MAXSIZE)
        self._log = logging.getLogger(logger_name)

    def qsize(self):
        return self._queue.qsize()

    async def enqueue(self, message):
        try:
            # Кладем очередь без блокировок на ожидании особождения места в очереди
            self._log.info(f"Enque message {message}")
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            raise errors.QueueFull(f"Queue is full. Max size is {self._queue.maxsize}")

    async def dequeue(self):
        return await self._queue.get()

    async def task_done(self):
        self._queue.task_done()
