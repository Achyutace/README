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
    """在 Flask app 上初始化 Flask-SQLAlchemy。

    逻辑说明：如果是 SQLite 且为相对路径，解析为绝对路径并创建目录；
    否则保留原始 DATABASE_URL，并对 Postgres 添加 sslmode=require（若未指定）。
    同时在 app context 中自动创建表以便开发环境能开箱即用。
    """
    from pathlib import Path

    db_url = settings.DATABASE_URL

    # 如果是 sqlite 且为相对路径，解析为项目根下的绝对路径
    if db_url and db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
        relative_part = db_url[len("sqlite:///"):]
        if not (len(relative_part) >= 2 and relative_part[1] == ':'):
            project_root = Path(__file__).resolve().parent.parent.parent
            abs_path = project_root / relative_part
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{abs_path}"
            logger.info(f"SQLite database path resolved to: {abs_path}")

    # 对非-sqlite 的数据库，确保 sslmode 参数（常见于 Postgres in cloud）
    if db_url and not db_url.startswith("sqlite:"):
        if "sslmode" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}sslmode=require"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # 优化连接池设置，防止连接断开
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,   # 5 分钟回收连接，防止被服务器强删
        "pool_pre_ping": True, # 每次请求前检查连接是否存活
        "pool_size": 10,       # 默认连接池大小
        "max_overflow": 20,    # 允许溢出的最大连接数
    }
    db.init_app(app)

    # 自动创建所有表（开发环境方便）
    import model.db.user_models   # noqa: F401
    import model.db.doc_models    # noqa: F401
    import model.db.chat_models   # noqa: F401
    import model.db.graph_models  # noqa: F401
    with app.app_context():
        Base.metadata.create_all(bind=db.engine)
        logger.info("Database tables created/verified.")

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

