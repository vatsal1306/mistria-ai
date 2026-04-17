"""Load environment configuration shared across the application."""

from __future__ import annotations

import os

from dotenv import dotenv_values

ROOT_DIR = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))

dotenv_path = os.path.join(ROOT_DIR, ".env")
dotenv_envs = {
    key: value
    for key, value in dotenv_values(dotenv_path, verbose=True).items()
    if value is not None
}

# Runtime environment variables override values from the optional .env file.
envs = {**dotenv_envs, **os.environ}

__all__ = ["ROOT_DIR", "envs"]
