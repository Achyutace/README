from typing import List, Dict, Optional, Any, Union
import logging
import uuid

try:
    from qdrant_client import models
except ImportError:
    models = None

from backend.core.database import vector_db

logger = logging.getLogger(__name__)

class VectorRepository:
    """向量数据库仓库，封装 Qdrant 常用操作。"""

    def __init__(self):
        self.client = vector_db.qdrant

    @property
    def is_available(self) -> bool:
        """检查数据库连接是否就绪。"""
        return self.client is not None

    # --- 过滤器构建 ---
    
    def _to_filter(self, filters: Optional[Dict]) -> Optional[Any]:
        """将 Python 字典转换为 Qdrant 过滤对象。支持 'exclude_' 前缀表示 must_not。"""
        if not filters or not models:
            return None
        
        must_conditions = []
        must_not_conditions = []

        for k, v in filters.items():
            if k.startswith("exclude_"):
                must_not_conditions.append(
                    models.FieldCondition(key=k[len("exclude_"):], match=models.MatchValue(value=v))
                )
            else:
                must_conditions.append(
                    models.FieldCondition(key=k, match=models.MatchValue(value=v))
                )
        
        return models.Filter(must=must_conditions, must_not=must_not_conditions)

    # --- 集合管理 (Management) ---

    def create_collection(self, collection_name: str, vector_size: int = 1536):
        """初始化集合"""
        if not self.is_available or self.client.collection_exists(collection_name):
            return
            
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size, 
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"Initialized collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")

    def delete_collection(self, collection_name: str):
        """销毁整个集合（不可恢复）。"""
        if not self.is_available: return
        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.warning(f"Destroyed collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")

    # --- 数据索引 (Indexing & Search) ---

    def upsert_vectors(self, collection_name: str, vectors: List[List[float]], payloads: List[Dict], ids: Optional[List[str]] = None):
        """批量写入或更新向量点及其元数据。"""
        if not self.is_available: return
        
        try:
            points = [
                models.PointStruct(
                    id=ids[i] if ids and i < len(ids) else str(uuid.uuid4()), 
                    vector=v, 
                    payload=payloads[i]
                ) for i, v in enumerate(vectors)
            ]
            self.client.upsert(collection_name=collection_name, points=points)
            logger.debug(f"Upserted {len(points)} points to {collection_name}")
        except Exception as e:
            logger.error(f"Upsert failed in {collection_name}: {e}")

    def search(self, collection_name: str, query_vector: List[float], limit: int = 4, filters: Optional[Dict] = None) -> List[Any]:
        """执行向量相似度搜索。"""
        if not self.is_available: return []
        
        try:
            return self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=self._to_filter(filters),
                limit=limit
            )
        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {e}")
            return []

    # --- 数据维护 (Maintenance & Cleanup) ---

    def delete_vectors(self, collection_name: str, filters: Dict):
        """根据过滤条件物理删除向量点。"""
        if not self.is_available: return
        
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(filter=self._to_filter(filters))
            )
            logger.info(f"Deleted vectors from {collection_name} matching {filters}")
        except Exception as e:
            logger.error(f"Delete operation failed: {e}")

    def remove_user_access(self, collection_name: str, user_id: str, filters: Dict):
        """
        移除 Payload 中特定的 user_id。
        用于用户取消关注或权限变更，不触发物理删除。
        """
        if not self.is_available: return
        
        points = self.scroll(collection_name, filters, limit=1000)
        updated_count = 0

        for p in points:
            user_ids = p.payload.get('user_ids', [])
            if user_id in user_ids:
                user_ids.remove(user_id)
                self.set_payload(collection_name, {'user_ids': user_ids}, ids=[p.id])
                updated_count += 1
        
        if updated_count > 0:
            logger.info(f"Access revoked for user {user_id} across {updated_count} points")

    def set_payload(self, collection_name: str, payload: Dict, filters: Optional[Dict] = None, ids: Optional[List[str]] = None):
        """精准或条件更新点元数据。"""
        if not self.is_available: return
        
        selector = ids if ids else (models.FilterSelector(filter=self._to_filter(filters)) if filters else None)
        if selector is None: 
            return logger.warning("Payload update skipped: No point selector provided.")

        try:
            self.client.set_payload(collection_name=collection_name, payload=payload, points=selector)
        except Exception as e:
            logger.error(f"Failed to update payload: {e}")

    # --- 状态查询 ---

    def count(self, collection_name: str, filters: Optional[Dict] = None) -> int:
        """统计匹配条件的点数量。"""
        if not self.is_available: return 0
        try:
            if filters:
                return self.client.count(collection_name=collection_name, count_filter=self._to_filter(filters)).count
            return self.client.get_collection(collection_name).points_count
        except Exception:
            return 0

    def scroll(self, collection_name: str, filters: Optional[Dict] = None, limit: int = 10) -> List[Any]:
        """分页流式读取数据。"""
        if not self.is_available: return []
        try:
            points, _ = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=self._to_filter(filters),
                limit=limit
            )
            return points
        except Exception:
            return []

# 单例导出
vector_repo = VectorRepository()
