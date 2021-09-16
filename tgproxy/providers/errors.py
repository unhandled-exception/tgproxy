class ProviderError(Exception):
    pass


class ProviderFatalError(ProviderError):
    pass


class ProviderTemporaryError(ProviderError):
    pass
