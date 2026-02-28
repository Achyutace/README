"""
聊天会话管理服务
负责处理业务逻辑，调用 SQLRepository 进行数据持久化，并进行数据格式化。
"""

import uuid
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any
from repository.sql_repo import SQLRepository 

class ChatService:
    def __init__(self, db_repo: SQLRepository):
        """
        初始化聊天服务
        :param db_repo: 数据库仓库实例
        """
        self.repo = db_repo

    # ==================== 业务逻辑 ====================

    def add_user_message(self, session_id: str, user_id: uuid.UUID, content: str) -> Dict:
        """添加用户消息"""
        s_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        msg = self.repo.add_chat_message(
            session_id=s_uuid,
            user_id=user_id,
            role="user",
            content=content
        )
        return self._model_to_dict(msg)

    def add_ai_message(self, session_id: str, user_id: uuid.UUID, content: str, citations: List[Dict] = None) -> Dict:
        """添加 AI 回复"""
        s_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        msg = self.repo.add_chat_message(
            session_id=s_uuid,
            user_id=user_id,
            role="assistant",
            content=content,
            citations=citations
        )
        return self._model_to_dict(msg)

    def get_formatted_history(self, session_id: str, user_id: uuid.UUID, limit: int = 10) -> List[Dict]:
        """
        获取格式化后的历史记录
        """
        s_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        raw_msgs = self.repo.get_chat_history(s_uuid, user_id)
        # 取最后 N 条
        selected_msgs = raw_msgs[-limit:] if limit else raw_msgs
        
        return [
            {'role': m.role, 'content': m.content}
            for m in selected_msgs
        ]

    def get_session_messages_for_ui(self, session_id: str, user_id: uuid.UUID) -> List[Dict]:
        """获取用于前端展示的所有消息"""
        s_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        raw_msgs = self.repo.get_chat_history(s_uuid, user_id)
        return self.format_messages(raw_msgs)

    def list_user_sessions(self, user_id: uuid.UUID, file_hash: str = None, limit: int = 50) -> List[Dict]:
        """列出用户会话"""
        sessions = self.repo.list_chat_sessions(user_id, file_hash=file_hash, limit=limit)
        return self.format_session_list(sessions)

    def create_session(self, user_id: uuid.UUID, file_hash: str = None, title: str = "New Chat") -> Dict:
        """创建新会话"""
        session_id = uuid.uuid4()
        
        session = self.repo.create_chat_session(
            session_id=session_id,
            user_id=user_id,
            file_hash=file_hash,
            title=title
        )
        
        pdf_id = file_hash
        if session.user_paper:
            pdf_id = session.user_paper.file_hash

        return {
            'id': str(session.id),
            'pdfId': pdf_id,
            'title': session.title,
            'createdAt': session.created_at.isoformat() if session.created_at else None,
            'updatedAt': session.updated_at.isoformat() if getattr(session, 'updated_at', None) else None,
        }

    def get_session(self, session_id, user_id) -> Optional[Dict]:
        """获取单个会话详情"""
        s_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        u_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        session = self.repo.get_chat_session(s_uuid, u_uuid)
        
        if not session:
            return None

        # 通过 user_paper 关联获取 file_hash
        pdf_id = None
        if session.user_paper:
            pdf_id = session.user_paper.file_hash

        return {
            'id': str(session.id),
            'pdfId': pdf_id,
            'title': session.title,
            'createdAt': session.created_at.isoformat() if session.created_at else None,
            'updatedAt': session.updated_at.isoformat() if getattr(session, 'updated_at', None) else None,
        }

    def delete_session(self, session_id: str, user_id: uuid.UUID) -> int:
        s_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        return self.repo.delete_chat_session(s_uuid, user_id)

    def update_title(self, session_id: str, user_id: uuid.UUID, title: str) -> bool:
        s_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        return self.repo.update_chat_session_title(s_uuid, user_id, title)

    # ==================== 格式化工具 ====================

    def _model_to_dict(self, model_obj) -> Dict:
        """简单的模型转字典辅助"""
        return {
            'id': model_obj.id,
            'role': getattr(model_obj, 'role', None),
            'content': getattr(model_obj, 'content', None),
            'citations': getattr(model_obj, 'citations', []),
            'created_at': model_obj.created_at.isoformat() if hasattr(model_obj, 'created_at') else None
        }

    def format_session_list(self, sessions: List[Any]) -> List[Dict]:
        """格式化会话列表"""
        result = []
        for s in sessions:
            pdf_id = None
            if s.user_paper:
                pdf_id = s.user_paper.file_hash
            result.append({
                'id': str(s.id),
                'pdfId': pdf_id,
                'title': s.title,
                'createdAt': s.created_at.isoformat() if s.created_at else None,
                'updatedAt': s.updated_at.isoformat() if s.updated_at else None,
            })
        return result

    def format_messages(self, messages: List[Any]) -> List[Dict]:
        """格式化消息列表（从数据库模型转为前端格式）"""
        result = []
        for m in messages:
            result.append({
                'id': m.id,
                'role': m.role,
                'content': m.content,
                'citations': m.citations or [],
                'timestamp': m.created_at.isoformat() if m.created_at else None
            })
        return result
