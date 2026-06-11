"""Hardcoded companion option contracts used by the API layer."""

from __future__ import annotations

from typing import Literal

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
