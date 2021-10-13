import pytest

import tgproxy


def test_build_telegram_channel(loop):
    channel = tgproxy.build_channel('telegram://bot2345:token12345@chat_1/channel_1?timeout=9999&param1=value1')
    assert isinstance(channel, tgproxy.channel.TelegramChannel)
    assert channel.name == 'channel_1'
    assert channel.send_banner_on_startup is True

    provider = channel.provider
    assert isinstance(provider, tgproxy.providers.TelegramChat)
    assert provider.chat_id == 'chat_1'
    assert provider.bot_token == 'bot2345:token12345'
    assert provider.timeout == 9999


def test_fetch_send_banner_on_startup_from_url(loop):
    channel = tgproxy.build_channel('telegram://bot2345:token12345@chat_1/channel_1?timeout=9999&param1=value1&send_banner_on_startup=0')
    assert isinstance(channel, tgproxy.channel.TelegramChannel)
    assert channel.name == 'channel_1'
    assert channel.send_banner_on_startup is False


def test_unknown_channel_type_raises_error(loop):
    with pytest.raises(tgproxy.errors.UnknownChannelType):
        tgproxy.build_channel('unknown://url')
