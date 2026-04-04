"""Paths and tunable constants."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FILE = PROJECT_ROOT / "database.json"

MODEL_NAME = "dolphin-llama3"
MODEL_TEMPERATURE = 0.88
MODEL_TOP_P = 0.9
MODEL_MAX_TOKENS = 150

PULSE_MIN = 30
PULSE_MAX = 100
PULSE_DEFAULT = 50
PULSE_DECAY_PER_TURN = 1
PULSE_TRIGGER_BOOST = 15
PULSE_LONG_MSG_BOOST = 5
PULSE_EXCLAIM_BOOST = 4
LONG_MSG_THRESHOLD = 40

AWAY_THRESHOLD_MINUTES = 30

HEAT_TRIGGERS = frozenset(
    [
        "touch", "hard", "want", "please", "body", "closer", "more", "miss",
        "kiss", "lips", "bite", "lick", "suck", "grab", "pull", "push",
        "bed", "naked", "strip", "clothes", "skin", "hot", "sexy", "naughty",
        "dirty", "wet", "tight", "deep", "faster", "harder", "slow",
        "moan", "scream", "whisper", "breathe", "gasp",
        "boobs", "tits", "ass", "pussy", "cock", "dick", "clit",
        "finger", "fingering", "cum", "ride", "thrust", "grind",
        "spank", "choke", "dominate", "submit", "beg",
        "love", "desire", "crave", "need", "ache",
    ],
)
