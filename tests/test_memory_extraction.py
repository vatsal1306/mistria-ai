"""Tests for memory extraction schemas and prompts."""

import pytest
from pydantic import ValidationError

from src.memory.schemas import MemoryExtraction
from src.prompts import MEMORY_EXTRACTION_SYSTEM_PROMPT


def test_memory_extraction_schema_valid_payload():
    """Test that a valid memory extraction payload is parsed successfully."""
    payload = {
        "should_remember": True,
        "memory_type": "preference",
        "canonical_key": "likes_bdsm",
        "content": "User enjoys intense BDSM dynamics.",
        "importance": 5,
        "confidence": 0.95,
        "reason": "Explicit statement of intimate preference."
    }
    
    memory = MemoryExtraction.model_validate(payload)
    
    assert memory.should_remember is True
    assert memory.memory_type == "preference"
    assert memory.canonical_key == "likes_bdsm"
    assert memory.content == "User enjoys intense BDSM dynamics."
    assert memory.importance == 5
    assert memory.confidence == 0.95
    assert memory.reason == "Explicit statement of intimate preference."


def test_memory_extraction_schema_rejects_invalid_type():
    """Test that invalid memory types are rejected."""
    payload = {
        "should_remember": True,
        "memory_type": "unknown_type",
        "canonical_key": "some_key",
        "content": "some content",
        "importance": 3,
        "confidence": 0.5,
        "reason": "test"
    }
    
    with pytest.raises(ValidationError) as exc:
        MemoryExtraction.model_validate(payload)
        
    assert "Input should be 'fact', 'preference', 'pattern' or 'emotional'" in str(exc.value)


def test_memory_extraction_schema_rejects_invalid_importance():
    """Test that importance outside 1-5 is rejected."""
    payload = {
        "should_remember": True,
        "memory_type": "fact",
        "canonical_key": "age",
        "content": "User is 30.",
        "importance": 6,  # Invalid
        "confidence": 0.9,
        "reason": "test"
    }
    
    with pytest.raises(ValidationError) as exc:
        MemoryExtraction.model_validate(payload)
        
    assert "Input should be less than or equal to 5" in str(exc.value)


def test_memory_extraction_schema_rejects_invalid_confidence():
    """Test that confidence outside 0.0-1.0 is rejected."""
    payload = {
        "should_remember": True,
        "memory_type": "fact",
        "canonical_key": "age",
        "content": "User is 30.",
        "importance": 3,
        "confidence": 1.5,  # Invalid
        "reason": "test"
    }
    
    with pytest.raises(ValidationError) as exc:
        MemoryExtraction.model_validate(payload)
        
    assert "Input should be less than or equal to 1" in str(exc.value)


def test_memory_extraction_prompts_contain_required_instructions():
    """Test that the extraction prompt contains critical behavior constraints."""
    prompt = MEMORY_EXTRACTION_SYSTEM_PROMPT
    
    # Must contain adult content allowance
    assert "consenting adults" in prompt.lower()
    assert "sexual preferences" in prompt.lower()
    
    # Must prioritize explicit memory commands
    assert "remember this" in prompt.lower()
    
    # Must handle isolation
    assert "isolated from companion memories" in prompt.lower()
    
    # Must ignore roleplay
    assert "roleplay-specific fictional state" in prompt.lower()
