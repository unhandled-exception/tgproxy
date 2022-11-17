import asyncio
import re
from unittest import mock

import aiohttp
import pytest
import tenacity
from aioresponses import aioresponses

import tgproxy

from . import AnyValue, NowTimeDeltaValue

TEST_CHANNELS = {
    'telegram://bot:token@chat_1/main/?timeout=100',
    'telegram://bot2:token2@chat_2/second',
}
TEST_QUEUE_SIZE = 5
TEST_PASSTHROUGH_SERVERS = ['http://127.0.0.1', 'http://127.0.1.1']


def fetch_request_from_mock(m, item=0):
    return list(m.requests.items())[item]


def assert_telegram_request(
    request,
    method='POST',
    bot_token='bot:token',
    data=None,
):
    data = dict(
        **{
            'chat_id': 'chat_1',
            'disable_notifications': 0,
            'disable_web_page_preview': 0,
        },
        **data
    )
    assert request[0][0] == method
    assert str(request[0][1]) == f'https://api.telegram.org/bot{bot_token}/sendMessage'
    assert request[1][0].kwargs['data'] == data


def assert_telegram_requests_count(m, count):
    assert len(fetch_request_from_mock(m)[1]) == count


@pytest.fixture
def sut(event_loop, aiohttp_client):
    tgproxy.queue.DEFAULT_QUEUE_MAXSIZE = TEST_QUEUE_SIZE
    tgproxy.providers.telegram.DEFAULT_RETRIES_OPTIONS = dict(
        stop=tenacity.stop_after_attempt(3),
    )

    api = tgproxy.HttpAPI(
        channels=dict(
            map(
                lambda x: (x.name, x),
                [tgproxy.build_channel(url, send_banner_on_startup=False) for url in TEST_CHANNELS],
            ),
        ),
    )
    api.app['api'] = api
    return event_loop.run_until_complete(
        aiohttp_client(api.app),
    )


@pytest.mark.asyncio
async def test_ping_ok(sut):
    resp = await sut.get('/ping.html')
    assert resp.ok
    assert await resp.json() == {
        'status': 'success',
        'workers': {
            'telegram://bot2:***@chat_2/second': 'active',
            'telegram://bot:***@chat_1/main?timeout=100': 'active',
        },
    }


@pytest.mark.asyncio
async def test_ping_fail(sut):
    api = sut.server.app['api']
    await api.stop_background_channels_tasks(sut.server.app)
    assert len(api.background_tasks) == len(TEST_CHANNELS)
    assert len(list(filter(lambda x: x.cancelled(), api.background_tasks))) == 0

    resp = await sut.get('/ping.html')
    assert await resp.json() == {
        'status': 'error',
        'message': 'Background workers canceled',
        'workers': {
            'telegram://bot2:***@chat_2/second': 'done',
            'telegram://bot:***@chat_1/main?timeout=100': 'done',
        },
    }
    assert not resp.ok


@pytest.mark.asyncio
async def test_start_background_tasks(sut):
    bt = sut.server.app['api'].background_tasks
    assert len(bt) == 2
    assert all([(not t.cancelled() and not t.done()) for t in bt])


@pytest.mark.asyncio
async def test_on_index_ok(sut):
    resp = await sut.get('/')
    assert resp.ok
    assert await resp.json() == {
        'status': 'success',
        'channels': {
            'main': 'telegram://bot:***@chat_1/main?timeout=100',
            'second': 'telegram://bot2:***@chat_2/second',
        },
    }


@pytest.mark.asyncio
async def test_channel_not_found(sut):
    resp = await sut.post('/not_found')
    assert await resp.json() == {
        'message': 'Channel "not_found" not found',
        'status': 'error',
    }
    assert resp.status == 404


@pytest.mark.asyncio
async def test_channel_isfull(sut):
    await sut.server.app['api'].stop_background_channels_tasks(sut.server.app['api'])
    assert tgproxy.queue.DEFAULT_QUEUE_MAXSIZE == TEST_QUEUE_SIZE

    for _ in range(TEST_QUEUE_SIZE):
        await sut.post('/main', data={'text': 'Message'})
    assert sut.server.app['api'].channels['main'].qsize() == TEST_QUEUE_SIZE

    resp = await sut.post('/main', data={'text': 'Message'})
    assert await resp.json() == {
        'message': f'Queue is full. Max size is {TEST_QUEUE_SIZE}',
        'status': 'error',
    }
    assert resp.status == 503


