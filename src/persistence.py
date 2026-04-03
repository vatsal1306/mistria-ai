"""JSON-backed user profile storage."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from typing import Any

from src.config import DB_FILE, PROJECT_ROOT

logger = logging.getLogger(__name__)


def load_user_data(user_id: str) -> dict[str, Any] | None:
    if not DB_FILE.exists():
        logger.error("%s not found", DB_FILE)
        return None
    try:
        with DB_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read %s: %s", DB_FILE, exc)
        return None
    return data.get(user_id)


def save_user_session(user_id: str, score: int) -> None:
    tmp_path: str | None = None
    if not DB_FILE.exists():
        logger.warning("%s missing — creating fresh database", DB_FILE)
        data: dict[str, Any] = {}
    else:
        try:
            with DB_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s for saving: %s", DB_FILE, exc)
            return

    if user_id not in data:
        logger.info("Creating new entry for %s", user_id)
        data[user_id] = {}

    data[user_id]["last_pulse"] = score
    data[user_id]["last_seen"] = time.time()

    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(PROJECT_ROOT), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=4)
        os.replace(tmp_path, DB_FILE)
    except OSError as exc:
        logger.error("Failed to save session: %s", exc)
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
