import logging

import aiohttp

TELEGRAM_API_URL = 'https://api.telegram.org'


class ProviderFatalError(Exception):
    pass


class ProviderTemporaryError(Exception):
    pass


class TelegramChat:
    def __init__(self, chat_id, bot_token, api_url=TELEGRAM_API_URL, timeout=20):
        self.chat_id = chat_id
        self._bot_token = bot_token
        self._bot_name = self._bot_token[:self._bot_token.find(":")]

        self._api_url = api_url
        self._bot_url = f'{self._api_url.rstrip("/")}/bot{self._bot_token}'
        self._timeout = timeout

        self._log = logging.getLogger(f'tgproxy.providers.telegram.bot{self._bot_name}.{self.chat_id}')

        self.__session = None

    @property
    def _session(self):
        if not self.__session:
            self.__session = aiohttp.ClientSession()
        return self.__session

    async def _request(self, method, request_data):
        resp = await self._session.post(
            f'{self._bot_url}/{method}',
            data=dict(
                chat_id=self.chat_id,
                **request_data
            ),
        )
        return await self.process_response(resp)

    async def _process_response(self, response):
        if response.ok:
            return (response.status, await response.json())

        if response.status in [404, 400]:
            raise ProviderFatalError(f'Status: {response.status}. Body: {await response.text()}')

        raise ProviderTemporaryError(f'Status: {response.status}. Body: {await response.text()}')

    async def send_message(self, message):
        self._log.info(f'Send message {repr(message)}')
        await self._request(
            'sendMessage',
            request_data=dict(
                text=message.text,
                **message.options
            ),
        )
