import time


class AnyValue():
    def __eq__(self, value):
        return True


class NowTimeDeltaValue():
    def __init__(self, delta_sec=1.5):
        self._delta_sec = delta_sec
        self._last_time = None

    def __eq__(self, value):
        value = round(value)
        self._last_time = round(time.time())
        return (value - self._delta_sec < self._last_time < value + self._delta_sec)

    def __repr__(self):
        return f'{self.__class__.__name__}<{self._last_time}±{self._delta_sec}>'
