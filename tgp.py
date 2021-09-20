#!/usr/bin/env python3

"""
A simple Telegram proxy

Start server:
pipenv run tgp.py telegram://bot:tok1@123/chat_1 telegram://bot:tok1@123/chat_2

API:
Get ping-status — GET http://localhost:5000/ping.html
Get channels list — GET http://localhost:5000/
Send messge POST http://localhost:5000/chat_1 (text="Message", parse_mode ...)
Get channel statistics GET http://localhost:5000/chat_1
"""

import argparse
import logging
import sys

import aiohttp

import tgproxy

DEFAULT_LOGGING_MODE = logging.INFO


class Args(argparse.ArgumentParser):
    def __init__(self):
        super().__init__(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.add_argument('channels_urls', nargs='+', help='List of channels uri. Formatting: telegram://bot:token@chat_id/channel_name?option=value')
        self.add_argument('-H', '--host', dest='host', default='localhost', help='Server hostname')
        self.add_argument('-P', '--port', dest='port', default='5000', help='Server port')
        self.add_argument('-d', '--debug', dest='debug', action='store_true', help='Debug mode')

    def error(self, message, exit_code=2):
        print(f'error: {message}\n', file=sys.stderr)
        self.print_help(file=sys.stderr)
        sys.exit(exit_code)


def build_channels_from_urls(urls):
    channels = dict()
    for ch in urls:
        ch = tgproxy.build_channel(ch)
        channels[ch.name] = ch
    return channels


def main():
    args = Args().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else DEFAULT_LOGGING_MODE,
        format='%(asctime)s:%(name)s:%(levelname)s:%(message)s',
    )
    app = tgproxy.APIApp(
        build_channels_from_urls(args.channels_urls),
    )
    aiohttp.web.run_app(
        app.serving_app(),
        host=args.host,
        port=args.port,
    )


if __name__ == '__main__':
    main()
