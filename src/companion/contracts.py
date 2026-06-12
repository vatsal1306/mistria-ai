"""Hardcoded companion option contracts used by the API layer."""

from __future__ import annotations

from typing import Literal

AIGender = Literal["Female", "Male", "Other"]
AIEthnicity = Literal[
    "African Descent",
    "South Asian",
    "Eastern European",
    "East Asian",
    "Latinx",
    "Latina",
    "Middle Eastern",
]
AIPersonality = Literal[
    "Flirty",
    "Obsessed",
    "Playful",
    "Dominant",
    "Mysterious",
    "Caring",
    "Confident",
    "Sensual",
    "Passionate",
]
AIBust = Literal["Small", "Natural", "Large", "Extra Large"]
AIHeight = Literal["Short", "Average", "Tall", "Very Tall"]

# Legacy option aliases retained for import compatibility. The active companion
# request/response schemas no longer expose these fields.
AIStyle = Literal["Realistic", "Anime", "Cartoon", "Retro Noir"]
AIEyeColor = Literal["Brown", "Blue", "Green", "Hazel", "Gray", "Black"]
AIHairStyle = Literal["Short", "Straight", "Long", "Curly", "Braids", "Pixie"]
AIHairColor = Literal["Black", "Brunette", "Blonde", "Pink", "Red", "White"]
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
