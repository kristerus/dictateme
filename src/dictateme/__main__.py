"""Entry point for `python -m dictateme`."""

from __future__ import annotations


def main() -> None:
    """Launch the DictateMe application."""
    from .app import DictateApp

    app = DictateApp()
    app.run()


if __name__ == "__main__":
    main()
