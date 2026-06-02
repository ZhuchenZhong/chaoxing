# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None):
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        prog="chaoxing",
        description="ZhuchenZhong/chaoxing TUI and CLI",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("tui", help="打开全程 TUI")
    subparsers.add_parser("run", add_help=False, help="按 config.ini 或命令行参数运行")

    if not argv:
        from api.tui import run_tui
        run_tui()
        return

    known, rest = parser.parse_known_args(argv)
    if known.command == "tui":
        from api.tui import run_tui
        run_tui()
        return

    if known.command == "run":
        import main as legacy_main
        sys.argv = [sys.argv[0], *rest]
        legacy_main.main(default_tui=False)
        return

    parser.print_help()
