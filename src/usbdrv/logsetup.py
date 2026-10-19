"""Logging: file di log con data e ora (testo o righe JSON) ed eco facoltativo sulla console."""

import json
import logging
import sys
from typing import Optional

LOGGER_NAME = "usbdrv"
LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARN": logging.WARNING,
          "WARNING": logging.WARNING, "ERROR": logging.ERROR}
MAX_OUTPUT_CHARS = 4000


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {"time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                "message": record.getMessage()}
        extra = getattr(record, "fields", None)
        if extra:
            data.update(extra)
        return json.dumps(data, ensure_ascii=False)


def parse_level(name: str) -> int:
    try:
        return LEVELS[name.upper()]
    except KeyError:
        raise ValueError("invalid log level '%s' (DEBUG, INFO, WARN, ERROR)" % name)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None, fmt: str = "text",
                  verbose: bool = False, stream=None) -> logging.Logger:
    """Configura e restituisce il logger 'usbdrv'. Si può chiamare più volte senza problemi (reimposta gli handler)."""
    logger = logging.getLogger(LOGGER_NAME)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    lvl = logging.DEBUG if verbose else parse_level(level)
    logger.setLevel(lvl)
    logger.propagate = False
    text = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", "%Y-%m-%d %H:%M:%S")
    chosen = JsonFormatter() if fmt == "json" else text
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(chosen)
        logger.addHandler(fh)
    if verbose:
        sh = logging.StreamHandler(stream or sys.stderr)
        sh.setFormatter(text)
        logger.addHandler(sh)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def log_fields(logger: logging.Logger, level: int, msg: str, **fields) -> None:
    logger.log(level, msg, extra={"fields": fields})


def clip(text: Optional[str]) -> str:
    text = text or ""
    return text if len(text) <= MAX_OUTPUT_CHARS else text[:MAX_OUTPUT_CHARS] + "...[truncated]"
