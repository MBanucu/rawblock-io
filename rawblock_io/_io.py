"""Raw block I/O — delegates to a chain of pluggable strategies."""

from rawblock_io._strategies import (
    IOStrategy,
    DirectIOStrategy,
    BackingFileStrategy,
    DDStrategy,
)


def _default_strategies() -> list[IOStrategy]:
    return [DirectIOStrategy(), BackingFileStrategy(), DDStrategy()]


class RawBlockIO:
    """Raw block I/O — delegates to a chain of pluggable strategies.

    Parameters
    ----------
    strategies
        Ordered list of ``IOStrategy`` instances. Defaults to
        ``[DirectIOStrategy(), BackingFileStrategy(), DDStrategy()]``
        on Linux; ``[DirectIOStrategy(), DDStrategy()]`` on macOS.
    """

    def __init__(self, strategies: list[IOStrategy] | None = None):
        self._strategies = strategies or _default_strategies()

    def clear_cache(self, device: str | None = None):
        for s in self._strategies:
            s.clear_cache(device)

    def read(self, device: str, offset: int, size: int) -> bytes:
        for s in self._strategies:
            result = s.read(device, offset, size)
            if result is not None:
                return result
        return b''

    def write(self, device: str, offset: int, data: bytes):
        for s in self._strategies:
            if s.write(device, offset, data):
                return
