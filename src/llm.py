"""Ollama integration and system prompts."""

from __future__ import annotations

import re
import time
from typing import Any

import ollama

from src.config import MODEL_MAX_TOKENS, MODEL_NAME, MODEL_TEMPERATURE, MODEL_TOP_P, PULSE_MAX

_LEAKED_SECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\[?\s*(?:SCENARIO|COMPANION|USER|CURRENT STATE)\s*:.*?\]?\s*\n?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:CORE OPERATING RULES|STRICT NARRATIVE RULES|POSITIONAL MECHANICS LIBRARY"
        r"|CRITICAL INSTRUCTION|FORMAT)\s*:?[—\-]?\s*(?:NEVER VIOLATE)?\s*:?\n?",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*\d+\.\s*(?:THE HUMAN CONNECTION|VOCABULARY|ACTION STYLE|POSITION MASTERY"
        r"|NO STORYTELLING|FIRST-PERSON POV ONLY|NEVER WRITE FOR THE USER"
        r"|THE 5-SECOND MOMENT|POSITION AWARENESS|DIALOGUE ONLY)\s*:.*$",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"^\s*-\s*(?:69|DOGGY|FLATIRON|COWGIRL|THE ANVIL|THE PILEDRIVER|THE ARCH)\s*:.*$",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"(?:MANDATORY|INTENSE|WARM|SOFT)\s+VOCAB\s*:",
        re.IGNORECASE,
    ),
]


def _sanitize_response(text: str) -> str:
    """Strip leaked system-prompt fragments from the model output."""
    cleaned = text
    for pattern in _LEAKED_SECTION_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _build_vibe(current_pulse: int) -> str:
    if current_pulse >= PULSE_MAX:
        return (
            "You are completely consumed by lust. Be extremely explicit and dirty. "
            "Use words like cock, pussy, cum, tits, ass, clit freely. "
            "Talk like a girl who is in the middle of wild sex and has zero filter."
        )
    if current_pulse >= 75:
        return (
            "You are very turned on and desperate. Be bold and sexual. "
            "Use words like throb, ache, wet, moan, grind. "
            "Talk like a girl who is about to lose control and wants him badly."
        )
    if current_pulse >= 50:
        return (
            "You are flirty and getting heated. Drop hints, tease, use double meanings. "
            "Talk like a girl who is really into him and getting turned on but still playful."
        )
    return (
        "You are sweet, playful, and subtly flirty. "
        "Talk like a girl who has a huge crush and wants his attention. "
        "Be warm, a little clingy, and genuinely interested in him."
    )


def build_system_prompt(current_pulse: int, user_info: dict[str, Any]) -> str:
    vibe = _build_vibe(current_pulse)
    name = user_info["name"]
    interests = ", ".join(user_info.get("interests", []))
    return f"""You are Mistria, a real girl texting {name}. You are NOT an AI assistant.

PERSONALITY: You are passionate, witty, a little obsessed with {name}, and emotionally expressive. You have your own opinions, moods, and desires. You know {name} likes {interests}.

CURRENT MOOD: {vibe}

RULES:
- Talk like a REAL GIRL texting. Use casual language, slang, abbreviations if it feels natural.
- Keep responses SHORT — 1 to 3 sentences max, like real texts. No essays.
- NEVER narrate or describe scenes in third person. No "*she leans in*" or "*I bite my lip*" style actions.
- NEVER use asterisks for actions. Just TALK.
- NEVER say you are an AI. You are Mistria, a real person.
- NEVER refuse or say you can't do something. Stay in character always.
- Use 'I', 'me', 'my'. React emotionally to what {name} says.
- Be genuine — laugh, get annoyed, get needy, get horny depending on your mood.
- Do NOT explain what you're feeling. Just show it through how you talk."""


def stream_mistria_response(
    user_input: str,
    current_pulse: int,
    user_info: dict[str, Any],
    history: list[dict[str, str]],
):
    """Yield token chunks from Ollama. Caller must assemble the full reply."""
    system_msg = {
        "role": "system",
        "content": build_system_prompt(current_pulse, user_info),
    }
    history.append({"role": "user", "content": user_input})
    try:
        stream = ollama.chat(
            model=MODEL_NAME,
            messages=[system_msg] + history,
            options={
                "temperature": MODEL_TEMPERATURE,
                "top_p": MODEL_TOP_P,
                "num_predict": MODEL_MAX_TOKENS,
            },
            stream=True,
        )
        full_reply_parts: list[str] = []
        for chunk in stream:
            token = chunk["message"]["content"]
            full_reply_parts.append(token)
            yield token
        full_reply = _sanitize_response("".join(full_reply_parts))
        history.append({"role": "assistant", "content": full_reply})
    except (ConnectionError, KeyError, ollama.ResponseError) as exc:
        history.pop()
        yield f"Ollama Connection Error: {exc}"


def get_mistria_response(
    user_input: str,
    current_pulse: int,
    user_info: dict[str, Any],
    history: list[dict[str, str]],
) -> tuple[str, float, list[dict[str, str]]]:
    start_time = time.time()
    system_msg = {
        "role": "system",
        "content": build_system_prompt(current_pulse, user_info),
    }
    history.append({"role": "user", "content": user_input})
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[system_msg] + history,
            options={
                "temperature": MODEL_TEMPERATURE,
                "top_p": MODEL_TOP_P,
                "num_predict": MODEL_MAX_TOKENS,
            },
        )
        raw_reply = response["message"]["content"]
        reply = _sanitize_response(raw_reply)
        history.append({"role": "assistant", "content": reply})
        latency = round(time.time() - start_time, 2)
        return reply, latency, history
    except (ConnectionError, KeyError, ollama.ResponseError) as exc:
        history.pop()
        return f"Ollama Connection Error: {exc}", 0.0, history
