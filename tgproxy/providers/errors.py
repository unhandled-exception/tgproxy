class ProviderError(Exception):
    pass


class ProviderFatalError(ProviderError):
    def __init__(self, source=None, *args, **kwargs):
        super().__init__(f"telegram fatal error: {source}" if source is not None else None, *args, **kwargs)


class ProviderTemporaryError(ProviderError):
    def __init__(self, source=None, *args, **kwargs):
        super().__init__(f"telegram temporary error: {source}" if source is not None else None, *args, **kwargs)
