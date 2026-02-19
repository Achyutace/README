"""
聊天相关 Celery 异步任务
- generate_session_title_task: 异步生成会话标题

注意:
    1. 不传递 Service 对象，只传可序列化的 ID / 字符串
    2. 在任务内部重新建立 DB 连接 + 实例化 Service，保证线程安全
    3. 标题生成仅需要 LLM，无需实例化整个 AcademicAgentService
"""
# TODO：添加轻量化llm组件
import logging
import uuid
from celery import shared_task

from core.database import db
from core.config import settings
from core.llm_provider import resolve_llm_profile
from repository.sql_repo import SQLRepository
from services.chat_service import ChatService

logger = logging.getLogger(__name__)


# ==================== 内部工具 ====================

def _generate_title_via_llm(user_query: str) -> str:
    """
    轻量级标题生成 —— 镜像 AcademicAgentService.generate_session_title 的核心逻辑,
    但不依赖 rag_service / storage_service，仅需 LLM。
    """
    # 1. 解析配置
    profile = resolve_llm_profile(scene="chat")
    
    if not profile.is_available:
        # Demo 模式：直接截断
        return (user_query[:20] + "...") if len(user_query) > 20 else user_query

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        llm_kwargs = {
            "model": profile.model,
            "temperature": 0.7,
            "api_key": profile.api_key
        }
        if profile.api_base:
            llm_kwargs["base_url"] = profile.api_base
            
        llm = ChatOpenAI(**llm_kwargs)

        prompt = (
            "请为下面的用户提问生成一个极简短的会话标题（不超过15个字）。\n"
            '不要使用"关于"、"询问"等废话，直接提取核心主题。\n'
            "不要使用引号。\n\n"
            f"用户提问：{user_query}\n"
            "标题："
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        title = response.content.strip()
        title = title.replace('"', '').replace('《', '').replace('》', '')
        return title

    except Exception as e:
        logger.error(f"LLM title generation failed: {e}")
        return user_query[:20]


# ==================== Celery Task ====================

@shared_task(ignore_result=True, name="tasks.chat_tasks.generate_session_title")
def generate_session_title_task(session_id: uuid.UUID, user_id: uuid.UUID, user_query: str):
    """
    异步生成会话标题并更新数据库。

    Args:
        session_id: 会话 UUID
        user_id:    用户 ID (UUID)
        user_query: 用户的第一句提问
    """
    from app import app
    with app.app_context():
        try:
            repo = SQLRepository(db.session)
            chat_service = ChatService(db_repo=repo)
            new_title = _generate_title_via_llm(user_query) or user_query[:20]
            chat_service.update_title(session_id, user_id, new_title)
            logger.info(f"Title updated for session {session_id}: {new_title}")
        except Exception as e:
            logger.error(f"Failed to generate title for session {session_id}: {e}")
            db.session.rollback()
