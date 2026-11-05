import logging
import logging.config
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
                "datefmt": "%H:%M:%S",
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
                "level": log_level,
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "json",
                "filename": "logs/app.log",
                "when": "midnight",
                "backupCount": 30,
                "level": log_level,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": "logs/errors.log",
                "maxBytes": 10_000_000,
                "backupCount": 10,
                "level": "ERROR",
                "encoding": "utf-8",
            },
        },
        "root": {
            "handlers": ["console", "file", "error_file"],
            "level": log_level,
        },
        "loggers": {
            "uvicorn.access": {"propagate": False},
            "sqlalchemy.engine": {"level": "WARNING", "propagate": True},
        },
    })


def get_logger(name: str = "app") -> logging.Logger:
    return logging.getLogger(name)
