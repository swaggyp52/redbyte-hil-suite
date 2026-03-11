from pathlib import Path

import pytest

from report_generator import generate_report


pytestmark = pytest.mark.playwright


def test_report_html_rendered_in_browser_with_playwright(tmp_path):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail(
            "playwright is required for browser validation tests. "
            "Install with: pip install playwright",
            pytrace=False,
        )

    session_path = Path("data/demo_sessions/demo_session_baseline.json")
    assert session_path.exists(), "Expected demo session asset for browser automation test"

    report_path = Path(generate_report(str(session_path), output_dir=str(tmp_path)))
    assert report_path.exists()

    screenshot_path = tmp_path / "report_ui.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(report_path.resolve().as_uri(), wait_until="load")
            page.wait_for_selector("h2")

            assert "HIL Session Report" in (page.text_content("h2") or "")
            assert page.locator("table").count() >= 2

            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
    except Exception:
        pytest.fail(
            "Playwright browser launch failed. "
            "Install browser binaries with: python -m playwright install chromium",
            pytrace=False,
        )

    assert screenshot_path.exists(), "Expected Playwright screenshot artifact"
