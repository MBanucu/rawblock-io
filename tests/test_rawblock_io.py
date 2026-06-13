"""Unit tests for rawblock-io — no sudo, no loop devices required."""

import os
import tempfile
import unittest

from rawblock_io import (
    IOStrategy,
    DirectIOStrategy,
    BackingFileStrategy,
    DDStrategy,
    RawBlockIO,
    resolve_device,
    resolve_mount_point,
    BLOCK_SIZE,
    _block_align,
    _try_pread,
    _try_pwrite,
)


class TestBlockAlign(unittest.TestCase):
    def test_aligned_offset(self):
        aligned, total, skip = _block_align(512, 512)
        self.assertEqual(aligned, 512)
        self.assertEqual(total, 512)
        self.assertEqual(skip, 0)

    def test_unaligned_offset(self):
        aligned, total, skip = _block_align(100, 200)
        self.assertEqual(aligned, 0)
        self.assertEqual(total, 512)
        self.assertEqual(skip, 100)

    def test_cross_block_boundary(self):
        aligned, total, skip = _block_align(400, 200)
        self.assertEqual(aligned, 0)
        self.assertEqual(total, 1024)
        self.assertEqual(skip, 400)


class TestDirectIOStrategy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.write(b'\x00' * 4096)
        self.tmp.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_read_write(self):
        s = DirectIOStrategy()
        data = s.read(self.tmp.name, 0, 512)
        self.assertEqual(len(data), 512)

        written = s.write(self.tmp.name, 64, b'HELLO')
        self.assertTrue(written)

        data = s.read(self.tmp.name, 64, 5)
        self.assertEqual(data, b'HELLO')

    def test_read_nonexistent(self):
        s = DirectIOStrategy()
        data = s.read('/nonexistent/rawblock_io_test', 0, 512)
        self.assertIsNone(data)


class TestRawBlockIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.write(b'\x00' * 4096)
        self.tmp.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_read_write_chain(self):
        io = RawBlockIO()
        data = io.read(self.tmp.name, 0, 512)
        self.assertEqual(len(data), 512)

        io.write(self.tmp.name, 128, b'WORLD')
        data = io.read(self.tmp.name, 128, 5)
        self.assertEqual(data, b'WORLD')

    def test_custom_strategies(self):
        io = RawBlockIO(strategies=[DirectIOStrategy()])
        data = io.read(self.tmp.name, 0, 512)
        self.assertEqual(len(data), 512)

    def test_read_returns_empty_on_failure(self):
        io = RawBlockIO()
        data = io.read('/nonexistent/path', 0, 512)
        self.assertEqual(data, b'')


class TestIOStrategyABC(unittest.TestCase):
    def test_cannot_instantiate_abc(self):
        with self.assertRaises(TypeError):
            IOStrategy()  # type: ignore[abstract]


class TestHelperFunctions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.write(b'\x00' * 4096)
        self.tmp.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_try_pread_try_pwrite(self):
        data = _try_pread(self.tmp.name, 0, 512)
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 512)

        ok = _try_pwrite(self.tmp.name, 0, b'TEST')
        self.assertTrue(ok)

        data = _try_pread(self.tmp.name, 0, 4)
        self.assertEqual(data, b'TEST')

    def test_block_size_constant(self):
        self.assertEqual(BLOCK_SIZE, 512)


class TestBackingFileStrategy(unittest.TestCase):
    def test_read_non_loop_device_returns_none(self):
        s = BackingFileStrategy()
        result = s.read('/dev/null', 0, 512)
        self.assertIsNone(result)

    def test_clear_cache(self):
        s = BackingFileStrategy()
        s.clear_cache()
        s.clear_cache('/dev/loop0')


class TestDDStrategy(unittest.TestCase):
    def test_read_nonexistent_returns_none(self):
        s = DDStrategy()
        result = s.read('/nonexistent_device_xyz', 0, 512)
        self.assertIsNone(result)

    def test_write_nonexistent_returns_false(self):
        s = DDStrategy()
        result = s.write('/nonexistent_device_xyz', 0, b'data')
        self.assertFalse(result)


class TestResolve(unittest.TestCase):
    def test_resolve_device_returns_something_for_root(self):
        dev = resolve_device('/')
        self.assertIsNotNone(dev)
        self.assertTrue(dev.startswith('/dev/') or os.path.isfile(dev),
                        f'Unexpected device: {dev}')

    def test_resolve_mount_point_returns_something_for_tmp(self):
        mp = resolve_mount_point('/tmp')
        self.assertIsNotNone(mp)
        self.assertTrue(mp.startswith('/'),
                        f'Unexpected mount point: {mp}')

    def test_resolve_device_nonexistent_returns_none(self):
        try:
            dev = resolve_device('/nonexistent/path/xyz')
        except OSError:
            dev = None
        self.assertIsNone(dev)


if __name__ == '__main__':
    unittest.main()
