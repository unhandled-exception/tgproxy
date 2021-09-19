import asyncio
import re

import aiohttp
import pytest
import tenacity
from aioresponses import aioresponses

import tgproxy

from . import AnyValue

TEST_CHANNELS = {
    'telegram://bot:token@chat_1/main/?timeout=100',
    'telegram://bot2:token2@chat_2/second',
}
TEST_QUEUE_SIZE = 5


def assert_telegram_call(
    tc,
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
    assert tc[0][0] == method
    assert str(tc[0][1]) == f'https://api.telegram.org/bot{bot_token}/sendMessage'
    assert tc[1][0].kwargs['data'] == data


def assert_telegram_requests_count(m, count):
    assert len(list(m.requests.items())[0][1]) == count


@pytest.fixture
def cli(loop, aiohttp_client):
    tgproxy.queue.DEFAULT_QUEUE_MAXSIZE = TEST_QUEUE_SIZE
    tgproxy.providers.telegram.DEFAULT_RETRIES_OPTIONS = dict(
        stop=tenacity.stop_after_attempt(3),
    )

    app = tgproxy.APIApp(
        channels=dict(
            map(
                lambda x: (x.name, x),
                [tgproxy.build_channel(url) for url in TEST_CHANNELS],
            ),
        ),
    )
    serving_app = app.serving_app()
    serving_app['api'] = app
    return loop.run_until_complete(
        aiohttp_client(serving_app),
    )


async def test_ping_ok(cli):
    resp = await cli.get('/ping.html')
    assert resp.ok
    assert await resp.json() == {
        'status': 'success',
        'workers': {
            'telegram://bot2:***@chat_2/second': 'active',
            'telegram://bot:***@chat_1/main': 'active',
        },
    }


async def test_ping_fail(cli):
    api = cli.server.app['api']
    await api.stop_background_channels_tasks(cli.server.app)
    assert len(api.background_tasks) == len(TEST_CHANNELS)
    assert len(list(filter(lambda x: x.cancelled(), api.background_tasks))) == 0

    resp = await cli.get('/ping.html')
    assert await resp.json() == {
        'status': 'error',
        'message': 'Background workers canceled',
        'workers': {
            'telegram://bot2:***@chat_2/second': 'done',
            'telegram://bot:***@chat_1/main': 'done',
        },
    }
    assert not resp.ok


async def test_start_background_tasks(cli):
    bt = cli.server.app['api'].background_tasks
    assert len(bt) == 2
    assert [(t.get_name(), (not t.cancelled() and not t.done())) for t in bt]


async def test_on_index_ok(cli):
    resp = await cli.get('/')
    assert resp.ok
    assert await resp.json() == {
        'status': 'success',
        'channels': {
            'main': 'telegram://bot:***@chat_1/main',
            'second': 'telegram://bot2:***@chat_2/second',
        },
    }


async def test_channel_not_found(cli):
    resp = await cli.post('/not_found')
    assert await resp.json() == {
        'message': 'Channel "not_found" not found',
        'status': 'error',
    }
    assert not resp.ok


async def test_channel_isfull(cli):
    await cli.server.app['api'].stop_background_channels_tasks(cli.server.app['api'])
    assert tgproxy.queue.DEFAULT_QUEUE_MAXSIZE == TEST_QUEUE_SIZE

    for _ in range(TEST_QUEUE_SIZE):
        await cli.post('/main', data={'text': 'Message'})
    assert cli.server.app['api'].channels['main'].qsize() == TEST_QUEUE_SIZE

    resp = await cli.post('/main', data={'text': 'Message'})
    assert await resp.json() == {
        'message': f'Queue is full. Max size is {TEST_QUEUE_SIZE}',
        'status': 'error',
    }
    assert resp.status == 503


async def test_successful_send_message(cli):
    with aioresponses(passthrough=['http://127.0.0.1']) as m:
        m.post(
            re.compile(r'^https://api.telegram.org/bot'),
            status=200,
            payload=dict(),
        )
        resp = await cli.post(
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
        assert_telegram_call(
            list(m.requests.items())[0],
            data={
                'parse_mode': 'MarkdownV2',
                'text': 'Test message',
            },
        )

        assert cli.server.app['api'].channels['main'].qsize() == 0
        assert cli.server.app['api'].channels['main'].get_stat() == {
            'errors': 0,
            'last_error': None,
            'queued': 1,
            'sended': 1,
        }


async def test_no_reties_on_fatal_error(cli):
    with aioresponses(passthrough=['http://127.0.0.1']) as m:
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=400, payload=dict())
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=400, payload=dict())

        resp = await cli.post(
            '/main',
            data=dict(
                text='Test message',
                parse_mode='MarkdownV2',
            ),
        )
        assert resp.ok

        assert_telegram_requests_count(m, 1)
        assert cli.server.app['api'].channels['main'].qsize() == 0
        assert cli.server.app['api'].channels['main'].get_stat() == {
            'errors': 1,
            'last_error': 'Status: 400. Body: <NO BODY>',
            'queued': 1,
            'sended': 0,
        }


async def test_reties_on_temporary_error(cli):
    with aioresponses(passthrough=['http://127.0.0.1']) as m:
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=500, exception=aiohttp.ClientConnectionError())
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=500, payload=dict(message='bad response'))
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=200, payload=dict(message='sended'))
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=500, payload=dict(message='bad response'))

        resp = await cli.post(
            '/main',
            data=dict(
                text='Test message',
                parse_mode='MarkdownV2',
            ),
        )
        assert resp.ok

        await asyncio.sleep(1)
        assert_telegram_requests_count(m, 3)
        assert cli.server.app['api'].channels['main'].get_stat() == {
            'errors': 0,
            'last_error': None,
            'queued': 1,
            'sended': 1,
        }


async def test_channel_statistics(cli):
    with aioresponses(passthrough=['http://127.0.0.1']) as m:
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=200)
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=400, body='bad request')
        m.post(re.compile(r'^https://api.telegram.org/bot'), status=200)

        await cli.post('/main', data=dict(text='Test message'))
        await cli.post('/main', data=dict(text='Test message'))
        await cli.post('/main', data=dict(text='Test message'))

        resp = await cli.get('/main')

        await asyncio.sleep(1)
        assert await resp.json() == {
            'errors': 1,
            'last_error': 'Status: 400. Body: <NO BODY>',
            'queued': 3,
            'sended': 2,
            'status': 'success',
        }
        assert resp.ok
