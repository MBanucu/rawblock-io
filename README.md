# rawblock-io

[![PyPI version](https://img.shields.io/pypi/v/rawblock-io)](https://pypi.org/project/rawblock-io/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/)
[![License](https://img.shields.io/github/license/MBanucu/rawblock-io)](LICENSE)
[![OS](https://img.shields.io/badge/OS-Linux%20%7C%20macOS-blue)](https://github.com/MBanucu/rawblock-io)

[![CI](https://img.shields.io/github/actions/workflow/status/MBanucu/rawblock-io/test.yml?branch=main)](https://github.com/MBanucu/rawblock-io/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/MBanucu/rawblock-io/branch/main/graph/badge.svg)](https://codecov.io/gh/MBanucu/rawblock-io)

[![Downloads total](https://pepy.tech/badge/rawblock-io)](https://pepy.tech/project/rawblock-io)
[![Downloads/month](https://pepy.tech/badge/rawblock-io/month)](https://pepy.tech/project/rawblock-io)
[![Downloads/week](https://pepy.tech/badge/rawblock-io/week)](https://pepy.tech/project/rawblock-io)

Raw block device I/O with automatic strategy fallback and cross-platform
device/mount point resolution.

## Features

- **Pluggable I/O strategies** — tries direct access first, falls back
  through loop-device backing file to `sudo dd`
- **`DirectIOStrategy`** — `os.pread`/`os.pwrite` on regular files and
  accessible block devices
- **`BackingFileStrategy`** — resolves loop-device backing files (`/sys/block`,
  `losetup`, or `hdiutil` on macOS)
- **`DDStrategy`** — `sudo dd` fallback for physical block devices
- **`resolve_device`** — find the underlying block device for any file path
  (Linux `/proc/partitions` + `/sys/dev/block`, macOS `hdiutil`)
- **`resolve_mount_point`** — find the mount point for any file path
  (Linux `findmnt`, macOS `df`)

## Quick start

```python
from rawblock_io import RawBlockIO, resolve_device

io = RawBlockIO()
device = resolve_device('/some/file')
data = io.read(device, 0, 512)  # read first sector
```

## License

GPL-3.0-only
