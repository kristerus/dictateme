"""Entry point for `python -m dictateme`."""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the DictateMe application."""
    # Fail fast on non-Windows
    if sys.platform != "win32":
        print("DictateMe currently only supports Windows.", file=sys.stderr)
        sys.exit(1)

    from .app import DictateApp

    app = DictateApp()
    app.run()


if __name__ == "__main__":
    main()
