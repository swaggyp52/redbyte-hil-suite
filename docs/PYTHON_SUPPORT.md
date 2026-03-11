# Python Support Policy

Last updated: 2026-03-11

## Support Matrix

| Status | Version | Notes |
|---|---|---|
| Supported | 3.12.x | Canonical runtime for development, CI, app launch, and full test validation. |
| Partially supported | 3.13.x | Not validated in CI for this repo; may work for some paths but not release-qualified. |
| Unsupported | 3.14.x | Explicitly unsupported for this repo at present. Preflight and tests are pinned to 3.12 for reproducibility. |
| Unsupported | < 3.12 | Out of policy. |

## Why 3.14 Is Marked Unsupported

During closure validation, environment drift was found:

1. Two virtual environments were in use (`redbyte_gfm/.venv` and `gfm_hil_suite/.venv`).
2. The workspace-selected 3.14 environment referenced `C:\Python314` and emitted prefix warnings (`Could not find platform independent libraries <prefix>`).
3. Browser validation was not reliably configured in that environment.

To remove ambiguity and ensure reproducible demo behavior, the repo is now policy-pinned to Python 3.12.

## Required Dependencies by Validation Scope

### Required for app runtime and core tests
- PyQt6
- pyqtgraph
- pyserial
- pandas
- numpy
- scipy
- matplotlib
- python-dotenv
- pytest

### Required for browser validation tests
- playwright (Python package)
- Chromium browser binary installed with:
  - `python -m playwright install chromium`

### Optional dependencies
- PyOpenGL / PyOpenGL_accelerate
- Used for OpenGL/3D visual paths only; non-OpenGL workflows remain functional without them.

## Enforcement

- `.python-version` pins the canonical interpreter to `3.12`.
- `pyproject.toml` enforces `requires-python = ">=3.12,<3.13"`.
- `tests/conftest.py` fails early on unsupported Python versions.
- `scripts/preflight_check.py` provides fail-fast environment diagnostics.
- CI runs on Python 3.12 and installs Playwright Chromium before running tests.
