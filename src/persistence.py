"""JSON-backed user profile storage."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from src.Logging import logger
from src.config import settings

_DB_FILE = Path(settings.storage.db_path)
_PROJECT_ROOT = Path(settings.root_dir)


def load_user_data(user_id: str) -> dict[str, Any] | None:
    """Load a user profile from the database file. Returns None if not found."""
    if not _DB_FILE.exists():
        logger.error("%s not found", _DB_FILE)
        return None
    try:
        with _DB_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read %s: %s", _DB_FILE, exc)
        return None

    user = data.get(user_id)
    if user is None:
        return None

    if "last_pulse" in user and "engagement_score" not in user:
        user["engagement_score"] = user.pop("last_pulse")

    return user


def save_user_session(
    user_id: str,
    engagement_score: int,
    session_message_count: int = 0,
) -> None:
    """Persist engagement score and timestamp for a user (atomic write)."""
    tmp_path: str | None = None

    if not _DB_FILE.exists():
        logger.warning("%s missing — creating fresh database", _DB_FILE)
        data: dict[str, Any] = {}
    else:
        try:
            with _DB_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read %s for saving: %s", _DB_FILE, exc)
            return

    if user_id not in data:
        logger.info("Creating new entry for %s", user_id)
        data[user_id] = {}

    data[user_id]["engagement_score"] = engagement_score
    data[user_id]["session_message_count"] = session_message_count
    data[user_id]["last_seen"] = time.time()

    if "last_pulse" in data[user_id]:
        del data[user_id]["last_pulse"]

    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(_PROJECT_ROOT), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=4)
        os.replace(tmp_path, _DB_FILE)
    except OSError as exc:
        logger.error("Failed to save session: %s", exc)
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
