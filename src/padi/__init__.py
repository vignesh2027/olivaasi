"""Padi: offline accessible pages from photos of Tamil and English textbooks."""

__version__ = "0.1.0"


def main() -> None:
    from .cli import main as cli_main

    raise SystemExit(cli_main())
