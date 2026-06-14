"""Raw block device I/O with automatic strategy fallback.

Provides a pluggable I/O strategy chain for reading/writing raw block
devices and disk image files.

Layers (one file per layer):
  ``_strategies``  — Pluggable I/O strategy base class & helpers
  ``_direct_io``   — ``DirectIOStrategy``
  ``_backing_file`` — ``BackingFileStrategy``
  ``_dd``          — ``DDStrategy``
  ``_io``          — ``RawBlockIO`` (strategy chain)
"""

from rawblock_io._strategies import (
    IOStrategy,
    DirectIOStrategy,
    BackingFileStrategy,
    DDStrategy,
    BLOCK_SIZE,
    _block_align,
    _try_pread,
    _try_pwrite,
)
from rawblock_io._io import RawBlockIO
__all__ = [
    'IOStrategy',
    'DirectIOStrategy',
    'BackingFileStrategy',
    'DDStrategy',
    'BLOCK_SIZE',
    '_block_align',
    '_try_pread',
    '_try_pwrite',
    'RawBlockIO',
]
