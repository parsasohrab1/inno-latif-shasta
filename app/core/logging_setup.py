"""سیستم logging ساختاریافته (JSON) برای دوقلوی دیجیتال.

خروجی‌ها به‌صورت JSON خطی (هر خط یک رکورد) برای ارسال به ELK/Loki.
"""

from __future__ import annotations
import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """formatter که هر رکورد log را به‌صورت یک JSON line تولید می‌کند."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exc"] = self.formatException(record.exc_info)
        # extra fields (از kwargs در log call)
        for k, v in record.__dict__.items():
            if k not in ("args","msg","levelname","levelno","pathname","filename",
                         "module","exc_info","exc_text","stack_info","lineno",
                         "funcName","created","msecs","relativeCreated","thread",
                         "threadName","processName","process","name","getMessage",
                         "taskName"):
                if not k.startswith("_"):
                    try:
                        log_entry[k] = v
                    except Exception:
                        pass
        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logging(level: str = "info") -> logging.Logger:
    """راه‌اندازی logger اصلی با JSON formatter."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)
    # پاک‌کردن handler های پیش‌فرض
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # کاهش verbosity کتابخانه‌های پرسر و صدا
    for noisy in ("uvicorn.access", "uvicorn.error", "asyncio", "asyncua"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("latif")


logger = setup_logging(os.environ.get("LATIF_LOG_LEVEL", "info"))
