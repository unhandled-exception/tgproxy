class UnknownChannelType(Exception):
    pass


class BaseError(Exception):
    http_status = 500


class QueueFull(BaseError):
    http_status = 503


class ChannelNotFound(BaseError):
    http_status = 404
