from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.api import common


@pytest.mark.parametrize('selected', ['C:/runs', None])
def test_windows_directory_picker_uses_tkinter(monkeypatch, selected):
    picker = lambda initial=None: selected
    monkeypatch.setattr(common.sys, 'platform', 'win32')
    monkeypatch.setattr(common, '_pick_directory_with_tkinter', picker)

    assert common.pick_local_directory('C:/initial') == selected


def test_other_platforms_try_tkinter(monkeypatch):
    monkeypatch.setattr(common.sys, 'platform', 'linux')
    monkeypatch.setattr(common, '_pick_directory_with_tkinter', lambda initial=None: '/data/runs')

    assert common.pick_local_directory('/data') == '/data/runs'


def test_macos_directory_picker_returns_finder_selection(tmp_path, monkeypatch):
    completed = SimpleNamespace(returncode=0, stdout='/Users/reviewer/runs/\n', stderr='')
    captured = {}

    def run(command, **kwargs):
        captured['command'] = command
        captured['kwargs'] = kwargs
        return completed

    monkeypatch.setattr(common.subprocess, 'run', run)

    selected = common._pick_directory_with_macos(str(tmp_path))

    assert selected == '/Users/reviewer/runs/'
    assert captured['command'] == ['osascript', '-', str(tmp_path.resolve())]
    assert 'shell' not in captured['kwargs']
    assert 'choose folder' in captured['kwargs']['input']


@pytest.mark.parametrize('error_text', ['execution error: User canceled. (-128)', 'User canceled.'])
def test_macos_directory_picker_treats_cancellation_normally(monkeypatch, error_text):
    completed = SimpleNamespace(returncode=1, stdout='', stderr=error_text)
    monkeypatch.setattr(common.subprocess, 'run', lambda *args, **kwargs: completed)

    assert common._pick_directory_with_macos() is None


def test_macos_directory_picker_failure_points_to_manual_entry(monkeypatch):
    completed = SimpleNamespace(returncode=1, stdout='', stderr='Finder is unavailable')
    monkeypatch.setattr(common.subprocess, 'run', lambda *args, **kwargs: completed)

    with pytest.raises(RuntimeError, match='Enter the directory path manually'):
        common._pick_directory_with_macos()


def test_macos_directory_picker_missing_host_tool_points_to_manual_entry(monkeypatch):
    def fail(*args, **kwargs):
        raise FileNotFoundError('osascript')

    monkeypatch.setattr(common.subprocess, 'run', fail)

    with pytest.raises(RuntimeError, match='Enter the directory path manually'):
        common._pick_directory_with_macos()


def test_macos_platform_dispatches_to_finder(monkeypatch):
    monkeypatch.setattr(common.sys, 'platform', 'darwin')
    monkeypatch.setattr(common, '_pick_directory_with_macos', lambda initial=None: '/Users/reviewer/runs')

    assert common.pick_local_directory('/Users/reviewer') == '/Users/reviewer/runs'
