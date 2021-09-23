import contextlib
import logging

import aiohttp
import tenacity

from .errors import ProviderFatalError, ProviderTemporaryError

TELEGRAM_API_URL = 'https://api.telegram.org'
DEFAULT_LOGGER_NAME = 'tgproxy.providers.telegram'

DEFAULT_RETRIES_OPTIONS = dict(
    stop=tenacity.stop_after_attempt(5),
    wait=tenacity.wait_random_exponential(
        multiplier=1,
        min=2,
        max=32,
    ),
)


class TelegramChat:
    def __init__(self, chat_id, bot_token, api_url=TELEGRAM_API_URL, timeout=5, logger_name=DEFAULT_LOGGER_NAME, **kwargs):
        self.chat_id = chat_id
        self.bot_token = bot_token
        self.bot_name = self.bot_token[:self.bot_token.find(":")]

        self.api_url = api_url
        self.bot_url = f'{self.api_url.rstrip("/")}/bot{self.bot_token}'
        self.timeout = timeout

        self._log = logging.getLogger(f'{logger_name}.bot{self.bot_name}.{self.chat_id}')

        self.http_timeout = aiohttp.ClientTimeout(total=self.timeout)
        self._http_client = None

        self._retries_options = dict(
            **DEFAULT_RETRIES_OPTIONS,
            retry=tenacity.retry_if_exception_type(ProviderTemporaryError),
            after=tenacity.after_log(self._log, logging.INFO),
        )

    async def send_message(self, message):
        self._log.info(f'Send message {message}')
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

        @tenacity.retry(
            reraise=True,
            **self._retries_options
        )
        async def _call_request_with_retries():
            try:
                resp = await self._http_client.post(
                    f'{self.bot_url}/{method}',
                    data=dict(
                        chat_id=self.chat_id,
                        **request_data
                    ),
                    timeout=self.http_timeout,
                    allow_redirects=False,
                )
                return await self._process_response(resp)
            except (aiohttp.ClientConnectionError, aiohttp.ClientResponseError) as e:
                raise ProviderTemporaryError(str(e))
            except ProviderTemporaryError:
                raise
            except Exception as e:
                raise ProviderFatalError(str(e))

        return await _call_request_with_retries()

    async def _process_response(self, response):
        if response.ok:
            return (response.status, await response.json())

        resp_text = '<NO BODY>'
        try:
            resp_text = await response.text()
        except aiohttp.ClientConnectionError:
            pass

        if response.status in [404, 400]:
            raise ProviderFatalError(f'Status: {response.status}. Body: {resp_text}')

        raise ProviderTemporaryError(f'Status: {response.status}. Body: {resp_text}')
