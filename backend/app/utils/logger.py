"""utils/logger.py — structured rotating logger."""
import logging, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str = "insightagent") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    try:
        Path("logs").mkdir(exist_ok=True)
        fh = RotatingFileHandler("logs/app.log", maxBytes=5*1024*1024, backupCount=3)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass
    logger.propagate = False
    return logger

log = get_logger()
