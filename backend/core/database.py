from __future__ import annotations
import os
import logging
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Vector DB Clients
try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None

from .config import settings

logger = logging.getLogger(__name__)

# ==========================================
# 1. PostgreSQL (SQLAlchemy)
# ==========================================
# 从配置获取数据库连接
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 2. Vector Databases (Qdrant)
# ==========================================
class VectorDBClient:
    def __init__(self):
        self.qdrant: Optional["QdrantClient"] = None
        self._init_clients()

    def _init_clients(self):
        # Init Qdrant
        if settings.vector_store.enable_qdrant:
            if QdrantClient:
                try:
                    self.qdrant = QdrantClient(
                        url=settings.vector_store.qdrant_url,
                        api_key=settings.vector_store.qdrant_api_key or None,
                        prefer_grpc=settings.vector_store.qdrant_prefer_grpc
                    )
                    logger.info(f"Qdrant initialized at {settings.vector_store.qdrant_url}")
                except Exception as e:
                    logger.error(f"Failed to initialize Qdrant: {e}")
            else:
                logger.warning("QdrantClient library not installed but enabled in config.")

# Global Vector DB Instance
vector_db = VectorDBClient()

