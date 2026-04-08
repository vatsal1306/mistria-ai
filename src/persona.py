"""
Companion persona generation framework.

Provides data structures and templates for creating AI companion personas.
Companions are stored in companions.json and loaded at runtime.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

_COMPANIONS_FILE = Path(settings.root_dir) / "companions.json"


@dataclass
class CompanionPersona:
    """Represents a fully configured AI companion."""

    id: str
    name: str
    personality: list[str]
    tone: str
    backstory: str
    interests: list[str]
    first_message: str
    active: bool = True

    @property
    def personality_summary(self) -> str:
        return ", ".join(self.personality)

    @property
    def interests_summary(self) -> str:
        return ", ".join(self.interests)


PERSONALITY_TEMPLATES: dict[str, dict[str, Any]] = {
    "caring": {
        "personality": ["nurturing", "empathetic", "warm", "patient"],
        "tone": "Gentle and supportive, always makes you feel safe",
        "backstory": "Grew up in a close family. Values emotional connection "
                     "above everything. She remembers the little things.",
    },
    "playful": {
        "personality": ["witty", "spontaneous", "flirtatious", "adventurous"],
        "tone": "Teasing and fun-loving, keeps you on your toes",
        "backstory": "Free spirit who lives for laughter and surprises. "
                     "She turns everything into a game worth playing.",
    },
    "dominant": {
        "personality": ["confident", "assertive", "commanding", "protective"],
        "tone": "Direct and authoritative, knows exactly what she wants",
        "backstory": "Natural leader who takes charge. She's intense, "
                     "focused, and expects nothing less than your full attention.",
    },
    "mysterious": {
        "personality": ["enigmatic", "intellectual", "alluring", "deep"],
        "tone": "Cryptic and magnetic, leaves you wanting more",
        "backstory": "She reveals herself in layers. Every conversation "
                     "uncovers something new, and she always keeps you guessing.",
    },
    "passionate": {
        "personality": ["passionate", "emotionally expressive", "obsessive", "intense"],
        "tone": "Flirtatious and emotionally reactive, wears her heart on her sleeve",
        "backstory": "Lives for intensity. When she's into someone, "
                     "they become her entire world.",
    },
}


def load_companion(companion_id: str) -> CompanionPersona | None:
    """Load a single companion persona from companions.json."""
    if not _COMPANIONS_FILE.exists():
        logger.error("companions.json not found at %s", _COMPANIONS_FILE)
        return None

    try:
        with _COMPANIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read companions.json: %s", exc)
        return None

    companion_data = data.get(companion_id)
    if not companion_data:
        return None

    return CompanionPersona(
        id=companion_id,
        name=companion_data.get("name", companion_id),
        personality=companion_data.get("personality", []),
        tone=companion_data.get("tone", ""),
        backstory=companion_data.get("backstory", ""),
        interests=companion_data.get("interests", []),
        first_message=companion_data.get("first_message", "Hey there."),
        active=companion_data.get("active", True),
    )


def load_all_companions() -> list[CompanionPersona]:
    """Load all active companion personas."""
    if not _COMPANIONS_FILE.exists():
        return []

    try:
        with _COMPANIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read companions.json: %s", exc)
        return []

    companions = []
    for cid, cdata in data.items():
        if not cdata.get("active", True):
            continue
        companions.append(CompanionPersona(
            id=cid,
            name=cdata.get("name", cid),
            personality=cdata.get("personality", []),
            tone=cdata.get("tone", ""),
            backstory=cdata.get("backstory", ""),
            interests=cdata.get("interests", []),
            first_message=cdata.get("first_message", "Hey there."),
            active=True,
        ))
    return companions


def generate_persona_from_traits(
    companion_id: str,
    name: str,
    archetype: str,
    user_interests: list[str] | None = None,
) -> CompanionPersona:
    """Generate a companion persona from a personality archetype template."""
    template = PERSONALITY_TEMPLATES.get(archetype, PERSONALITY_TEMPLATES["playful"])

    return CompanionPersona(
        id=companion_id,
        name=name,
        personality=template["personality"],
        tone=template["tone"],
        backstory=template["backstory"],
        interests=user_interests or ["conversation", "connection"],
        first_message="Hey... I don't usually text first, but something about you caught my eye.",
        active=True,
    )
