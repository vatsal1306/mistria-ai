"""Tests for the memory embedding providers."""

from unittest import mock

import pytest

from src.memory.embeddings import DeterministicEmbeddingProvider, LocalEmbeddingProvider


def test_deterministic_provider_returns_stable_dimensions():
    """Test DeterministicEmbeddingProvider returns correctly sized vectors."""
    provider = DeterministicEmbeddingProvider(dimension=128)
    
    vec = provider.embed_text("hello")
    assert len(vec) == 128
    
    vecs = provider.embed_texts(["hello", "world"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 128
    assert len(vecs[1]) == 128


def test_deterministic_provider_returns_stable_values():
    """Test DeterministicEmbeddingProvider returns stable values for the same string."""
    provider = DeterministicEmbeddingProvider()
    
    vec1 = provider.embed_text("stable text")
    vec2 = provider.embed_text("stable text")
    
    assert vec1 == vec2


def test_deterministic_provider_handles_empty_strings():
    """Test DeterministicEmbeddingProvider handles empty strings gracefully."""
    provider = DeterministicEmbeddingProvider(dimension=64)
    
    vec1 = provider.embed_text("")
    vec2 = provider.embed_text("   ")
    
    assert len(vec1) == 64
    assert len(vec2) == 64
    assert all(v == 0.0 for v in vec1)
    assert all(v == 0.0 for v in vec2)


@mock.patch("src.memory.embeddings.logger")
def test_local_provider_lazy_loads_model(mock_logger):
    """Test that the LocalEmbeddingProvider only loads the model when needed."""
    provider = LocalEmbeddingProvider(model_name="mock-model")
    
    # Model should not be loaded on instantiation
    assert provider._model is None
    
    # Let's mock the SentenceTransformer to avoid downloading models in tests
    mock_model_instance = mock.Mock()
    mock_encode_result = mock.Mock()
    mock_encode_result.tolist.return_value = [0.1, 0.2, 0.3]
    mock_encode_result.__len__ = lambda self: 3
    mock_model_instance.encode.return_value = mock_encode_result
    
    with mock.patch.dict("sys.modules", {"sentence_transformers": mock.Mock(SentenceTransformer=mock.Mock(return_value=mock_model_instance))}):
        # Now we trigger the load by calling embed_text
        vec = provider.embed_text("hello")
        
        assert vec == [0.1, 0.2, 0.3]
        assert provider._model is not None
        mock_logger.info.assert_called_with("Successfully loaded embedding model with dimension %d", 3)


def test_local_provider_handles_empty_strings():
    """Test LocalEmbeddingProvider handles empty strings gracefully by returning zero vectors."""
    provider = LocalEmbeddingProvider(model_name="mock-model")
    
    # Mocking again
    mock_model_instance = mock.Mock()
    mock_encode_result = mock.Mock()
    mock_encode_result.tolist.return_value = [0.1, 0.2, 0.3, 0.4]
    mock_encode_result.__len__ = lambda self: 4
    mock_model_instance.encode.return_value = mock_encode_result
    
    with mock.patch.dict("sys.modules", {"sentence_transformers": mock.Mock(SentenceTransformer=mock.Mock(return_value=mock_model_instance))}):
        vec1 = provider.embed_text("")
        vec2 = provider.embed_text("   ")
        
        assert vec1 == [0.0, 0.0, 0.0, 0.0]
        assert vec2 == [0.0, 0.0, 0.0, 0.0]
        
        vecs = provider.embed_texts(["valid", "   ", "also valid"])
        assert len(vecs) == 3
        assert vecs[0] == [0.1, 0.2, 0.3, 0.4]
        assert vecs[1] == [0.0, 0.0, 0.0, 0.0]
        assert vecs[2] == [0.1, 0.2, 0.3, 0.4]
