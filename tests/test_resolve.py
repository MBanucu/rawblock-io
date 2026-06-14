from unittest.mock import patch, MagicMock

from rawblock_io import resolve_device, resolve_mount_point, resolve
from rawblock_io._resolve import _df_output

import rawblock_io

import os
import shutil
import subprocess
import tempfile
import unittest


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


class TestUnifiedResolve(unittest.TestCase):
    def test_resolve_root_returns_tuple(self):
        result = resolve('/')
        self.assertIsNotNone(result)
        dev, mp, fstype = result
        self.assertIsInstance(dev, str)
        self.assertGreater(len(dev), 0)
        self.assertIsInstance(mp, str)
        self.assertGreater(len(mp), 0)
        self.assertIsInstance(fstype, str)

    def test_resolve_tmp_returns_tuple(self):
        result = resolve('/tmp')
        self.assertIsNotNone(result)
        dev, mp, fstype = result
        self.assertGreater(len(dev), 0)
        self.assertGreater(len(mp), 0)

    @patch('rawblock_io._resolve.resolve_device', return_value=None)
    def test_resolve_no_device_returns_none(self, _mock):
        self.assertIsNone(resolve('/'))

    @patch('rawblock_io._resolve.resolve_mount_point', return_value=None)
    def test_resolve_no_mount_returns_none(self, _mock):
        self.assertIsNone(resolve('/'))


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

    def test_df_output_tmp(self):
        result = _df_output('/tmp')
        self.assertIsNotNone(result)
        dev, mp, fstype = result
        self.assertIsInstance(dev, str)
        self.assertGreater(len(dev), 0)
        self.assertIsInstance(mp, str)
        self.assertGreater(len(mp), 0)

    def test_df_output_cwd(self):
        result = _df_output(os.getcwd())
        self.assertIsNotNone(result)
        dev, mp, fstype = result
        self.assertIsInstance(dev, str)
        self.assertGreater(len(dev), 0)

    def test_df_output_symlink(self):
        d = tempfile.mkdtemp(prefix='rbio_df_')
        try:
            target = os.path.join(d, 'target')
            link = os.path.join(d, 'mylink')
            with open(target, 'w') as f:
                f.write('x')
            os.symlink('target', link)
            result = _df_output(link)
            self.assertIsNotNone(result)
            dev, mp, fstype = result
            self.assertIsInstance(dev, str)
            self.assertGreater(len(dev), 0)
        finally:
            shutil.rmtree(d)

    def test_df_output_nonexistent_returns_none(self):
        self.assertIsNone(_df_output('/nonexistent_path_xyz123_test'))
