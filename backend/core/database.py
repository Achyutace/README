from __future__ import annotations
import logging
from typing import Optional

from flask_sqlalchemy import SQLAlchemy
from model.db.base import Base

# Vector DB Clients
try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None

from .config import settings

logger = logging.getLogger(__name__)

# ==========================================
# 1. PostgreSQL (Flask-SQLAlchemy)
# ==========================================
db = SQLAlchemy(model_class=Base)


def init_db(app):
    """在 Flask app 上初始化 Flask-SQLAlchemy"""
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    # 确保所有模型在建表前被导入
    import model.db.user_models
    import model.db.doc_models
    import model.db.chat_models
    import model.db.graph_models

# 生产环境改为数据库迁移
#    with app.app_context():
#        db.create_all()
#        logger.info("Database tables verified/created successfully.")

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

