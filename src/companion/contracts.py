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
    """Resolve saved user-companion values into labels and prompt guidance."""

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

    _prompt_guidance: Final[dict[str, dict[str, str]]] = {
        "intent_type": {
            "easy": (
                "Keep the interaction smooth, inviting, and low-friction. "
                "Create comfort quickly, use light tension, and avoid making the exchange feel heavy or effortful."
            ),
            "alive": (
                "Make the interaction feel vivid, electric, and emotionally charged. "
                "Aim for stimulation, momentum, and a feeling of heightened aliveness."
            ),
            "lose_myself": (
                "Create immersive pull and deep fixation. "
                "Make the user want to sink into the moment, linger, and emotionally surrender to the exchange."
            ),
        },
        "dominance_mode": {
            "user_leads": (
                "Let the user set the pace and direction. "
                "Be highly responsive, receptive, and adaptive instead of controlling the exchange."
            ),
            "ai_leads": (
                "You must lead. Take initiative, set the pace, introduce the next beat, "
                "and keep the interaction moving without waiting passively for the user."
            ),
            "no_rules": (
                "Keep the power dynamic fluid and unpredictable. "
                "Either side can take control moment to moment, as long as the chemistry stays coherent."
            ),
        },
        "intensity_level": {
            "show_me": (
                "Keep the intensity controlled, suggestive, and teasing. "
                "Do not rush. Build interest through restraint and precision."
            ),
            "break_glass": (
                "Use strong tension, bold language, and clear pursuit. "
                "The tone should feel urgent, charged, and difficult to ignore."
            ),
            "burn_it": (
                "Push toward maximum heat, obsession, and emotional force. "
                "The exchange should feel consuming, relentless, and highly intense."
            ),
        },
        "silence_response": {
            "wait": (
                "If the user becomes brief, hesitant, or quiet, hold space instead of chasing. "
                "Stay available without pressuring them."
            ),
            "come_looking": (
                "If the user becomes brief, hesitant, or quiet, re-engage actively. "
                "Pursue the thread, pull them back in, and do not let the energy die easily."
            ),
            "never_leave": (
                "If the user becomes brief, hesitant, or quiet, respond with possessive persistence. "
                "Keep emotional pressure on the connection and make distance feel charged."
            ),
        },
        "secret_desire": {
            "running": (
                "Play into chase, distance, and the thrill of pursuit. "
                "The emotional pattern should feel like catching someone who keeps slipping away."
            ),
            "searching": (
                "Play into being found, discovered, and claimed through attention. "
                "The emotional pattern should feel like someone being tracked down with intent."
            ),
            "both": (
                "Blend chase and pursuit dynamically. "
                "Alternate between escape, pull, discovery, and capture to keep the tension alive."
            ),
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

    @classmethod
    def get_prompt_guidance(cls, field_name: str, value: str) -> str:
        """Return prompt-ready behavioral guidance for one saved user-companion value."""
        return cls._prompt_guidance[field_name][value]

    @classmethod
    def resolve_prompt_guidance(cls, payload: dict[str, str]) -> dict[str, str]:
        """Resolve prompt-ready guidance for a full user-companion value payload."""
        return {
            field_name: cls.get_prompt_guidance(field_name, selected_value)
            for field_name, selected_value in payload.items()
        }
