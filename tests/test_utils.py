from urllib.parse import ParseResult

from tgproxy import utils


def test_parse_url(event_loop):
    parsed_url, options = utils.parse_url('telegram://bot:token@chat_1/channel_1?timeout=5&param1=value1')
    assert parsed_url == ParseResult(
        scheme='telegram',
        netloc='bot:token@chat_1',
        path='/channel_1',
        params='',
        query='timeout=5&param1=value1',
        fragment='',
    )
    assert options == {
        'param1': 'value1',
        'timeout': '5',
    }
