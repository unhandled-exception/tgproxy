import pytest

import tgproxy

TEST_CHANNELS = {
    'telegram://bot:token@chat_1/main/?timeout=100',
    'telegram://bot2:token2@chat_2/second',
}


@pytest.fixture
def cli(loop, aiohttp_client):
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
    assert resp.ok is True
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
    assert len(api._background_tasks) == len(TEST_CHANNELS)
    assert len(list(filter(lambda x: x.cancelled(), api._background_tasks))) == 0

    resp = await cli.get('/ping.html')
    # assert resp.ok is False
    assert await resp.json() == {
        'status': 'error',
        'message': 'Background workers canceled',
        'workers': {
            'telegram://bot2:***@chat_2/second': 'done',
            'telegram://bot:***@chat_1/main': 'done',
        },
    }


async def test_on_index_ok(cli):
    resp = await cli.get('/')
    assert resp.ok is True
    assert await resp.json() == {
        'status': 'success',
        'channels': {
            'main': 'telegram://bot:***@chat_1/main',
            'second': 'telegram://bot2:***@chat_2/second',
        },
    }
