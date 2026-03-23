"""Floating overlay UI with webview backend and tkinter fallback.

The webview overlay provides a premium experience with CSS animations,
blur effects, and smooth transitions. Falls back to tkinter if webview
is not available.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.config import FormattingConfig, UIConfig

logger = logging.getLogger(__name__)

FORMAT_KEY_LABELS = [
    ("1", "As-is"),
    ("2", "Formal"),
    ("3", "Casual"),
    ("4", "Email"),
    ("5", "Bullets"),
    ("6", "Code comment"),
    ("7", "AI prompt"),
    ("8", "Slack"),
]


class WebviewOverlay:
    """Premium overlay using pywebview (Edge WebView2 on Windows).

    Renders the overlay using HTML/CSS/JS for a polished, animated
    experience. The webview event loop runs on the main thread; the
    app bootstraps everything else via the loaded callback.
    """

    def __init__(self, ui_config: UIConfig, formatting_config: FormattingConfig) -> None:
        self._ui_config = ui_config
        self._formatting_config = formatting_config
        self._window = None
        self._visible = False
        self._ready = threading.Event()

    def create_window(self) -> None:
        """Create the webview window object (call before start)."""
        import webview

        from .overlay_html import OVERLAY_HTML

        self._window = webview.create_window(
            "DictateMe",
            html=OVERLAY_HTML,
            width=self._ui_config.overlay_width + 16,
            height=320,
            resizable=False,
            frameless=True,
            on_top=True,
            transparent=True,
            hidden=True,
        )
        self._window.events.loaded += self._on_loaded

    def start_main_loop(self, on_ready: object = None) -> None:
        """Start the webview event loop. MUST be called from the main thread.

        This blocks until the webview is closed. All other app components
        should be started from the on_ready callback or before this call
        on background threads.
        """
        import webview

        webview.start(debug=False)

    def _on_loaded(self) -> None:
        self._ready.set()
        logger.debug("Webview overlay loaded")

    def initialize(self, root: object = None) -> None:
        """No-op for compatibility. Window is created via create_window()."""
        pass

    def _eval(self, js: str) -> None:
        """Execute JavaScript in the webview."""
        if self._window and self._ready.is_set():
            try:
                self._window.evaluate_js(js)
            except Exception:
                logger.debug("Failed to eval JS in overlay")

    def show_recording(self) -> None:
        self._position_window()
        if self._window:
            self._window.show()
        self._eval("overlayAPI.show(); overlayAPI.setRecording();")
        self._visible = True

    def show_processing(self) -> None:
        self._eval("overlayAPI.setProcessing();")

    def show_text_preview(self, text: str, show_formats: bool = False) -> None:
        safe_text = json.dumps(text)
        auto_ms = self._formatting_config.auto_insert_delay_ms if show_formats else 0
        self._eval(
            f"overlayAPI.setText({safe_text}, {str(show_formats).lower()}, {auto_ms});"
        )

    def hide(self) -> None:
        self._eval("overlayAPI.hide();")
        self._visible = False
        if self._window:
            threading.Timer(0.3, self._do_hide).start()

    def _do_hide(self) -> None:
        if self._window:
            try:
                self._window.hide()
            except Exception:
                pass

    def _position_window(self) -> None:
        if not self._window:
            return
        import ctypes

        pos = self._ui_config.overlay_position
        width = self._ui_config.overlay_width + 16

        if pos == "cursor":
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            x, y = pt.x + 20, pt.y + 20
        elif pos == "center":
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
            x = (sw - width) // 2
            y = sh // 3
        elif pos == "top_right":
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            x = sw - width - 20
            y = 40
        else:
            x, y = 100, 100

        try:
            self._window.move(x, y)
        except Exception:
            pass

    @property
    def is_visible(self) -> bool:
        return self._visible


class TkinterOverlay:
    """Fallback overlay using tkinter when webview is not available."""

    def __init__(self, ui_config: UIConfig, formatting_config: FormattingConfig) -> None:
        self._ui_config = ui_config
        self._formatting_config = formatting_config
        self._root = None
        self._window = None
        self._status_label = None
        self._text_label = None
        self._format_frame = None
        self._visible = False

    def create_window(self) -> None:
        """No-op for tkinter — window created in initialize()."""
        pass

    def start_main_loop(self, on_ready: object = None) -> None:
        """Run the tkinter main loop."""
        if self._root:
            self._root.mainloop()

    def initialize(self, root: object) -> None:
        import tkinter as tk

        self._root = root
        self._window = tk.Toplevel(root)
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.attributes("-alpha", self._ui_config.overlay_opacity)
        self._window.withdraw()

        frame = tk.Frame(
            self._window, bg="#111115", padx=14, pady=10,
            highlightbackground="#2A2A32", highlightthickness=1,
        )
        frame.pack(fill=tk.BOTH, expand=True)

        self._status_label = tk.Label(
            frame, text="", fg="#FFFFFF", bg="#111115",
            font=("Segoe UI", 11, "bold"), anchor="w",
        )
        self._status_label.pack(fill=tk.X, pady=(0, 6))

        self._text_label = tk.Label(
            frame, text="", fg="#CCCCCC", bg="#111115",
            font=("Segoe UI", 10), anchor="nw", justify="left",
            wraplength=self._ui_config.overlay_width - 30,
        )
        self._text_label.pack(fill=tk.BOTH, expand=True)

        self._format_frame = tk.Frame(frame, bg="#111115")
        for key, label in FORMAT_KEY_LABELS:
            row = tk.Frame(self._format_frame, bg="#111115")
            row.pack(fill=tk.X, pady=1)
            tk.Label(
                row, text=f" {key} ", fg="#FFBA08", bg="#1E1E25",
                font=("Consolas", 9, "bold"), width=3,
            ).pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(
                row, text=label, fg="#9A9AA6", bg="#111115",
                font=("Segoe UI", 9), anchor="w",
            ).pack(side=tk.LEFT)

    def show_recording(self) -> None:
        if self._root is None:
            return
        self._root.after(0, self._show_recording_impl)

    def _show_recording_impl(self) -> None:
        self._status_label.config(text="\u25cf Recording...", fg="#FF5F57")
        self._text_label.config(text="Speak now...")
        self._format_frame.pack_forget()
        self._position_and_show()

    def show_processing(self) -> None:
        if self._root is None:
            return
        self._root.after(0, lambda: self._status_label.config(
            text="\u25cf Processing...", fg="#FF9F43"
        ))

    def show_text_preview(self, text: str, show_formats: bool = False) -> None:
        if self._root is None:
            return
        self._root.after(0, lambda: self._show_text_impl(text, show_formats))

    def _show_text_impl(self, text: str, show_formats: bool) -> None:
        self._status_label.config(text="\u2713 Ready", fg="#2DD4BF")
        display = text[:500] + "..." if len(text) > 500 else text
        self._text_label.config(text=display)
        if show_formats:
            self._format_frame.pack(fill="x", pady=(8, 0))
        else:
            self._format_frame.pack_forget()

    def hide(self) -> None:
        if self._root is None:
            return
        self._root.after(0, self._hide_impl)

    def _hide_impl(self) -> None:
        if self._window:
            self._window.withdraw()
        self._visible = False

    def _position_and_show(self) -> None:
        if not self._window or not self._root:
            return
        width = self._ui_config.overlay_width
        pos = self._ui_config.overlay_position
        if pos == "cursor":
            x = self._root.winfo_pointerx() + 20
            y = self._root.winfo_pointery() + 20
        elif pos == "center":
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            x = (sw - width) // 2
            y = sh // 3
        elif pos == "top_right":
            sw = self._root.winfo_screenwidth()
            x = sw - width - 20
            y = 40
        else:
            x, y = 100, 100
        self._window.geometry(f"{width}x+{x}+{y}")
        self._window.deiconify()
        self._visible = True

    @property
    def is_visible(self) -> bool:
        return self._visible


def create_overlay(ui_config: UIConfig, formatting_config: FormattingConfig) -> WebviewOverlay | TkinterOverlay:
    """Create the best available overlay.

    Currently defaults to tkinter because pywebview's transparent
    frameless windows are unreliable on Windows EdgeChromium.
    The WebviewOverlay is kept for future use once transparency
    support improves.
    """
    logger.info("Using tkinter overlay")
    return TkinterOverlay(ui_config, formatting_config)


def has_webview() -> bool:
    """Check if pywebview overlay is enabled.

    Currently disabled — pywebview transparent windows show as
    white rectangles on Windows. Returns False to force tkinter path.
    """
    return False
