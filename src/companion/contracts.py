"""Hardcoded companion option contracts used by the API layer."""

from __future__ import annotations

from typing import Final, Literal

IntentType = Literal["easy", "alive", "lose_myself"]
DominanceMode = Literal["user_leads", "ai_leads", "no_rules"]
IntensityLevel = Literal["show_me", "break_glass", "burn_it"]
SilenceResponse = Literal["wait", "come_looking", "never_leave"]
SecretDesire = Literal["running", "searching", "both"]

AIGender = Literal["Female", "Male", "Other"]
AIStyle = Literal["Realistic", "Anime", "Cartoon", "Retro Noir"]
AIEthnicity = Literal[
    "African Descent",
    "South Asian",
    "Eastern European",
    "East Asian",
    "Latinx",
    "Middle Eastern",
]
AIEyeColor = Literal["Brown", "Blue", "Green", "Hazel", "Gray", "Black"]
AIHairStyle = Literal["Short", "Straight", "Long", "Curly", "Braids", "Pixie"]
AIHairColor = Literal["Black", "Brunette", "Blonde", "Pink", "Red", "White"]
AIPersonality = Literal[
    "Seductive",
    "Adventurous",
    "Confident",
    "Ambitious",
    "Passionate",
    "Submissive",
    "Dominant",
    "Sensual",
    "Playful",
    "Intellectual",
    "Caring",
    "Mysterious",
]
AIVoice = Literal["Calm", "Breathy", "Confident", "Playful", "Deep", "Soft"]
AIConnection = Literal[
    "New Encounter",
    "Casual Hookup",
    "Friends With Benefits",
    "Secret Affair",
    "Passionate Lover",
    "Dominant Partner",
    "Submissive Partner",
    "Long-Distance Desire",
    "Online Fantasy",
]


class UserCompanionLabelCatalog:
    """Resolve saved user-companion values into frontend labels."""

    _labels: Final[dict[str, dict[str, str]]] = {
        "intent_type": {
            "easy": "Something Easy",
            "alive": "I Want to Feel Alive",
            "lose_myself": "I Want to Lose Myself",
        },
        "dominance_mode": {
            "user_leads": "I Lead",
            "ai_leads": "She Leads",
            "no_rules": "No Rules",
        },
        "intensity_level": {
            "show_me": "Show me what I want",
            "break_glass": "Break the Glass",
            "burn_it": "Burn it all",
        },
        "silence_response": {
            "wait": "I'd wait",
            "come_looking": "I'd come looking",
            "never_leave": "I'd make sure you never leave",
        },
        "secret_desire": {
            "running": "Running",
            "searching": "Searching",
            "both": "Both",
        },
    }

    @classmethod
    def get_label(cls, field_name: str, value: str) -> str:
        """Return the display label for one saved user-companion value."""
        return cls._labels[field_name][value]

    @classmethod
    def resolve_payload_labels(cls, payload: dict[str, str]) -> dict[str, str]:
        """Resolve labels for a full user-companion value payload."""
        return {
            field_name: cls.get_label(field_name, selected_value)
            for field_name, selected_value in payload.items()
        }
