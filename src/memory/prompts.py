"""Prompt templates for the memory extraction pipeline."""

MEMORY_EXTRACTION_SYSTEM_PROMPT = (
    "You are a memory extraction engine. Given a conversation turn, "
    "identify and extract distinct facts, preferences, events, or relationship details "
    "that the user has shared. Return them as structured JSON."
)

MEMORY_EXTRACTION_USER_PROMPT = """Extract memorable facts from this conversation turn:

{conversation_text}

Return a JSON array of objects, each with "content", "category", and "confidence" fields.
Categories: "fact", "preference", "event", "relationship"."""
