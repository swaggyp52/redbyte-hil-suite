# Fresh Machine Validation (Windows)

Use this checklist on a brand-new machine or a clean clone.

> **One-liner option (Windows):** Download the repo, `cd gfm_hil_suite`, then
> double-click `install.cmd` — it runs steps 3 and 4 for you. Then go straight to step 5.

## 1. Install prerequisites

1. Install Python 3.12.x from python.org.
2. Confirm installation:
   - `py -3.12 --version`

## 2. Clone and enter repo

1. `git clone <repo-url>`
2. `cd gfm_hil_suite`

## 3. Create and activate virtual environment

1. `py -3.12 -m venv .venv`
2. `.venv\Scripts\activate`

## 4. Install dependencies

1. `python -m pip install --upgrade pip`
2. `pip install -r requirements.txt`
3. For dev/testing (optional, required to run the test suite):
   - `pip install -r requirements-dev.txt`
4. For Excel import support (optional):
   - `pip install openpyxl` (or included in requirements-dev.txt)

## 5. Verify import

1. `python -c "import PyQt6; import pyqtgraph; import numpy; import scipy; print('OK')"`
2. Expected result: prints `OK` with no errors.
3. If any import fails, re-run `pip install -r requirements.txt`.

## 6. Run tests

1. Full suite (requires requirements-dev.txt installed):
   - `python -m pytest tests/ --ignore=tests/test_ui_integration.py -q`
2. Expected: 352 passing, 3 skipped (Excel tests skip automatically if openpyxl absent).
3. Playwright UI test (requires playwright, separate install):
   - `pip install playwright && python -m playwright install chromium`
   - `python -m pytest tests\test_playwright_report_ui.py -v`

## 7. Launch app in demo mode

1. `python run.py`
2. Optional flags:
   - `python run.py --fullscreen` (fullscreen demo mode)
   - `python run.py --no-3d` (disable OpenGL if unavailable)
   - `python run.py --live` (live hardware mode via serial port)

## 8. Common recovery actions

- Wrong Python selected:
  - Recreate venv using `py -3.12 -m venv .venv`
- Missing runtime deps:
  - `pip install -r requirements.txt`
- Missing test deps:
  - `pip install -r requirements-dev.txt`
- OpenGL import warning:
  - `pip install PyOpenGL PyOpenGL_accelerate`

## Expected closure state

- App launches in demo mode (sidebar visible, Overview page shown).
- Full pytest run shows 352 passing, 3 skipped, 0 failures.
- No ambiguous interpreter behavior.
