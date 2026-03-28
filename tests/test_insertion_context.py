"""Tests for active window detection."""
from __future__ import annotations
import sys
from unittest.mock import patch
import pytest
from dictateme.core.types import ActiveWindowInfo
from dictateme.insertion.context import get_active_window

def _fake_window(**kw):
    d = dict(hwnd=12345, title="Test Window", process_name="test.exe", process_id=999, is_elevated=False)
    d.update(kw)
    return ActiveWindowInfo(**d)

class TestGetActiveWindowDispatch:
    @patch("dictateme.insertion.context._win_get_active_window")
    def test_dispatches_to_win32(self, mock_win):
        expected = _fake_window()
        mock_win.return_value = expected
        with patch.object(sys, "platform", "win32"): result = get_active_window()
        assert result == expected
        mock_win.assert_called_once()

    @patch("dictateme.insertion.context._mac_get_active_window")
    def test_dispatches_to_darwin(self, mock_mac):
        expected = _fake_window(title="Safari")
        mock_mac.return_value = expected
        with patch.object(sys, "platform", "darwin"): result = get_active_window()
        assert result == expected
        mock_mac.assert_called_once()

    @patch("dictateme.insertion.context._linux_get_active_window")
    def test_dispatches_to_linux(self, mock_linux):
        expected = _fake_window(title="Terminal")
        mock_linux.return_value = expected
        with patch.object(sys, "platform", "linux"): result = get_active_window()
        assert result == expected
        mock_linux.assert_called_once()

class TestActiveWindowInfoReturnType:
    @patch("dictateme.insertion.context._win_get_active_window")
    def test_return_type(self, mock_win):
        mock_win.return_value = _fake_window()
        with patch.object(sys, "platform", "win32"): result = get_active_window()
        assert isinstance(result, ActiveWindowInfo)
        for attr in ["hwnd", "title", "process_name", "process_id", "is_elevated"]:
            assert hasattr(result, attr)

class TestActiveWindowInfoFields:
    def test_holds_all_fields(self):
        info = ActiveWindowInfo(hwnd=42, title="My Editor", process_name="code.exe", process_id=1234, is_elevated=True)
        assert info.hwnd == 42
        assert info.title == "My Editor"
        assert info.process_name == "code.exe"
        assert info.process_id == 1234
        assert info.is_elevated is True

    def test_equality(self):
        a = _fake_window(hwnd=1, title="A")
        b = _fake_window(hwnd=1, title="A")
        c = _fake_window(hwnd=2, title="B")
        assert a == b
        assert a != c
