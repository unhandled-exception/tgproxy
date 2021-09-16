import contextlib
import logging

import aiohttp

from .errors import ProviderFatalError, ProviderTemporaryError

TELEGRAM_API_URL = 'https://api.telegram.org'


class TelegramChat:
    def __init__(self, chat_id, bot_token, api_url=TELEGRAM_API_URL, timeout=5):
        self.chat_id = chat_id
        self._bot_token = bot_token
        self._bot_name = self._bot_token[:self._bot_token.find(":")]

        self._api_url = api_url
        self._bot_url = f'{self._api_url.rstrip("/")}/bot{self._bot_token}'
        self._timeout = timeout

        self._log = logging.getLogger(f'tgproxy.providers.telegram.bot{self._bot_name}.{self.chat_id}')

        self._http_timeout = aiohttp.ClientTimeout(total=timeout)
        self._http_client = None

    async def send_message(self, message):
        self._log.info(f'Send message {repr(message)}')
        await self._request(
            'sendMessage',
            request_data=dict(
                text=message.text,
                **message.options
            ),
        )

    @contextlib.asynccontextmanager
    async def session(self):
        async with aiohttp.ClientSession() as http_client:
            self._http_client = http_client
            yield self
            self._http_client = None

    async def _request(self, method, request_data):
        if not self._http_client:
            raise RuntimeError('Call requests with in session context manager')

        try:
            resp = await self._http_client.post(
                f'{self._bot_url}/{method}',
                data=dict(
                    chat_id=self.chat_id,
                    **request_data
                ),
                timeout=self._http_timeout,
            )
            return await self._process_response(resp)
        except Exception as e:
            raise ProviderFatalError(str(e))

    async def _process_response(self, response):
        if response.ok:
            return (response.status, await response.json())

        if response.status in [404, 400]:
            raise ProviderFatalError(f'Status: {response.status}. Body: {await response.text()}')

        raise ProviderTemporaryError(f'Status: {response.status}. Body: {await response.text()}')
