"""
聊天会话管理

1. 会话生命周期管理（自动创建、智能标题生成）
2. 消息验证和预处理
3. 历史记录格式化（适配 Agent/UI 不同需求）
4. 数据聚合和增强
"""

import uuid
import re
from datetime import datetime
from typing import List, Dict, Optional
from services.storage_service import StorageService


class ChatService:
    def __init__(self, storage_service: StorageService):
        """
        初始化聊天服务
        
        Args:
            storage_service: 存储服务实例，用于数据持久化
        """
        self.storage = storage_service

    def get_session_basic_info(self, session_id: str) -> Optional[Dict]:
        """
        查数据库是否存在该 ID
        """
        return self.storage.get_chat_session(session_id)

    def get_or_create_session(self, session_id: str = None, 
                             file_hash: str = None, 
                             title: str = None) -> Dict:
        """
        获取或创建聊天会话
        
        Args:
            session_id: 会话ID（可选，不提供则自动生成）
            file_hash: 关联的PDF文件哈希值（可选）
            title: 会话标题（可选，首条消息时自动生成）
        
        Returns:
            会话信息字典，包含前端所需的格式
        """
        # 如果没有提供 session_id，生成新的
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # 尝试获取现有会话
        session = self.storage.get_chat_session(session_id)
        
        # 如果会话不存在，创建新会话
        if not session:
            self.storage.create_chat_session(
                session_id=session_id,
                file_hash=file_hash,
                title=title or '新对话'
            )
            session = self.storage.get_chat_session(session_id)
        
        # 获取消息数量
        messages = self.storage.get_chat_messages(session_id)
        
        # 返回前端格式
        return {
            'id': session['session_id'],
            'pdfId': session.get('file_hash'),
            'title': session['title'],
            'createdAt': session['created_time'],
            'updatedAt': session['updated_time'],
            'messageCount': len(messages)
        }
    
    def list_sessions(self, file_hash: Optional[str] = None, 
                     limit: int = 50) -> List[Dict]:
        """
        获取会话列表
        
        Args:
            file_hash: 可选，筛选特定PDF的会话
            limit: 返回数量限制
        
        Returns:
            会话列表，已按更新时间倒序排列
        """
        sessions = self.storage.list_chat_sessions(limit=limit)
        
        # 筛选特定PDF的会话
        if file_hash:
            sessions = [s for s in sessions if s.get('file_hash') == file_hash]
        
        # 转换为前端格式
        result = []
        for s in sessions:
            result.append({
                'id': s['session_id'],
                'pdfId': s.get('file_hash'),
                'title': s['title'],
                'createdAt': s['created_time'],
                'updatedAt': s['updated_time'],
                'messageCount': s.get('message_count', 0)
            })
        
        return result
    
    def add_message(self, 
                    session_id: str, 
                    role: str, 
                    content: str, 
                    citations: Optional[List[dict]] = None,
                    steps: Optional[List[str]] = None,
                    metadata: Optional[dict] = None) -> dict:
        """
        添加消息到会话
        
        Args:
            session_id: 会话ID
            role: 角色 ('user' 或 'assistant')
            content: 消息内容
            citations: 引用来源（可选，对应 Agent 的 citations）
            steps: 执行步骤（可选，对应 Agent 的 steps）
            metadata: 额外元数据（可选，如 context_used）
        
        Returns:
            消息对象
        """
        # 验证会话是否存在
        session = self.storage.get_chat_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # 构建完整的 citations 数据（包含 steps 等信息）
        full_citations = citations or []
        
        # 存储到数据库
        message_id = self.storage.add_chat_message(
            session_id=session_id,
            role=role,
            content=content,
            citations=full_citations
        )
        
        # 返回消息对象（前端格式）
        message = {
            'id': message_id,
            'role': role,
            'content': content,
            'citations': citations or [],
            'steps': steps or [],
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        }
        
        return message

    def get_chat_history_for_agent(self, session_id: str, limit: int = 10) -> List[dict]:
        """
        获取符合 Agent 接口要求的对话历史格式
        格式: [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]
        """
        # 从数据库获取消息
        messages = self.storage.get_chat_messages(session_id)
        
        # 只取角色和内容，并限制轮数防止 prompt 过长
        history = [
            {'role': m['role'], 'content': m['content']} 
            for m in messages[-limit:]
        ]
        return history
    
    def get_messages(self, session_id: str) -> List[dict]:
        """获取会话的所有消息"""
        return self.storage.get_chat_messages(session_id)
    
    def update_session_title(self, session_id: str, new_title: str) -> bool:
        """
        更新会话标题
        
        Args:
            session_id: 会话ID
            new_title: 新标题
        
        Returns:
            是否更新成功
        """
        # 验证会话是否存在
        session = self.storage.get_chat_session(session_id)
        if not session:
            return False
        
        # 验证标题不能为空
        if not new_title or not new_title.strip():
            return False
        
        # 更新标题
        self.storage.update_chat_session_title(session_id, new_title.strip())
        return True
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            deleted_count = self.storage.delete_chat_session(session_id)
            return deleted_count > 0
        except Exception:
            return False
    
    def _generate_title(self, first_message: str) -> str:
        """
        根据第一条消息生成会话标题
        提取关键词作为标题
        """
        title = first_message.strip()
        if len(title) > 30:
            title = title[:30] + '...'
        
        # 移除换行符
        title = title.replace('\n', ' ')
        
        return title or '新对话'
