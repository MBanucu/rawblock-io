"""Unit tests for rawblock-io — no sudo, no loop devices required."""

import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import rawblock_io

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
from rawblock_io._resolve import _df_output


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

    def test_clear_cache(self):
        io = RawBlockIO(strategies=[BackingFileStrategy()])
        io.clear_cache('/dev/loop0')
        io.clear_cache()


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

    @patch('rawblock_io._strategies.os.pwrite', side_effect=OSError)
    def test_try_pwrite_os_error(self, _mock):
        self.assertFalse(_try_pwrite('/nonexistent/path', 0, b'data'))


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
        """Integration: dd reads from a regular file."""
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
        """Integration: dd writes to a regular file."""
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
        """Integration: dd read-modify-write on a regular file."""
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


class TestResolveLinux(unittest.TestCase):
    @patch('rawblock_io._resolve_linux.os.readlink', return_value='../../devices/pci0000:00/0000:00:1f.2/ata1/host0/target0:0:0/0:0:0:0/block/sda/sda1')
    @patch('builtins.open')
    @patch('rawblock_io._resolve_linux.os.stat')
    def test_resolve_device_fallback_sysfs(self, mock_stat, mock_open, _mock_readlink):
        mock_stat.return_value.st_dev = os.makedev(8, 1)
        mock_file = MagicMock()
        mock_file.__iter__.return_value = iter([
            'major minor #blocks name\n',
            '   1       0   819200 sda\n',
        ])
        mock_open.return_value.__enter__.return_value = mock_file
        from rawblock_io._resolve_linux import resolve_device
        dev = resolve_device('/')
        self.assertEqual(dev, '/dev/sda1')

    @patch('rawblock_io._resolve_linux.os.readlink', side_effect=OSError)
    @patch('builtins.open')
    @patch('rawblock_io._resolve_linux.os.stat')
    def test_resolve_device_fallback_sysfs_fails(self, mock_stat, mock_open, _mock_readlink):
        mock_stat.return_value.st_dev = os.makedev(8, 1)
        mock_file = MagicMock()
        mock_file.__iter__.return_value = iter([
            'major minor #blocks name\n',
            '   1       0   819200 sda\n',
        ])
        mock_open.return_value.__enter__.return_value = mock_file
        from rawblock_io._resolve_linux import resolve_device
        dev = resolve_device('/')
        self.assertIsNone(dev)

    @patch('rawblock_io._resolve_linux.subprocess.run')
    def test_resolve_mount_point_findmnt_fails(self, mock_run):
        mock_run.return_value.returncode = 1
        from rawblock_io._resolve_linux import resolve_mount_point
        self.assertIsNone(resolve_mount_point('/'))


