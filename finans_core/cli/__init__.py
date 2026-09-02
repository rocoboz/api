"""
borsapy CLI - Command-line interface for Turkish financial markets data.

Usage:
    uvx borsapy --help
    uvx borsapy price THYAO GARAN
    uvx borsapy quote THYAO
"""

from finans_core.cli.app import app


def main() -> None:
    """Entry point for the CLI."""
    app()


__all__ = ["main", "app"]
