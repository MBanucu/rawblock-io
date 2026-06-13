# rawblock-io

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
