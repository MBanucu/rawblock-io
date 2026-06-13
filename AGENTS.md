# rawblock-io — AGENTS.md

## Project

Raw block device I/O Python library with automatic strategy fallback and cross-platform device/mount resolution.

- **Package**: `rawblock-io` (PyPI), `rawblock_io` (import)
- **Repo**: `https://github.com/MBanucu/rawblock-io`
- **Python**: `>=3.10`
- **License**: GPL-3.0-only

## Commands

```bash
# Install (editable)
pip install -e .

# Run tests
python -m unittest discover -s tests -v

# Run tests with coverage
pip install coverage
python -m coverage run -m unittest discover -s tests -v
python -m coverage report --fail-under=70 --skip-covered

# Coverage per-file JSON dump
python -m coverage json -o cov.json
```

CI workflow: `.github/workflows/test.yml` — matrix on `ubuntu-latest` and `macos-latest` × Python 3.10–3.14.

## Coverage — Codecov API

Coverage data is uploaded per-runner and merged by Codecov. Query programmatically via the Codecov v2 REST API (no auth needed for public repos).

### Commit/branch coverage report (per-file totals + line-by-line)

```
GET https://api.codecov.io/api/v2/github/{owner}/repos/{repo}/report/?branch=main
GET https://api.codecov.io/api/v2/github/{owner}/repos/{repo}/report/?sha={sha}
```

For rawblock-io:
```
https://api.codecov.io/api/v2/github/MBanucu/repos/rawblock-io/report/?branch=main
```

### Filter by file path prefix

```
https://api.codecov.io/api/v2/github/MBanucu/repos/rawblock-io/report/?branch=main&path=rawblock_io/_resolve
```

### Response shape

```json
{
  "totals": {
    "coverage": 93.38,
    "hits": 494,
    "misses": 35,
    "lines": 529,
    "partials": 0,
    "files": 10
  },
  "files": [
    {
      "name": "rawblock_io/_resolve.py",
      "totals": {
        "coverage": 100.0,
        "hits": 36,
        "misses": 0,
        "lines": 36
      },
      "line_coverage": [
        [8, 0],
        [9, 0],
        [10, 0],
        [13, 0]
      ]
    }
  ]
}
```

Each entry in `line_coverage` is `[line_number, status]` where:
- `0` = hit (covered)
- `1` = miss (uncovered)
- `2` = partial

### Extract missed lines with python

```bash
curl -s "https://api.codecov.io/api/v2/github/MBanucu/repos/rawblock-io/report/?branch=main" | \
  python3 -c "
import json, sys
d = json.load(sys.stdin)
for f in d.get('files', []):
    t = f['totals']
    misses = [ln for ln, st in f.get('line_coverage', []) if st == 1]
    print(f'{f[\"name\"]:45s} {t[\"coverage\"]:5.1f}% ({t[\"hits\"]:3d}/{t[\"lines\"]:3d})  missed: {misses}')
"
```

### Other useful endpoints

| Endpoint | Purpose |
|----------|---------|
| `/report/?sha={sha}` | Coverage for a specific commit |
| `/report/?branch={branch}&path={prefix}` | Filtered coverage by file path prefix |
| `/totals/?branch={branch}` | Totals only (no line-by-line) |
| `/report/?branch={branch}&flag={flag}` | Filter by coverage flag |
| `/commits/?branch={branch}` | Paginated commit list |
| `/branches/` | Branch list with head commit info |

Full API reference: `https://docs.codecov.com/llms.txt`

### Notes

- Report is **merged** across all CI runners (Linux + macOS) — Codecov combines per-file data based on matched path names. `relative_files = True` in `.coveragerc` ensures consistent paths: `rawblock_io/_resolve.py` on all OS.
- File paths use `/` separators regardless of OS.
- The `line_coverage` array only includes lines that have statement-level coverage data (not blanks/comments).
- Codecov may take a few minutes after CI finishes to process the upload.

## Module structure

```
rawblock_io/
  __init__.py        — public API re-exports
  _resolve.py        — cross-platform df-based resolution + dispatcher
  _resolve_linux.py  — Linux-specific (os.stat + /proc/partitions + findmnt)
  _resolve_darwin.py — macOS-specific (df + hdiutil + plistlib)
  _strategies.py     — IOStrategy ABC + helpers (_block_align, _try_pread, _try_pwrite)
  _direct_io.py      — DirectIOStrategy (os.pread/os.pwrite)
  _backing_file.py   — BackingFileStrategy (DMG/sparseimage backing via hdiutil)
  _dd.py             — DDStrategy (dd/sudo dd fallback)
  _io.py             — RawBlockIO (strategy chain)
tests/
  test_rawblock_io.py — 41 tests (unit + mocked + integration)
```

## Branch protection

- Ruleset `17641120` on `main` requires: PR → squash/merge/rebase → **All tests** status check (from `.github/workflows/test.yml` result job).
