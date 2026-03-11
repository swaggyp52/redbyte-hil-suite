"""Fail-fast environment validation for local and CI runs."""

from __future__ import annotations

import importlib
import sys
from typing import List, Tuple

SUPPORTED_PYTHON = (3, 12)


def _check_python_version() -> Tuple[bool, str]:
    current = sys.version_info[:2]
    if current != SUPPORTED_PYTHON:
        return (
            False,
            (
                "Unsupported Python version "
                f"{current[0]}.{current[1]}. "
                f"Use Python {SUPPORTED_PYTHON[0]}.{SUPPORTED_PYTHON[1]} for this repo."
            ),
        )
    return True, f"Python {current[0]}.{current[1]}"


def _check_import(module_name: str, install_hint: str) -> Tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        return True, module_name
    except Exception as exc:  # pragma: no cover - defensive import guard
        return False, f"{module_name} import failed: {exc}. Install with: {install_hint}"


def _check_playwright_browser() -> Tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - defensive import guard
        return (
            False,
            "playwright.sync_api import failed: "
            f"{exc}. Install with: pip install playwright",
        )

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
        return True, "playwright chromium launch"
    except Exception as exc:  # pragma: no cover - runtime environment dependent
        return (
            False,
            "Playwright browser check failed: "
            f"{exc}. Install browser with: python -m playwright install chromium",
        )


def main() -> int:
    failures: List[str] = []
    optional_warnings: List[str] = []

    required_modules = [
        ("PyQt6", "pip install PyQt6"),
        ("pyqtgraph", "pip install pyqtgraph"),
        ("serial", "pip install pyserial"),
        ("pandas", "pip install pandas"),
        ("numpy", "pip install numpy"),
        ("scipy", "pip install scipy"),
        ("matplotlib", "pip install matplotlib"),
        ("dotenv", "pip install python-dotenv"),
        ("pytest", "pip install pytest"),
        ("pytest_cov", "pip install pytest-cov"),
        ("playwright.sync_api", "pip install playwright"),
    ]

    optional_modules = [
        ("OpenGL", "pip install PyOpenGL PyOpenGL_accelerate"),
    ]

    ok, msg = _check_python_version()
    if ok:
        print(f"[PASS] {msg}")
    else:
        print(f"[FAIL] {msg}")
        failures.append(msg)

    for module_name, hint in required_modules:
        ok, msg = _check_import(module_name, hint)
        if ok:
            print(f"[PASS] {msg}")
        else:
            print(f"[FAIL] {msg}")
            failures.append(msg)

    browser_ok, browser_msg = _check_playwright_browser()
    if browser_ok:
        print(f"[PASS] {browser_msg}")
    else:
        print(f"[FAIL] {browser_msg}")
        failures.append(browser_msg)

    for module_name, hint in optional_modules:
        ok, msg = _check_import(module_name, hint)
        if ok:
            print(f"[PASS] optional {msg}")
        else:
            warning = f"Optional dependency missing for 3D OpenGL views: {msg}"
            print(f"[WARN] {warning}")
            optional_warnings.append(warning)

    if failures:
        print("\nPreflight failed. Resolve the issues above and rerun.")
        return 1

    if optional_warnings:
        print("\nPreflight passed with optional warnings.")
    else:
        print("\nPreflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
