from __future__ import annotations

import argparse
import importlib
import os
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PASS_MARK = "[PASS]"
FAIL_MARK = "[FAIL]"


class CheckRunner:
    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet
        self.failures: list[str] = []

    def ok(self, label: str) -> None:
        if not self.quiet:
            print(f"{PASS_MARK} {label}")

    def fail(self, label: str, detail: str = "") -> None:
        message = f"{label}{': ' + detail if detail else ''}"
        print(f"{FAIL_MARK} {message}")
        self.failures.append(message)

    def run(self, label: str, check) -> None:
        try:
            result = check()
        except Exception as exc:
            self.fail(label, str(exc))
            if not self.quiet:
                traceback.print_exc()
            return

        if result is False:
            self.fail(label)
        else:
            self.ok(label)


def _check_python_version() -> bool:
    return sys.version_info >= (3, 12)


def _import_required_modules() -> None:
    for module_name in (
        "PyQt6",
        "pyqtgraph",
        "numpy",
        "pandas",
        "openpyxl",
        "matplotlib",
        "scipy",
    ):
        importlib.import_module(module_name)


def _check_qt_offscreen() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    if app is None:
        raise RuntimeError("QApplication could not be created")


def _check_entrypoint_imports() -> None:
    import run  # noqa: F401
    from src.main import main  # noqa: F401


def _check_overview_boot() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication
    from ui.app_shell import AppShell, _PAGE_INDICES

    app = QApplication.instance() or QApplication([])
    shell = AppShell(demo_mode=False, mock_mode=False, enable_3d=False, windowed=True)
    try:
        if shell.stack.currentIndex() != _PAGE_INDICES["overview"]:
            raise RuntimeError("AppShell did not open on the Overview page")
    finally:
        shell.close()


def _check_sample_data_imports() -> None:
    from src.file_ingestion import ingest_file

    sample_files = [
        PROJECT_ROOT / "sample_data" / "demo_session.json",
        PROJECT_ROOT / "sample_data" / "demo_three_phase.csv",
    ]
    for sample_path in sample_files:
        if not sample_path.exists():
            raise FileNotFoundError(f"Missing sample data file: {sample_path}")
        dataset = ingest_file(str(sample_path))
        if dataset.row_count <= 0:
            raise RuntimeError(f"Sample data file has no rows: {sample_path.name}")


def _check_artifacts_writable() -> None:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    probe_path = artifacts_dir / ".package-self-check.tmp"
    probe_path.write_text("ok\n", encoding="utf-8")
    probe_path.unlink(missing_ok=True)


def _check_package_files() -> None:
    required_paths = (
        PROJECT_ROOT / "install.cmd",
        PROJECT_ROOT / "run.bat",
        PROJECT_ROOT / "run.py",
        PROJECT_ROOT / "scripts" / "bootstrap.cmd",
    )
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing package file(s): " + ", ".join(missing))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the packaged Windows install surface.")
    parser.add_argument("--mode", choices=("runtime", "install", "launch"), default="install")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not args.quiet:
        print("=" * 60)
        print(f"VSM Evidence Workbench - Package Self-Check ({args.mode})")
        print("=" * 60)

    runner = CheckRunner(quiet=args.quiet)
    runner.run("Python 3.12+ is available", _check_python_version)
    runner.run("Required runtime modules import", _import_required_modules)
    runner.run("Qt offscreen startup works", _check_qt_offscreen)
    runner.run("App entrypoints import", _check_entrypoint_imports)
    runner.run("App boots to Overview", _check_overview_boot)
    runner.run("Bundled sample data imports", _check_sample_data_imports)
    runner.run("artifacts/ is writable", _check_artifacts_writable)
    runner.run("Package launcher files exist", _check_package_files)

    if runner.failures:
        if not args.quiet:
            print("=" * 60)
            print(f"RESULT: {len(runner.failures)} self-check failure(s)")
        return 1

    if not args.quiet:
        print("=" * 60)
        print("RESULT: Package self-check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())