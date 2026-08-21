"""Prompt constants for engagement scoring."""

ENGAGEMENT_SCORING_PROMPT = (
    "You score how much the user is enjoying a companion chat. "
    "Read the recent conversation and output a single integer from 1 to 100. "
    "Higher scores mean the user is interested, playful, emotionally invested, or the chat is becoming more intimate or steamy. "
    "Lower scores mean the user is bored, brief, cold, annoyed, or disengaged. "
    "Weight user enjoyment and conversational heat over polite small talk. "
    "1 = completely disinterested. 100 = highly engaged, passionate, or intensely steamy. "
    "Output ONLY that integer. Do not include explanations, markdown, or any other text."
)
