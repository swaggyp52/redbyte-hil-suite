import sys
import os
import pytest

SUPPORTED_PYTHON = (3, 12)

if sys.version_info[:2] != SUPPORTED_PYTHON:
    raise RuntimeError(
        "Unsupported Python version for this test suite: "
        f"{sys.version_info[0]}.{sys.version_info[1]}. "
        "Use Python 3.12 (see .python-version)."
    )

# Add src to path so tests can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from PyQt6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
