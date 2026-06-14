from unittest.mock import patch, MagicMock

from rawblock_io import DDStrategy

import os
import tempfile
import unittest


class TestDDStrategy(unittest.TestCase):
    def test_read_nonexistent_returns_none(self):
        s = DDStrategy()
        result = s.read('/nonexistent_device_xyz', 0, 512)
        self.assertIsNone(result)

    def test_write_nonexistent_returns_false(self):
        s = DDStrategy()
        result = s.write('/nonexistent_device_xyz', 0, b'data')
        self.assertFalse(result)

    @patch('rawblock_io._dd.subprocess.run')
    def test_read_success(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b'\x00' * 512
        s = DDStrategy()
        result = s.read('/dev/loop0', 0, 512)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 512)

    @patch('rawblock_io._dd.subprocess.run')
    def test_read_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        s = DDStrategy()
        result = s.read('/dev/loop0', 0, 512)
        self.assertIsNone(result)

    @patch('rawblock_io._dd.subprocess.run')
    @patch('rawblock_io._dd.tempfile.NamedTemporaryFile')
    def test_write_blocks(self, mock_tmpfile, mock_run):
        mock_file = MagicMock()
        mock_file.name = '/tmp/dd_write_test'
        mock_tmpfile.return_value.__enter__.return_value = mock_file
        mock_run.return_value.returncode = 0
        s = DDStrategy()
        result = s._write_blocks('/dev/loop0', 0, b'\x00' * 512)
        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch.object(DDStrategy, '_write_blocks', return_value=True)
    def test_write_aligned(self, mock_wb):
        s = DDStrategy()
        result = s.write('/dev/loop0', 0, b'\x00' * 512)
        self.assertTrue(result)
        mock_wb.assert_called_once()

    @patch.object(DDStrategy, '_write_blocks', return_value=True)
    @patch.object(DDStrategy, 'read', return_value=b'\x00' * 512)
    def test_write_misaligned(self, mock_read, mock_wb):
        s = DDStrategy()
        result = s.write('/dev/loop0', 100, b'HELLO')
        self.assertTrue(result)
        mock_read.assert_called_once()
        mock_wb.assert_called_once()

    @patch.object(DDStrategy, 'read', return_value=None)
    def test_write_misaligned_read_fails(self, mock_read):
        s = DDStrategy()
        result = s.write('/dev/loop0', 100, b'HELLO')
        self.assertFalse(result)

    @patch('rawblock_io._dd.subprocess.run', side_effect=FileNotFoundError)
    def test_read_file_not_found(self, _mock):
        s = DDStrategy()
        self.assertIsNone(s.read('/dev/loop0', 0, 512))

    @patch('rawblock_io._dd.subprocess.run', side_effect=FileNotFoundError)
    def test_write_file_not_found(self, _mock):
        s = DDStrategy()
        self.assertFalse(s.write('/dev/loop0', 0, b'\x00' * 512))

    @patch('rawblock_io._dd.subprocess.run')
    def test_write_blocks_double_fail(self, mock_run):
        mock_run.return_value.returncode = 1
        s = DDStrategy()
        self.assertFalse(s._write_blocks('/dev/loop0', 0, b'\x00' * 512))

    def test_read_real_file(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b'\x00' * 512)
        tmp.close()
        try:
            s = DDStrategy()
            data = s.read(tmp.name, 0, 512)
            self.assertIsNotNone(data)
            self.assertEqual(len(data), 512)
        finally:
            os.unlink(tmp.name)

    def test_write_aligned_real_file(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b'\x00' * 1024)
        tmp.close()
        try:
            s = DDStrategy()
            ok = s.write(tmp.name, 512, b'\xFF' * 512)
            self.assertTrue(ok)

            with open(tmp.name, 'rb') as f:
                before = f.read(512)
                after = f.read(512)
            self.assertEqual(before, b'\x00' * 512)
            self.assertEqual(after, b'\xFF' * 512)
        finally:
            os.unlink(tmp.name)

    def test_write_misaligned_real_file(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b'\x00' * 1024)
        tmp.close()
        try:
            s = DDStrategy()
            ok = s.write(tmp.name, 100, b'HELLO')
            self.assertTrue(ok)

            with open(tmp.name, 'rb') as f:
                data = f.read()
            self.assertEqual(data[0:100], b'\x00' * 100)
            self.assertEqual(data[100:105], b'HELLO')
            self.assertEqual(data[105:512], b'\x00' * 407)
        finally:
            os.unlink(tmp.name)
