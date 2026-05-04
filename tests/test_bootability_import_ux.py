import os

from PyQt6.QtWidgets import QMessageBox

from run import resolve_startup_args
from src.dataset_converter import dataset_to_session
from src.file_ingestion import ingest_file
from ui.app_shell import AppShell
from ui.app_shell import _PAGE_INDICES


class _FakeUrl:
    def __init__(self, path: str):
        self._path = path

    def toLocalFile(self) -> str:
        return self._path


class _FakeMimeData:
    def __init__(self, paths: list[str]):
        self._paths = paths

    def hasUrls(self) -> bool:
        return bool(self._paths)

    def urls(self) -> list[_FakeUrl]:
        return [_FakeUrl(p) for p in self._paths]


class _FakeDropEvent:
    def __init__(self, paths: list[str]):
        self._mime = _FakeMimeData(paths)
        self.accepted = False
        self.ignored = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


def test_resolve_startup_args_defaults_to_overview_windowed():
    argv = ["run.py"]
    resolved = resolve_startup_args(argv)

    assert "--windowed" in resolved
    assert "--demo" not in resolved


def test_resolve_startup_args_live_flag_is_consumed():
    argv = ["run.py", "--live", "--port", "COM5"]
    resolved = resolve_startup_args(argv)

    assert "--live" not in resolved
    assert "--port" in resolved
    assert "COM5" in resolved


def test_resolve_startup_args_fullscreen_disables_windowed_default():
    argv = ["run.py", "--demo", "--fullscreen"]
    resolved = resolve_startup_args(argv)

    assert "--fullscreen" not in resolved
    assert "--windowed" not in resolved
    assert "--demo" in resolved


def test_drag_enter_accepts_any_file_drop_for_feedback(qapp):
    shell = AppShell(demo_mode=False, mock_mode=False, enable_3d=False, windowed=True)
    event = _FakeDropEvent([r"C:\\tmp\\notes.md"])

    shell.dragEnterEvent(event)

    assert event.accepted is True
    assert event.ignored is False
    shell.close()


def test_drop_supported_file_opens_import_dialog(qapp, monkeypatch):
    shell = AppShell(demo_mode=False, mock_mode=False, enable_3d=False, windowed=True)
    opened: dict[str, str] = {}

    def _fake_open(preload_path: str = ""):
        opened["path"] = preload_path

    monkeypatch.setattr(shell, "_open_import_dialog", _fake_open)

    supported_path = r"C:\\tmp\\capture.csv"
    event = _FakeDropEvent([supported_path])
    shell.dropEvent(event)

    assert opened.get("path") == supported_path
    shell.close()


def test_drop_unsupported_file_shows_clear_guidance(qapp, monkeypatch):
    shell = AppShell(demo_mode=False, mock_mode=False, enable_3d=False, windowed=True)
    captured: dict[str, str] = {}

    def _fake_warning(_parent, title: str, message: str):
        captured["title"] = title
        captured["message"] = message
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(_fake_warning))

    unsupported_path = os.path.join("C:\\tmp", "README.md")
    event = _FakeDropEvent([unsupported_path])
    shell.dropEvent(event)

    assert captured.get("title") == "Unsupported File Type"
    assert "cannot be analyzed" in captured.get("message", "")
    assert "Supported data files" in captured.get("message", "")
    shell.close()


def test_supported_import_lands_in_replay_with_locked_demo_navigation(qapp):
    shell = AppShell(demo_mode=False, mock_mode=False, enable_3d=False, windowed=True)

    dataset = ingest_file("data/demo_sessions/session_nominal.json")
    capsule = dataset_to_session(dataset)
    capsule["_dataset"] = dataset

    shell._on_session_imported(capsule)

    assert shell.stack.currentIndex() == _PAGE_INDICES["replay"]
    assert shell._current_session is not None
    assert not shell._overview._info_panel.isHidden()
    assert shell._replay.studio.sessions
    assert not shell.sidebar._buttons["overview"].isVisible()

    tabs = shell._replay.studio.tabs
    tab_bar = tabs.tabBar()
    tab_names = [
        tabs.tabText(i)
        for i in range(tabs.count())
        if tab_bar.isTabVisible(i)
    ]
    assert tab_names == ["Replay", "Metrics", "Compare"]

    for btn in shell._replay._top_bar._export_btns:
        assert btn.isEnabled()

    shell._clear_active_session()
    assert shell.stack.currentIndex() == _PAGE_INDICES["overview"]
    assert not shell.sidebar._buttons["overview"].isHidden()
    assert not shell._replay.studio.sessions

    shell.close()
