from rawblock_io import DirectIOStrategy

import os
import tempfile
import unittest


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
