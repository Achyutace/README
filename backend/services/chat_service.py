"""
聊天会话管理服务
负责处理业务逻辑，调用 SQLRepository 进行数据持久化，并进行数据格式化。
"""

import uuid
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any
from ..repository.sql_repo import SQLRepository 

class ChatService:
    def __init__(self, db_repo: SQLRepository):
        """
        初始化聊天服务
        :param db_repo: 数据库仓库实例
        """
        self.repo = db_repo

    # ==================== 业务逻辑 ====================

    def add_user_message(self, session_id: str, user_id: str, content: str) -> Dict:
        """添加用户消息"""
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        msg = self.repo.add_chat_message(
            session_id=uuid.UUID(session_id),
            user_id=u_uuid,
            role="user",
            content=content
        )
        return self._model_to_dict(msg)

    def add_ai_message(self, session_id: str, user_id: str, content: str, citations: List[Dict] = None) -> Dict:
        """添加 AI 回复"""
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        msg = self.repo.add_chat_message(
            session_id=uuid.UUID(session_id),
            user_id=u_uuid,
            role="assistant",
            content=content,
            citations=citations
        )
        return self._model_to_dict(msg)

    def get_formatted_history(self, session_id: str, user_id: str, limit: int = 10) -> List[Dict]:
        """
        获取格式化后的历史记录
        """
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        raw_msgs = self.repo.get_chat_history(uuid.UUID(session_id), u_uuid)
        # 取最后 N 条
        selected_msgs = raw_msgs[-limit:] if limit else raw_msgs
        
        return [
            {'role': m.role, 'content': m.content}
            for m in selected_msgs
        ]

    def get_session_messages_for_ui(self, session_id: str, user_id: str) -> List[Dict]:
        """获取用于前端展示的所有消息"""
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        raw_msgs = self.repo.get_chat_history(uuid.UUID(session_id), u_uuid)
        return self.format_messages(raw_msgs)

    def list_user_sessions(self, user_id: str, file_hash: str = None, limit: int = 50) -> List[Dict]:
        """列出用户会话"""
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        sessions = self.repo.list_chat_sessions(u_uuid, file_hash=file_hash, limit=limit)
        return self.format_session_list(sessions)

    def create_session(self, user_id: str, file_hash: str = None, title: str = "New Chat") -> Dict:
        """创建新会话"""
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        session_id = uuid.uuid4()
        
        session = self.repo.create_chat_session(
            session_id=session_id,
            user_id=u_uuid,
            file_hash=file_hash,
            title=title
        )
        
        return {
            'id': str(session.id),
            'pdfId': getattr(session, 'file_hash', file_hash),
            'title': session.title,
            'createdAt': session.created_at.isoformat() if session.created_at else None,
            'updatedAt': session.updated_at.isoformat() if getattr(session, 'updated_at', None) else None,
        }

    def get_session(self, session_id: str, user_id: str) -> Optional[Dict]:
        """获取单个会话详情"""
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        session = self.repo.get_chat_session(uuid.UUID(session_id), u_uuid)
        
        if not session:
            return None
            
        return {
            'id': str(session.id),
            'pdfId': session.file_hash,
            'title': session.title,
            'createdAt': session.created_at.isoformat() if session.created_at else None,
            'updatedAt': session.updated_at.isoformat() if getattr(session, 'updated_at', None) else None,
        }

    def delete_session(self, session_id: str, user_id: str) -> int:
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        return self.repo.delete_chat_session(uuid.UUID(session_id), u_uuid)

    def update_title(self, session_id: str, user_id: str, title: str) -> bool:
        u_uuid = uuid.UUID(user_id) if user_id != 'default' else uuid.UUID('00000000-0000-0000-0000-000000000000')
        return self.repo.update_chat_session_title(uuid.UUID(session_id), u_uuid, title)

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
            result.append({
                'id': str(s.id),
                'pdfId': s.file_hash,
                'title': s.title,
                'createdAt': s.created_at.isoformat() if s.created_at else None,
                'updatedAt': s.updated_at.isoformat() if s.updated_at else None,
                # 如果需要 messageCount，可能需要在 Repo层做 count 查询，这里暂时略过或设为默认
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
