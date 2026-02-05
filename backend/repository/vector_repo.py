from typing import List, Dict, Optional, Any, Union
import logging
import uuid
try:
    from qdrant_client import QdrantClient, models
except ImportError:
    QdrantClient = None
    models = None

from backend.core.database import vector_db

logger = logging.getLogger(__name__)

class VectorRepository:
    def __init__(self):
        self.client = vector_db.qdrant

    def is_available(self) -> bool:
        return self.client is not None

    def check_collection_exists(self, collection_name: str) -> bool:
        if not self.client: 
            return False
        return self.client.collection_exists(collection_name)

    def create_collection(self, collection_name: str, vector_size: int = 1536):
        """
        Create a collection if it doesn't exist.
        """
        if not self.client: 
            return
        
        if self.check_collection_exists(collection_name):
            return

        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, 
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            raise

    def delete_collection(self, collection_name: str):
        if not self.client: 
            return
        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.info(f"Deleted Qdrant collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Failed to delete collection {collection_name}: {e}")

    def upsert_vectors(self, 
                       collection_name: str, 
                       vectors: List[List[float]], 
                       payloads: List[Dict], 
                       ids: Optional[List[str]] = None):
        if not self.client: 
            return
        
        points = []
        for i, vector in enumerate(vectors):
            # Generate UUID if ID not provided
            _id = ids[i] if ids and i < len(ids) else str(uuid.uuid4())
            
            points.append(models.PointStruct(
                id=_id, 
                vector=vector, 
                payload=payloads[i]
            ))
            
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )
            logger.info(f"Upserted {len(points)} points to {collection_name}")
        except Exception as e:
            logger.error(f"Failed to upsert vectors to {collection_name}: {e}")
            raise

    def search(self, 
               collection_name: str, 
               query_vector: List[float], 
               limit: int = 4, 
               filter_conditions: Optional[Dict] = None) -> List[Any]:
        if not self.client: 
            return []
        
        query_filter = None
        if filter_conditions:
            must_conditions = []
            for k, v in filter_conditions.items():
                must_conditions.append(
                    models.FieldCondition(
                        key=k, 
                        match=models.MatchValue(value=v)
                    )
                )
            query_filter = models.Filter(must=must_conditions)

        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit
            )
            return results
        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {e}")
            return []

    def count(self, collection_name: str) -> int:
        if not self.client:
            return 0
        try:
            info = self.client.get_collection(collection_name)
            return info.points_count
        except Exception:
            return 0

# Global instance
vector_repo = VectorRepository()
