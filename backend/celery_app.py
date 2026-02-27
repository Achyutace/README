"""
Celery 应用实例
使用方式:
    启动 Worker: celery -A celery_app.celery worker --loglevel=info --pool=solo
"""
from celery import Celery
from flask import Flask
from core.config import settings

celery = Celery(
    "readme_worker",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

# Celery 配置
celery.conf.update(
    # 序列化
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # 任务追踪：允许 worker 发送 task-started 事件
    task_track_started=True,
    
    # 结果过期时间 (24小时)
    result_expires=86400,
    
    # Worker 预取数量 (1 = 公平调度，适合长任务)
    worker_prefetch_multiplier=1,
    
    # 任务确认：任务完成后才 ack (防止任务丢失)
    task_acks_late=True,
    
    # 自动发现任务模块
    include=["tasks.pdf_tasks", "tasks.chat_tasks"],
)


def create_worker_app() -> Flask:
    """
    为 Celery Worker 创建轻量级 Flask 应用。
    只初始化数据库连接，不加载路由和重量级服务，
    避免 Worker 必须 import app.py 才能获取 Flask context。
    """
    from datetime import timedelta
    from flask_jwt_extended import JWTManager
    from core.database import db, init_db

    worker_app = Flask(__name__)
    worker_app.config['JWT_SECRET_KEY'] = settings.jwt.secret
    worker_app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=settings.jwt.access_expire_minutes)
    worker_app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=settings.jwt.refresh_expire_days)
    JWTManager(worker_app)
    init_db(worker_app)
    return worker_app


# 延迟单例：首次调用时创建，后续复用
_worker_app: Flask | None = None


def get_worker_app() -> Flask:
    """获取（或懒加载创建）Worker 专用 Flask 实例。"""
    global _worker_app
    if _worker_app is None:
        _worker_app = create_worker_app()
    return _worker_app
