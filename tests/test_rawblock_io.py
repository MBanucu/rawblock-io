from rawblock_io import RawBlockIO, DirectIOStrategy, BackingFileStrategy

import os
import tempfile
import unittest


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

    def test_clear_cache(self):
        io = RawBlockIO(strategies=[BackingFileStrategy()])
        io.clear_cache('/dev/loop0')
        io.clear_cache()
