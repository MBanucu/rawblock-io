from unittest.mock import patch

from rawblock_io import IOStrategy, BLOCK_SIZE, _block_align, _try_pread, _try_pwrite

import os
import tempfile
import unittest


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

    @patch('rawblock_io._strategies.os.pwrite', side_effect=OSError)
    def test_try_pwrite_os_error(self, _mock):
        self.assertFalse(_try_pwrite('/nonexistent/path', 0, b'data'))


class TestIOStrategyABC(unittest.TestCase):
    def test_cannot_instantiate_abc(self):
        with self.assertRaises(TypeError):
            IOStrategy()  # type: ignore[abstract]
