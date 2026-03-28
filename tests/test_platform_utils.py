"""Tests for platform utility functions."""
from __future__ import annotations
import sys
from unittest.mock import patch
import pytest
from dictateme.utils.platform import (
    get_os_name, is_linux, is_macos, is_windows,
    get_cursor_pos, get_screen_size, check_platform,
)

class TestIsWindows:
    def test_true_on_win32(self):
        with patch.object(sys, "platform", "win32"): assert is_windows() is True
    def test_false_on_darwin(self):
        with patch.object(sys, "platform", "darwin"): assert is_windows() is False
    def test_false_on_linux(self):
        with patch.object(sys, "platform", "linux"): assert is_windows() is False

class TestIsMacos:
    def test_true_on_darwin(self):
        with patch.object(sys, "platform", "darwin"): assert is_macos() is True
    def test_false_on_win32(self):
        with patch.object(sys, "platform", "win32"): assert is_macos() is False

class TestIsLinux:
    def test_true_on_linux(self):
        with patch.object(sys, "platform", "linux"): assert is_linux() is True
    def test_false_on_win32(self):
        with patch.object(sys, "platform", "win32"): assert is_linux() is False
    def test_false_on_darwin(self):
        with patch.object(sys, "platform", "darwin"): assert is_linux() is False

class TestGetOsName:
    def test_windows(self):
        with patch.object(sys, "platform", "win32"): assert get_os_name() == "Windows"
    def test_macos(self):
        with patch.object(sys, "platform", "darwin"): assert get_os_name() == "macOS"
    def test_linux(self):
        with patch.object(sys, "platform", "linux"): assert get_os_name() == "Linux"
    def test_unknown(self):
        with patch.object(sys, "platform", "freebsd13"): assert get_os_name() == "freebsd13"

class TestGetCursorPos:
    def test_returns_two_ints(self):
        pos = get_cursor_pos()
        assert isinstance(pos, tuple) and len(pos) == 2
        assert isinstance(pos[0], int) and isinstance(pos[1], int)

class TestGetScreenSize:
    def test_returns_positive_ints(self):
        size = get_screen_size()
        assert isinstance(size, tuple) and len(size) == 2
        assert size[0] > 0 and size[1] > 0

class TestCheckPlatform:
    def test_does_not_raise(self): check_platform()
    def test_unknown_does_not_raise(self):
        with patch.object(sys, "platform", "freebsd13"): check_platform()
