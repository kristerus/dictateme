"""Thread helpers and cancellation utilities."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class CancellableThread(threading.Thread):
    """A thread that supports cooperative cancellation via an Event."""

    def __init__(
        self,
        target: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        daemon: bool = True,
    ) -> None:
        super().__init__(
            target=target, name=name, args=args, kwargs=kwargs or {}, daemon=daemon
        )
        self._cancel_event = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """Signal the thread to stop."""
        self._cancel_event.set()

    def wait_cancelled(self, timeout: float | None = None) -> bool:
        """Block until cancel is signalled or timeout expires."""
        return self._cancel_event.wait(timeout)


class WorkerThread(CancellableThread):
    """A thread that processes items from a queue-like callable.

    Runs `process_fn` in a loop until cancelled. The process function
    should check `self.cancelled` and return promptly when True.
    """

    def __init__(
        self,
        process_fn: Callable[[CancellableThread], None],
        *,
        name: str = "worker",
    ) -> None:
        super().__init__(name=name)
        self._process_fn = process_fn

    def run(self) -> None:
        logger.debug("Worker thread '%s' started", self.name)
        try:
            while not self.cancelled:
                self._process_fn(self)
        except Exception:
            logger.exception("Worker thread '%s' crashed", self.name)
        finally:
            logger.debug("Worker thread '%s' exiting", self.name)
