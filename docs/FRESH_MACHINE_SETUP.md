# Fresh Machine Validation (Windows)

Use this checklist on a brand-new machine or a clean clone.

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
2. `pip install -e ".[dev]"`
3. `python -m playwright install chromium`

## 5. Run fail-fast preflight

1. `python scripts\preflight_check.py`
2. Expected result: all required checks pass.
3. Optional OpenGL warnings are acceptable if you do not need 3D OpenGL paths.

## 6. Run tests

1. Full suite:
   - `python -m pytest tests/ -v`
2. Browser validation specifically:
   - `python -m pytest tests\test_playwright_report_ui.py -v`

## 7. Launch app in demo mode

1. `python src\redbyte_launcher.py --mock`
2. Optional app-specific launch:
   - `python src\redbyte_launcher.py --mock --app diagnostics`
   - `python src\redbyte_launcher.py --mock --app replay --load data\demo_sessions\demo_session_baseline.json`

## 8. Common recovery actions

- Wrong Python selected:
  - Recreate venv using `py -3.12 -m venv .venv`
- Playwright import fails:
  - `pip install playwright`
- Browser launch fails:
  - `python -m playwright install chromium`
- OpenGL import warning:
  - `pip install PyOpenGL PyOpenGL_accelerate`

## Expected closure state

- App launches in mock mode.
- Full pytest run is green.
- Browser report test runs and passes (not skipped).
- No ambiguous interpreter behavior.
