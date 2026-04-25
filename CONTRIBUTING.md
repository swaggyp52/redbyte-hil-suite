# Contributing to VSM Evidence Workbench

Welcome to the **VSM Evidence Workbench** — the Cyber Engineering contribution
to the Gannon University Senior Design capstone (2025-2026). This document is
for team members and reviewers who need to understand how to set up the
development environment and contribute changes.

## Development setup

```bat
cd redbyte-hil-suite
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install openpyxl PyOpenGL      # optional but recommended
python -m src.main                  # launch the app
```

Run the test suite before committing:

```bat
python -m pytest tests/ -v
```

Expected: ≥94 passed, 1 skipped.

## Project layout

```
redbyte-hil-suite/
  src/          Backend modules (importer, analysis, compliance, report, ...)
  ui/           PyQt6 widgets (main_window, replay_studio, import_wizard, ...)
  tests/        Test suite (pytest)
  bin/          Windows batch launchers
  data/         Demo session files
  exports/      Output from evidence-package generation
  docs/         Engineering documentation
```

The authoritative product description is in the root [README.md](README.md).

## Workflow

1. **Branch:** `main` (stable/demo-ready), `dev` (integration), `feature/<name>`.
2. **Commits:** Clear messages, one change per commit.
3. **PRs:** Open against `dev`; all tests must pass; one reviewer.

## Coding standards

- **Style:** PEP 8.
- **Docstrings:** Google-style for all public classes and functions.
- **Type hints:** Use where they add clarity.
- **Tests:** Add unit tests in `tests/` for new logic; UI load must not crash.

## Key modules to understand first

| Module | Role |
|--------|------|
| `src/importer.py` | CSV/Excel → Data Capsule |
| `src/event_detector.py` | Disturbance detection + run summary |
| `src/analysis.py` | Time-aligned run comparison |
| `src/compliance_checker.py` | Standards-inspired evaluation profiles |
| `src/report_generator.py` | Evidence-package export |
| `ui/replay_studio.py` | Main replay + import + evidence UI |

## Documentation

- Update `docs/meeting_log_template.md` weekly.
- Update `docs/architecture.md` if module structure changes.
- Document failure modes in `docs/fmea.md`.
