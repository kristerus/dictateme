"""Tests for clipboard module."""
from __future__ import annotations
import sys
from unittest.mock import MagicMock, patch
import pytest
from dictateme.insertion.clipboard import (
    clipboard_paste, get_clipboard_text, set_clipboard_text,
    simulate_paste, _linux_clipboard_tool,
)

class TestPublicAPIExists:
    def test_get_clipboard_text_callable(self): assert callable(get_clipboard_text)
    def test_set_clipboard_text_callable(self): assert callable(set_clipboard_text)
    def test_simulate_paste_callable(self): assert callable(simulate_paste)
    def test_clipboard_paste_callable(self): assert callable(clipboard_paste)

class TestPlatformRouting:
    @patch("dictateme.insertion.clipboard._win_get_clipboard", return_value="win-text")
    def test_get_routes_win32(self, m):
        with patch.object(sys, "platform", "win32"): r = get_clipboard_text()
        assert r == "win-text"; m.assert_called_once()

    @patch("dictateme.insertion.clipboard._mac_get_clipboard", return_value="mac-text")
    def test_get_routes_darwin(self, m):
        with patch.object(sys, "platform", "darwin"): r = get_clipboard_text()
        assert r == "mac-text"; m.assert_called_once()

    @patch("dictateme.insertion.clipboard._linux_get_clipboard", return_value="linux-text")
    def test_get_routes_linux(self, m):
        with patch.object(sys, "platform", "linux"): r = get_clipboard_text()
        assert r == "linux-text"; m.assert_called_once()

    @patch("dictateme.insertion.clipboard._win_set_clipboard", return_value=True)
    def test_set_routes_win32(self, m):
        with patch.object(sys, "platform", "win32"): r = set_clipboard_text("test")
        assert r is True; m.assert_called_once_with("test")

    @patch("dictateme.insertion.clipboard._mac_set_clipboard", return_value=True)
    def test_set_routes_darwin(self, m):
        with patch.object(sys, "platform", "darwin"): r = set_clipboard_text("test")
        assert r is True; m.assert_called_once_with("test")

    @patch("dictateme.insertion.clipboard._linux_set_clipboard", return_value=True)
    def test_set_routes_linux(self, m):
        with patch.object(sys, "platform", "linux"): r = set_clipboard_text("test")
        assert r is True; m.assert_called_once_with("test")

    @patch("dictateme.insertion.clipboard._win_simulate_paste")
    def test_paste_routes_win32(self, m):
        with patch.object(sys, "platform", "win32"): simulate_paste()
        m.assert_called_once()

    @patch("dictateme.insertion.clipboard._mac_simulate_paste")
    def test_paste_routes_darwin(self, m):
        with patch.object(sys, "platform", "darwin"): simulate_paste()
        m.assert_called_once()

    @patch("dictateme.insertion.clipboard._linux_simulate_paste")
    def test_paste_routes_linux(self, m):
        with patch.object(sys, "platform", "linux"): simulate_paste()
        m.assert_called_once()

class TestClipboardPaste:
    @patch("dictateme.insertion.clipboard.simulate_paste")
    @patch("dictateme.insertion.clipboard.set_clipboard_text", return_value=True)
    @patch("dictateme.insertion.clipboard.get_clipboard_text", return_value="original")
    def test_sets_text_and_pastes(self, mg, ms, mp):
        r = clipboard_paste("hello", restore=False)
        assert r is True; ms.assert_called_with("hello"); mp.assert_called_once()

    @patch("dictateme.insertion.clipboard.simulate_paste")
    @patch("dictateme.insertion.clipboard.set_clipboard_text", return_value=False)
    @patch("dictateme.insertion.clipboard.get_clipboard_text", return_value="original")
    def test_returns_false_on_set_failure(self, mg, ms, mp):
        r = clipboard_paste("hello", restore=False)
        assert r is False; mp.assert_not_called()

class TestLinuxClipboardTool:
    @patch("shutil.which", side_effect=lambda x: "/usr/bin/xclip" if x == "xclip" else None)
    def test_detects_xclip(self, m): assert _linux_clipboard_tool() == "xclip"

    @patch("shutil.which", side_effect=lambda x: "/usr/bin/xsel" if x == "xsel" else None)
    def test_detects_xsel(self, m): assert _linux_clipboard_tool() == "xsel"

    @patch("shutil.which", side_effect=lambda x: "/usr/bin/wl-copy" if x == "wl-copy" else None)
    def test_detects_wayland(self, m): assert _linux_clipboard_tool() == "wl"

    @patch("shutil.which", return_value=None)
    def test_returns_none_when_no_tool(self, m): assert _linux_clipboard_tool() is None
