# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-14

### Added

- New `resolve(path)` function that returns a `(device, mount_point, fstype)` tuple in one call.
- `_df_output` function exported as part of the public API.
- GPL-3.0 license.

### Changed

- `DDStrategy` now tries plain `dd` first and only falls back to `sudo dd` on failure, removing the hard requirement for sudo.

### Fixed

- `_write_blocks` in `DDStrategy` now correctly returns `False` when both `dd` and `sudo dd` fail.

## [0.1.0] - 2026-06-13

### Added

- Raw block device I/O with pluggable strategy system (DirectIO, DD, BackingFile).
- Cross-platform device and mount point resolution (Linux via `/proc/partitions`, macOS via `diskutil`/`hdiutil`).
- `RawBlockIO` class with automatic strategy fallback chain.

[unreleased]: https://github.com/MBanucu/rawblock-io/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/MBanucu/rawblock-io/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MBanucu/rawblock-io/releases/tag/v0.1.0