@pytest.mark.asyncio
async def test_successful_send_message(sut):
    with aioresponses(passthrough=TEST_PASSTHROUGH_SERVERS) as m:
        m.post(
            re.compile(r'^https://api\.telegram\.org/bot'),
            status=200,
            payload=dict(),
        )
        resp = await sut.post(
            '/main',
            data=dict(
                text='Test message',
                parse_mode='MarkdownV2',
            ),
        )
        assert resp.ok
        assert await resp.json() == {
            'request_id': AnyValue(),
            'status': 'success',
        }

        assert_telegram_requests_count(m, 1)
        assert_telegram_request(
            fetch_request_from_mock(m),
            data={
                'parse_mode': 'MarkdownV2',
                'text': 'Test message',
            },
        )

        assert sut.server.app['api'].channels['main'].qsize() == 0
        assert sut.server.app['api'].channels['main'].stat() == {
            'errors': 0,
            'queued': 1,
            'sended': 1,
            'last_sended_at': NowTimeDeltaValue(),
        }


@pytest.mark.asyncio
async def test_no_reties_on_fatal_error(sut):
    with aioresponses(passthrough=TEST_PASSTHROUGH_SERVERS) as m:
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=400, payload=dict())
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=400, payload=dict())

        resp = await sut.post(
            '/main',
            data=dict(
                text='Test message',
                parse_mode='MarkdownV2',
            ),
        )
        assert resp.ok

        assert_telegram_requests_count(m, 1)
        assert sut.server.app['api'].channels['main'].qsize() == 0
        assert sut.server.app['api'].channels['main'].stat() == {
            'errors': 1,
            'last_error': 'Status: 400. Body: {}',
            'last_error_at': NowTimeDeltaValue(),
            'queued': 1,
            'sended': 0,
        }


@pytest.mark.asyncio
async def test_reties_on_temporary_error(sut):
    with aioresponses(passthrough=TEST_PASSTHROUGH_SERVERS) as m:
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=500, exception=aiohttp.ClientConnectionError())
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=500, payload=dict(message='bad response'))
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=200, payload=dict(message='sended'))
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=500, payload=dict(message='bad response'))

        resp = await sut.post(
            '/main',
            data=dict(
                text='Test message',
                parse_mode='MarkdownV2',
            ),
        )
        assert resp.ok

        await asyncio.sleep(1)
        assert_telegram_requests_count(m, 3)
        assert sut.server.app['api'].channels['main'].stat() == {
            'errors': 0,
            'queued': 1,
            'sended': 1,
            'last_sended_at': NowTimeDeltaValue(),
        }


@pytest.mark.asyncio
async def test_channel_statistics(sut):
    with aioresponses(passthrough=TEST_PASSTHROUGH_SERVERS) as m:
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=200)
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=400, body='bad request')
        m.post(re.compile(r'^https://api\.telegram\.org/bot'), status=200)

        await sut.post('/main', data=dict(text='Test message'))
        await sut.post('/main', data=dict(text='Test message'))
        await sut.post('/main', data=dict(text='Test message'))

        resp = await sut.get('/main')

        await asyncio.sleep(1)
        assert await resp.json() == {
            'errors': 1,
            'last_error': 'Status: 400. Body: bad request',
            'last_error_at': NowTimeDeltaValue(),
            'queued': 3,
            'sended': 2,
            'last_sended_at': NowTimeDeltaValue(),
            'status': 'success',
        }
        assert resp.ok


@mock.patch('socket.gethostname', lambda: 'host.test.local')
@pytest.mark.asyncio
async def test_send_banner_on_startup(sut):
    await sut.server.app['api'].stop_background_channels_tasks(sut.server.app['api'])

    with aioresponses(passthrough=TEST_PASSTHROUGH_SERVERS) as m:
        sut.server.app['api'].channels['main'].send_banner_on_startup = True
        await sut.server.app['api'].start_background_channels_tasks(sut.server.app['api'])
        await asyncio.sleep(1)
        assert_telegram_request(
            fetch_request_from_mock(m),
            data={
                'text': 'Start tgproxy on host.test.local',
            },
        )
