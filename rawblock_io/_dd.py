"""DD strategy — falls back to ``dd`` with automatic ``sudo`` elevation."""

import subprocess
import tempfile

from rawblock_io._strategies import IOStrategy, BLOCK_SIZE, _block_align


class DDStrategy(IOStrategy):
    """Use ``dd`` for raw block I/O, elevating to ``sudo`` on failure.

    Each operation first tries plain ``dd``.  If the exit code is
    non-zero (e.g. permission denied on a block device) the command
    is retried with ``sudo dd``.
    """

    def read(self, device: str, offset: int, size: int) -> bytes | None:
        try:
            aligned_off, total, skip = _block_align(offset, size)
            args = [
                f'if={device}', f'bs={BLOCK_SIZE}',
                f'skip={aligned_off // BLOCK_SIZE}',
                f'count={total // BLOCK_SIZE}',
            ]
            for prefix in (['dd'], ['sudo', 'dd']):
                r = subprocess.run(
                    prefix + args, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL)
                if r.returncode == 0:
                    return r.stdout[skip:skip + size]
            return None
        except FileNotFoundError:
            return None

    def write(self, device: str, offset: int, data: bytes) -> bool:
        try:
            aligned_off, total, skip = _block_align(offset, len(data))
            if skip == 0 and total == len(data):
                return self._write_blocks(device, aligned_off, data)
            buf = self.read(device, aligned_off, total)
            if buf is None or len(buf) < total:
                return False
            buf = bytearray(buf)
            buf[skip:skip + len(data)] = data
            return self._write_blocks(device, aligned_off, bytes(buf))
        except FileNotFoundError:
            return False

    def _write_blocks(self, device: str, offset: int, data: bytes) -> bool:
        with tempfile.NamedTemporaryFile() as tf:
            tf.write(data)
            tf.flush()
            args = [
                f'if={tf.name}', f'of={device}',
                f'bs={BLOCK_SIZE}',
                f'seek={offset // BLOCK_SIZE}',
                f'count={len(data) // BLOCK_SIZE}',
                'conv=fsync',
            ]
            for prefix in (['dd'], ['sudo', 'dd']):
                r = subprocess.run(
                    prefix + args, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL)
                if r.returncode == 0:
                    return True
        return False