class TestResolveDarwin(unittest.TestCase):
    @patch('rawblock_io._resolve_darwin.plistlib.loads')
    @patch('rawblock_io._resolve_darwin.subprocess.run')
    @patch('rawblock_io._resolve_darwin._df_output')
    def test_resolve_device_returns_backing(self, mock_df, mock_run, _mock_plist):
        mock_df.return_value = ('/dev/disk3s1', '/Volumes/MyDisk', 'hfs')
        mock_run.return_value.returncode = 0
        with patch.object(rawblock_io._resolve_darwin, '_resolve_backing_file_darwin',
                          return_value='/tmp/test.dmg'):
            with patch('os.path.isfile', return_value=True):
                from rawblock_io._resolve_darwin import resolve_device
                dev = resolve_device('/Volumes/MyDisk')
                self.assertEqual(dev, '/tmp/test.dmg')

    @patch('rawblock_io._resolve_darwin.subprocess.run')
    def test_resolve_backing_file_hdiutil_fails(self, mock_run):
        mock_run.return_value.returncode = 1
        from rawblock_io._resolve_darwin import _resolve_backing_file_darwin
        self.assertIsNone(_resolve_backing_file_darwin('/dev/disk3s1'))

    @patch('rawblock_io._resolve_darwin.plistlib.loads')
    @patch('rawblock_io._resolve_darwin.subprocess.run')
    def test_resolve_backing_file_image_not_dict(self, mock_run, mock_plist):
        mock_run.return_value.returncode = 0
        mock_plist.return_value = {'images': ['not-a-dict', {}]}
        from rawblock_io._resolve_darwin import _resolve_backing_file_darwin
        self.assertIsNone(_resolve_backing_file_darwin('/dev/disk3s1'))

    @patch('rawblock_io._resolve_darwin.plistlib.loads')
    @patch('rawblock_io._resolve_darwin.subprocess.run')
    def test_resolve_backing_file_no_match(self, mock_run, mock_plist):
        mock_run.return_value.returncode = 0
        mock_plist.return_value = {
            'images': [{
                'image-path': '/other.dmg',
                'system-entities': [{'dev-entry': '/dev/disk4s1'}],
            }],
        }
        from rawblock_io._resolve_darwin import _resolve_backing_file_darwin
        self.assertIsNone(_resolve_backing_file_darwin('/dev/disk3s1'))

    @patch('rawblock_io._resolve_darwin.subprocess.run', side_effect=OSError)
    def test_resolve_backing_file_exception(self, _mock):
        from rawblock_io._resolve_darwin import _resolve_backing_file_darwin
        self.assertIsNone(_resolve_backing_file_darwin('/dev/disk3s1'))

    @patch('rawblock_io._resolve_darwin.plistlib.loads')
    @patch('rawblock_io._resolve_darwin.subprocess.run')
    def test_resolve_backing_file_success(self, mock_run, mock_plist):
        mock_run.return_value.returncode = 0
        mock_plist.return_value = {
            'images': [{
                'image-path': '/tmp/test.dmg',
                'system-entities': [{'dev-entry': '/dev/disk3s1'}],
            }],
        }
        from rawblock_io._resolve_darwin import _resolve_backing_file_darwin
        result = _resolve_backing_file_darwin('/dev/disk3s1')
        self.assertEqual(result, '/tmp/test.dmg')

    @patch('rawblock_io._resolve_darwin._df_output', return_value=None)
    def test_resolve_device_df_returns_none(self, _mock_df):
        from rawblock_io._resolve_darwin import resolve_device
        self.assertIsNone(resolve_device('/tmp'))

    @patch('rawblock_io._resolve_darwin._resolve_backing_file_darwin', return_value=None)
    @patch('rawblock_io._resolve_darwin._df_output')
    def test_resolve_device_no_backing(self, mock_df, _mock_backing):
        mock_df.return_value = ('/dev/disk3s1', '/Volumes/MyDisk', 'hfs')
        from rawblock_io._resolve_darwin import resolve_device
        dev = resolve_device('/Volumes/MyDisk')
        self.assertEqual(dev, '/dev/disk3s1')

    @patch('rawblock_io._resolve_darwin._df_output')
    def test_resolve_mount_point(self, mock_df):
        mock_df.return_value = ('/dev/disk3s1', '/Volumes/MyDisk', 'hfs')
        from rawblock_io._resolve_darwin import resolve_mount_point
        mp = resolve_mount_point('/Volumes/MyDisk')
        self.assertEqual(mp, '/Volumes/MyDisk')

    @patch('rawblock_io._resolve_darwin._df_output', return_value=None)
    def test_resolve_mount_point_df_returns_none(self, _mock_df):
        from rawblock_io._resolve_darwin import resolve_mount_point
        self.assertIsNone(resolve_mount_point('/Volumes/MyDisk'))


class TestDfOutput(unittest.TestCase):
    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Darwin')
    def test_darwin_df_fails(self, mock_run):
        mock_run.return_value.returncode = 1
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Darwin')
    def test_darwin_df_few_lines(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = 'header\n'
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Darwin')
    def test_darwin_df_few_parts(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = 'Filesystem  Size\n/dev/disk1 1G\n'
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Darwin')
    def test_darwin_df_stat_fails(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=(
                'Filesystem   512-blocks  Mounted on\n'
                '/dev/disk1s1 489620264   /\n'
            )),
            MagicMock(returncode=1, stdout=''),
        ]
        result = _df_output('/')
        self.assertEqual(result, ('/dev/disk1s1', '/', ''))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Darwin')
    def test_darwin_df_success(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=(
                'Filesystem   512-blocks  Mounted on\n'
                '/dev/disk1s1 489620264   /\n'
            )),
            MagicMock(returncode=0, stdout='apfs\n'),
        ]
        result = _df_output('/')
        self.assertEqual(result, ('/dev/disk1s1', '/', 'apfs'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Linux')
    def test_linux_df_fails(self, mock_run):
        mock_run.return_value.returncode = 1
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Linux')
    def test_linux_df_few_lines(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = 'header\n'
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Linux')
    def test_linux_df_few_cols(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = 'header\ncol1 col2\n'
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Linux')
    def test_linux_df_success(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            'fstype target source\n'
            'ext4   /      /dev/sda1\n'
        )
        result = _df_output('/')
        self.assertEqual(result, ('/dev/sda1', '/', 'ext4'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Linux')
    def test_subprocess_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Linux')
    def test_subprocess_os_error(self, mock_run):
        mock_run.side_effect = OSError
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Linux')
    def test_subprocess_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(['df', '/'], 5)
        self.assertIsNone(_df_output('/'))

    @patch('rawblock_io._resolve.subprocess.run')
    @patch('rawblock_io._resolve.SYSTEM', 'Darwin')
    def test_darwin_subprocess_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        self.assertIsNone(_df_output('/'))

    def test_df_output_with_real_path(self):
        result = _df_output('/')
        self.assertIsNotNone(result)
        dev, mp, fstype = result
        self.assertIsInstance(dev, str)
        self.assertIsInstance(mp, str)
        self.assertIsInstance(fstype, str)


if __name__ == '__main__':
    unittest.main()
