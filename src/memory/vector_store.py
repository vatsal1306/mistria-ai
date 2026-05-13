"""Vector store abstraction and implementations for semantic search."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.Logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class VectorStoreResult:
    """A search result from the vector store."""
    memory_id: int
    score: float


class BaseVectorStore(ABC):
    """Abstract base class for memory vector stores."""

    @abstractmethod
    def bootstrap_collection(self, dimension: int) -> None:
        """Ensure the vector collection exists with the required dimension."""
        pass

    @abstractmethod
    def upsert_memory(
        self,
        memory_id: int,
        user_id: int,
        ai_companion_id: int,
        memory_type: str,
        canonical_key: str,
        status: str,
        vector: list[float],
    ) -> None:
        """Upsert a memory vector and its metadata payload."""
        pass

    @abstractmethod
    def delete_memory(self, memory_id: int) -> None:
        """Delete a memory from the vector store."""
        pass

    @abstractmethod
    def search(
        self,
        user_id: int,
        ai_companion_id: int,
        query_vector: list[float],
        limit: int,
    ) -> list[VectorStoreResult]:
        """Search for memories belonging to a specific user and companion."""
        pass


class QdrantVectorStore(BaseVectorStore):
    """Qdrant-backed vector store implementation."""

    def __init__(self, url: str, collection_name: str, enabled: bool = True):
        self.url = url
        self.collection_name = collection_name
        self.enabled = enabled
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy-load the qdrant client and handle connection/import errors."""
        if not self.enabled:
            return None
            
        if self._client is None:
            from src.backend.exceptions import ConfigurationError
            try:
                from qdrant_client import QdrantClient
                self._client = QdrantClient(url=self.url)
            except ImportError as e:
                logger.error("qdrant-client is not installed. Vector search will be disabled.")
                raise ConfigurationError("qdrant-client is not installed. Please install it to use QdrantVectorStore.") from e
            except Exception as e:
                logger.error("Failed to initialize QdrantClient: %s", e)
                raise ConfigurationError(f"Failed to initialize QdrantClient: {e}") from e
                
        return self._client

    def bootstrap_collection(self, dimension: int) -> None:
        client = self._get_client()
        if not client:
            return

        from qdrant_client.models import Distance, VectorParams
        from qdrant_client.http.exceptions import UnexpectedResponse
        from src.backend.exceptions import ConfigurationError
        import time

        max_retries = 5
        retry_delay = 2.0

        for attempt in range(1, max_retries + 1):
            try:
                # Check if collection exists
                client.get_collection(collection_name=self.collection_name)
                logger.debug("Qdrant collection '%s' already exists.", self.collection_name)
                return
            except (UnexpectedResponse, ValueError) as e:
                # If it doesn't exist, create it. ValueError is raised by newer qdrant-client versions
                # UnexpectedResponse by older ones.
                logger.info("Creating Qdrant collection '%s' with dimension %d.", self.collection_name, dimension)
                try:
                    client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
                    )
                    return
                except Exception as create_err:
                    logger.error("Failed to create Qdrant collection: %s", create_err)
                    raise ConfigurationError(f"Failed to create Qdrant collection '{self.collection_name}': {create_err}") from create_err
            except Exception as e:
                if attempt < max_retries:
                    logger.warning("Failed to connect to Qdrant (attempt %d/%d). Retrying in %.1fs...", attempt, max_retries, retry_delay)
                    time.sleep(retry_delay)
                else:
                    logger.error("Failed to connect to Qdrant after %d attempts: %s", max_retries, e)
                    raise ConfigurationError(f"Failed to connect to Qdrant at {self.url} after {max_retries} attempts: {e}") from e

    def upsert_memory(
        self,
        memory_id: int,
        user_id: int,
        ai_companion_id: int,
        memory_type: str,
        canonical_key: str,
        status: str,
        vector: list[float],
    ) -> None:
        client = self._get_client()
        if not client:
            return

        from qdrant_client.models import PointStruct

        payload = {
            "memory_id": memory_id,
            "user_id": user_id,
            "ai_companion_id": ai_companion_id,
            "memory_type": memory_type,
            "canonical_key": canonical_key,
            "status": status,
        }

        try:
            client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
            logger.debug("Upserted memory %d to Qdrant.", memory_id)
        except Exception as e:
            logger.error("Failed to upsert memory %d to Qdrant: %s", memory_id, e)

    def delete_memory(self, memory_id: int) -> None:
        client = self._get_client()
        if not client:
            return

        try:
            client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id],
            )
            logger.debug("Deleted memory %d from Qdrant.", memory_id)
        except Exception as e:
            logger.error("Failed to delete memory %d from Qdrant: %s", memory_id, e)

    def search(
        self,
        user_id: int,
        ai_companion_id: int,
        query_vector: list[float],
        limit: int,
    ) -> list[VectorStoreResult]:
        client = self._get_client()
        if not client:
            return []

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Strictly enforce user_id and ai_companion_id isolation
        # Also only return 'active' status memories
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                ),
                FieldCondition(
                    key="ai_companion_id",
                    match=MatchValue(value=ai_companion_id)
                ),
                FieldCondition(
                    key="status",
                    match=MatchValue(value="active")
                )
            ]
        )

        try:
            response = client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=search_filter,
                limit=limit,
            )
            
            return [VectorStoreResult(memory_id=hit.payload["memory_id"], score=hit.score) for hit in response.points if hit.payload]
        except Exception as e:
            logger.error("Failed to search Qdrant for user %d, companion %d: %s", user_id, ai_companion_id, e)
            return []


class NoOpVectorStore(BaseVectorStore):
    """A disabled vector store that does nothing safely."""

    def bootstrap_collection(self, dimension: int) -> None:
        """Do nothing since this is a no-op store."""
        pass

    def upsert_memory(
        self,
        memory_id: int,
        user_id: int,
        ai_companion_id: int,
        memory_type: str,
        canonical_key: str,
        status: str,
        vector: list[float],
    ) -> None:
        """Do nothing since this is a no-op store."""
        pass

    def delete_memory(self, memory_id: int) -> None:
        """Do nothing since this is a no-op store."""
        pass

    def search(
        self,
        user_id: int,
        ai_companion_id: int,
        query_vector: list[float],
        limit: int,
    ) -> list[VectorStoreResult]:
        """Return an empty list since this is a no-op store."""
        return []
