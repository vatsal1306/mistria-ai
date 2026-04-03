"""Paths and tunable constants."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FILE = PROJECT_ROOT / "database.json"

MODEL_NAME = "dolphin-llama3"
MODEL_TEMPERATURE = 0.88
MODEL_TOP_P = 0.9

PULSE_MIN = 30
PULSE_MAX = 100
PULSE_DEFAULT = 50
PULSE_DECAY_PER_TURN = 3
PULSE_TRIGGER_BOOST = 12
PULSE_LONG_MSG_BOOST = 5
PULSE_EXCLAIM_BOOST = 3
LONG_MSG_THRESHOLD = 40

AWAY_THRESHOLD_MINUTES = 30

HEAT_TRIGGERS = frozenset(
    [
        "touch",
        "hard",
        "want",
        "please",
        "body",
        "closer",
        "more",
        "miss",
    ],
)
