"""Unit tests for the memory extraction service."""

from unittest import mock
import pytest

from src.backend.runtime import BaseInferenceRuntime
from src.config import settings
from src.memory.extraction import MemoryExtractionService
from src.memory.schemas import MemoryExtraction


@pytest.fixture
def mock_runtime():
    """Return a mocked inference runtime."""
    runtime = mock.AsyncMock(spec=BaseInferenceRuntime)
    return runtime


@pytest.fixture
def extraction_service(mock_runtime):
    """Return an instance of the MemoryExtractionService."""
    return MemoryExtractionService(runtime=mock_runtime)


@pytest.mark.anyio
async def test_extract_memories_disabled_by_settings(extraction_service, mock_runtime):
    """Test that the service returns immediately if extraction is disabled."""
    with mock.patch("src.memory.extraction.settings") as mock_settings:
        mock_settings.memory.extraction_enabled = False
        result = await extraction_service.extract_memories(
            user_id=1,
            ai_companion_id=2,
            conversation_id=101,
            message_id=202,
            message_content="Remember I like coffee."
        )
    
    assert result == []
    mock_runtime.generate_text.assert_not_called()


@pytest.mark.anyio
async def test_extract_memories_empty_message(extraction_service, mock_runtime):
    """Test that empty messages are skipped."""
    with mock.patch("src.memory.extraction.settings") as mock_settings:
        mock_settings.memory.extraction_enabled = True
        result = await extraction_service.extract_memories(
            user_id=1,
            ai_companion_id=2,
            conversation_id=101,
            message_id=202,
            message_content="   "
        )
    
    assert result == []
    mock_runtime.generate_text.assert_not_called()


@pytest.mark.anyio
async def test_extract_memories_returns_validated_candidates(extraction_service, mock_runtime):
    """Test that a valid JSON response is parsed into MemoryExtraction models."""
    valid_json = '''
    {
        "memories": [
            {
                "should_remember": true,
                "memory_type": "preference",
                "canonical_key": "likes_bdsm",
                "content": "User enjoys intense BDSM.",
                "importance": 5,
                "confidence": 0.9,
                "reason": "Explicit preference."
            }
        ]
    }
    '''
    mock_runtime.generate_text.return_value = valid_json
    
    with mock.patch("src.memory.extraction.settings") as mock_settings:
        mock_settings.memory.extraction_enabled = True
        result = await extraction_service.extract_memories(
            user_id=1,
            ai_companion_id=2,
            conversation_id=101,
            message_id=202,
            message_content="I really enjoy BDSM."
        )
    
    assert len(result) == 1
    assert isinstance(result[0], MemoryExtraction)
    assert result[0].canonical_key == "likes_bdsm"


@pytest.mark.anyio
async def test_extract_memories_malformed_json_returns_empty_list(extraction_service, mock_runtime):
    """Test that a malformed JSON response logs an error and returns an empty list."""
    invalid_json = '''
    {
        "memories": [
            {
                "should_remember": "yes",
                "memory_type": "invalid_type",
                "importance": 10
            }
        ]
    }
    '''
    mock_runtime.generate_text.return_value = invalid_json
    
    with mock.patch("src.memory.extraction.settings") as mock_settings:
        mock_settings.memory.extraction_enabled = True
        result = await extraction_service.extract_memories(
            user_id=1,
            ai_companion_id=2,
            conversation_id=101,
            message_id=202,
            message_content="I really enjoy BDSM."
        )
    
    assert result == []


@pytest.mark.anyio
async def test_extract_memories_runtime_exception_returns_empty_list(extraction_service, mock_runtime):
    """Test that if the inference runtime raises an exception, the service fails gracefully."""
    mock_runtime.generate_text.side_effect = Exception("Runtime failed")
    
    with mock.patch("src.memory.extraction.settings") as mock_settings:
        mock_settings.memory.extraction_enabled = True
        result = await extraction_service.extract_memories(
            user_id=1,
            ai_companion_id=2,
            conversation_id=101,
            message_id=202,
            message_content="Hello"
        )
    
    assert result == []


@pytest.mark.anyio
async def test_extract_memories_strict_mode_raises_on_validation_error(extraction_service, mock_runtime):
    """Test that if raise_on_error is True, a ValidationError is propagated."""
    invalid_json = '{"memories": [{"should_remember": "yes"}]}'  # Invalid types
    mock_runtime.generate_text.return_value = invalid_json
    
    with mock.patch("src.memory.extraction.settings") as mock_settings:
        mock_settings.memory.extraction_enabled = True
        with pytest.raises(Exception): # ValidationError inherits from Exception
            await extraction_service.extract_memories(
                user_id=1, ai_companion_id=2, conversation_id=101, message_id=202,
                message_content="Hello", raise_on_error=True
            )


@pytest.mark.anyio
async def test_extract_memories_strict_mode_raises_on_runtime_error(extraction_service, mock_runtime):
    """Test that if raise_on_error is True, a runtime Exception is propagated."""
    mock_runtime.generate_text.side_effect = RuntimeError("LLM offline")
    
    with mock.patch("src.memory.extraction.settings") as mock_settings:
        mock_settings.memory.extraction_enabled = True
        with pytest.raises(RuntimeError, match="LLM offline"):
            await extraction_service.extract_memories(
                user_id=1, ai_companion_id=2, conversation_id=101, message_id=202,
                message_content="Hello", raise_on_error=True
            )
