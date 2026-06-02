import sys
from pathlib import Path

from loguru import logger
from rich.console import Console

from api.config import GlobalConst as gc

console = Console(stderr=True)


def _rich_sink(msg):
    console.print(str(msg).rstrip(), markup=False, highlight=False)


def configure_logging(console_enabled=True, console_level="INFO", tui_sink=None):
    logger.remove()
    if console_enabled:
        logger.add(
            _rich_sink,
            level=console_level,
            enqueue=True,
            format="{time:HH:mm:ss} | {level:<7} | {message}",
        )
    if tui_sink:
        logger.add(
            tui_sink,
            level="INFO",
            enqueue=True,
            format="{time:HH:mm:ss} | {level:<7} | {message}",
        )

    log_path = Path(gc.LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_path),
        rotation="10 MB",
        level="TRACE",
        encoding="utf8",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {name}:{function}:{line} - {message}",
    )


configure_logging(console_enabled=sys.stderr.isatty())
