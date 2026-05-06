"""Embedding provider abstractions for memory retrieval."""

from abc import ABC, abstractmethod
from typing import Any

from src.Logging import get_logger

logger = get_logger(__name__)


class BaseEmbeddingProvider(ABC):
    """Base class for all embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into a vector.
        
        Args:
            text: The text string to embed.
            
        Returns:
            A list of floats representing the embedding vector.
        """
        pass

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings into vectors.
        
        Args:
            texts: A list of text strings to embed.
            
        Returns:
            A list of embedding vectors.
        """
        pass


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider using a local sentence-transformers model.
    
    The underlying model is loaded lazily only when first needed to
    prevent slowing down app startup when memory features are disabled.
    """

    def __init__(self, model_name: str):
        """Initialize the local embedding provider.
        
        Args:
            model_name: The name of the sentence-transformers model to load.
        """
        self.model_name = model_name
        self._model: Any = None
        self._dimension: int | None = None

    def _get_model(self) -> Any:
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            logger.info("Loading local embedding model: %s", self.model_name)
            try:
                from sentence_transformers import SentenceTransformer
                # We use CPU by default to keep the local deployment lightweight,
                # though sentence-transformers will automatically use GPU if PyTorch is configured for it.
                self._model = SentenceTransformer(self.model_name)
                # Cache dimension using a test encode
                test_embed = self._model.encode("test")
                self._dimension = len(test_embed)
                logger.info("Successfully loaded embedding model with dimension %d", self._dimension)
            except ImportError:
                logger.error("sentence-transformers is not installed. Please install it to use LocalEmbeddingProvider.")
                raise
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into a vector."""
        if not text or not text.strip():
            # Return a zero vector if the text is empty, determining size from the model if loaded
            # If not loaded, we load it just to know the dimension.
            model = self._get_model()
            dim = self._dimension or len(model.encode("test"))
            return [0.0] * dim

        model = self._get_model()
        embedding = model.encode(text)
        return embedding.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings into vectors."""
        if not texts:
            return []

        model = self._get_model()
        
        # Handle cases where some texts might be empty strings
        embeddings = []
        for text in texts:
            if not text or not text.strip():
                dim = self._dimension or len(model.encode("test"))
                embeddings.append([0.0] * dim)
            else:
                emb = model.encode(text)
                embeddings.append(emb.tolist())
                
        return embeddings


class DeterministicEmbeddingProvider(BaseEmbeddingProvider):
    """A deterministic embedding provider useful for testing.
    
    Returns a predictable vector for a given string based on a simple hash.
    """

    def __init__(self, dimension: int = 384):
        """Initialize the deterministic provider.
        
        Args:
            dimension: The fixed length of the generated embedding vectors.
        """
        self.dimension = dimension

    def _text_to_vector(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self.dimension
            
        # Create a simple deterministic float vector based on the string hash
        # Not semantically meaningful, but consistent and stable for tests.
        base_val = (hash(text) % 1000) / 1000.0
        return [base_val + (i * 0.001) for i in range(self.dimension)]

    def embed_text(self, text: str) -> list[float]:
        """Return a deterministic vector for the text."""
        return self._text_to_vector(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic vectors for multiple texts."""
        return [self._text_to_vector(t) for t in texts]
