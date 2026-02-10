"""
Celery 应用实例
使用方式:
    启动 Worker: celery -A celery_app.celery worker --loglevel=info --pool=solo
"""
from celery import Celery
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
    include=["tasks.pdf_tasks"],
)
