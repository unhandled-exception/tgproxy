import functools
import urllib.parse


@functools.cache
def parse_url(url):
    parsed_url = urllib.parse.urlparse(url)
    options = dict()
    if parsed_url.query:
        options = dict(
            urllib.parse.parse_qsl(parsed_url.query),
        )
    return (parsed_url, options)
