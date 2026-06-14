from unittest.mock import patch

from rawblock_io import BackingFileStrategy

import os
import tempfile
import unittest


class TestBackingFileStrategy(unittest.TestCase):
    def test_read_non_loop_device_returns_none(self):
        s = BackingFileStrategy()
        result = s.read('/dev/null', 0, 512)
        self.assertIsNone(result)

    def test_clear_cache(self):
        s = BackingFileStrategy()
        s.clear_cache()
        s.clear_cache('/dev/loop0')

    def setUp_bftmp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.write(b'\x00' * 4096)
        self.tmp.close()

    def tearDown_bftmp(self):
        os.unlink(self.tmp.name)

    @patch.object(BackingFileStrategy, '_resolve', return_value=None)
    def test_read_no_backing_returns_none(self, _mock):
        s = BackingFileStrategy()
        self.assertIsNone(s.read('/dev/loop0', 0, 512))

    @patch.object(BackingFileStrategy, '_resolve', return_value=None)
    def test_write_no_backing_returns_false(self, _mock):
        s = BackingFileStrategy()
        self.assertFalse(s.write('/dev/loop0', 0, b'data'))

    @patch('rawblock_io._backing_file.subprocess.run')
    def test_resolve_linux_cmd_success(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '/tmp/backing.img\n'
        mock_run.return_value.stderr = ''
        s = BackingFileStrategy()
        result = s._resolve_linux('/dev/loop0')
        self.assertEqual(result, '/tmp/backing.img')

    @patch('rawblock_io._backing_file.subprocess.run', side_effect=OSError)
    def test_resolve_linux_cmd_exception(self, _mock):
        s = BackingFileStrategy()
        self.assertIsNone(s._resolve_linux('/dev/loop0'))

    @patch('rawblock_io._backing_file.subprocess.run')
    @patch('rawblock_io._backing_file.plistlib.loads')
    def test_resolve_darwin_success(self, mock_plist, mock_run):
        mock_run.return_value.returncode = 0
        mock_plist.return_value = {
            'images': [{
                'image-path': '/tmp/test.dmg',
                'system-entities': [{'dev-entry': '/dev/disk3s1'}],
            }],
        }
        s = BackingFileStrategy()
        result = s._resolve_darwin('/dev/disk3s1')
        self.assertEqual(result, '/tmp/test.dmg')

    @patch('rawblock_io._backing_file.subprocess.run')
    def test_resolve_darwin_hdiutil_fails(self, mock_run):
        mock_run.return_value.returncode = 1
        s = BackingFileStrategy()
        self.assertIsNone(s._resolve_darwin('/dev/disk3s1'))

    @patch('rawblock_io._backing_file.subprocess.run')
    @patch('rawblock_io._backing_file.plistlib.loads')
    def test_resolve_darwin_image_not_dict(self, mock_plist, mock_run):
        mock_run.return_value.returncode = 0
        mock_plist.return_value = {'images': ['not-a-dict']}
        s = BackingFileStrategy()
        self.assertIsNone(s._resolve_darwin('/dev/disk3s1'))

    @patch('rawblock_io._backing_file.subprocess.run', side_effect=OSError)
    def test_resolve_darwin_exception(self, _mock):
        s = BackingFileStrategy()
        self.assertIsNone(s._resolve_darwin('/dev/disk3s1'))

    def test_read_write_with_backing(self):
        self.setUp_bftmp()
        try:
            s = BackingFileStrategy()
            with patch.object(s, '_resolve', return_value=self.tmp.name):
                result = s.read('/dev/loop0', 0, 512)
                self.assertIsNotNone(result)
                self.assertEqual(len(result), 512)

                ok = s.write('/dev/loop0', 0, b'TEST')
                self.assertTrue(ok)

                result = s.read('/dev/loop0', 0, 4)
                self.assertEqual(result, b'TEST')
        finally:
            self.tearDown_bftmp()
