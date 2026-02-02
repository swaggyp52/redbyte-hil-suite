# Contributing to gfm_hil_suite

Welcome to the **gfm_hil_suite** team! As a senior design project, this repository serves as both a software product and an academic deliverable. Please follow these guidelines to verify that our work remains high-quality and easy to merge.

## 🛠️ Development Workflow

1. **Branching:**
    - `main`: Stable, demo-ready code.
    - `dev`: Integration branch for active development.
    - `feature/<name>`: New features (e.g., `feature/serial-reader`).
    - `fix/<issue>`: Bug fixes (e.g., `fix/gui-crash`).

2. **Commits:**
    - Use clear, descriptive messages: `feat: add serial reader class` or `fix: resolve graph flickering`.
    - Keep commits focused on a single change.

3. **Pull Requests:**
    - Open PRs against the `dev` branch.
    - Request a review from at least one other team member.
    - Ensure all tests pass before merging.

## 📐 Coding Standards

- **Style:** Follow PEP 8 guidelines.
- **Docstrings:** Use Google-style docstrings for all classes and functions.
- **Typing:** Use Python type hints (`def func(a: int) -> str:`) where possible.
- **Imports:** Sort imports using `isort` or manually group standard lib, third-party, and local.

## 📝 Documentation

- Update `docs/meeting_log_template.md` weekly.
- Keep `docs/design_overview.md` updated if you change the system architecture.
- Document known failure modes in `docs/fmea.md`.

## 🧪 Testing

- Write unit tests for new logic in `tests/`.
- Ensure the UI loads without crashing by running `tests/test_ui_load.py`.
- Run `pytest` locally before pushing.

Thank you for your hard work!
