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
    # 处理云数据库常见的连接断开问题
    database_url = settings.DATABASE_URL
    if "sslmode" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # 优化连接池设置，防止连接断开
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,   # 5 分钟回收连接，防止被服务器强删
        "pool_pre_ping": True, # 每次请求前检查连接是否存活
        "pool_size": 10,       # 默认连接池大小
        "max_overflow": 20,    # 允许溢出的最大连接数
    }
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

