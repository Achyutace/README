"""
聊天会话管理服务

功能：
1. 创建和管理聊天会话
2. 存储聊天消息历史
3. 生成会话标题（基于关键词）

TODO 目前的对话历史管理完全依赖前端，这部分需要等对话历史存数据库写好之后再启用
"""

import uuid
from datetime import datetime
from typing import List, Dict, Optional


class ChatService:
    def __init__(self):
        # 内存存储（演示用，生产环境应使用数据库）
        self.sessions: Dict[str, dict] = {}
        self.messages: Dict[str, List[dict]] = {}
    
    def create_session(self, pdf_id: str, title: Optional[str] = None) -> dict:
        """
        创建新的聊天会话
        
        Args:
            pdf_id: 关联的PDF文档ID
            title: 会话标题（可选，如果不提供则自动生成）
        
        Returns:
            会话信息字典
        """
        session_id = str(uuid.uuid4())
        session = {
            'id': session_id,
            'pdfId': pdf_id,
            'title': title or '新对话',
            'createdAt': datetime.now().isoformat(),
            'updatedAt': datetime.now().isoformat(),
            'messageCount': 0
        }
        
        self.sessions[session_id] = session
        self.messages[session_id] = []
        
        return session
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话信息"""
        return self.sessions.get(session_id)
    
    def list_sessions(self, pdf_id: Optional[str] = None) -> List[dict]:
        """
        获取会话列表
        
        Args:
            pdf_id: 可选，筛选特定PDF的会话
        
        Returns:
            会话列表，按更新时间倒序排列
        """
        sessions = list(self.sessions.values())
        
        # 筛选特定PDF的会话
        if pdf_id:
            sessions = [s for s in sessions if s['pdfId'] == pdf_id]
        
        # 按更新时间倒序排列
        sessions.sort(key=lambda x: x['updatedAt'], reverse=True)
        
        return sessions
    
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
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        
        message = {
            'id': str(uuid.uuid4()),
            'role': role,
            'content': content,
            'citations': citations or [],
            'steps': steps or [],
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        }
        
        self.messages[session_id].append(message)
        
        # 更新会话信息
        session = self.sessions[session_id]
        session['updatedAt'] = datetime.now().isoformat()
        session['messageCount'] = len(self.messages[session_id])
        
        # 如果是第一条用户消息，自动生成标题
        if role == 'user' and session['messageCount'] == 1:
            session['title'] = self._generate_title(content)
        
        return message

    def get_chat_history_for_agent(self, session_id: str, limit: int = 10) -> List[dict]:
        """
        获取符合 Agent 接口要求的对话历史格式
        格式: [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]
        """
        messages = self.messages.get(session_id, [])
        # 只取角色和内容，并限制轮数防止 prompt 过长
        history = [
            {'role': m['role'], 'content': m['content']} 
            for m in messages[-limit:]
        ]
        return history
    
    def get_messages(self, session_id: str) -> List[dict]:
        """获取会话的所有消息"""
        return self.messages.get(session_id, [])
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            if session_id in self.messages:
                del self.messages[session_id]
            return True
        return False
    
    def _generate_title(self, first_message: str) -> str:
        """
        根据第一条消息生成会话标题
        提取关键词作为标题
        """
        # 简单实现：取前30个字符
        # 生产环境可以使用NLP提取关键词
        title = first_message.strip()
        if len(title) > 30:
            title = title[:30] + '...'
        
        # 移除换行符
        title = title.replace('\n', ' ')
        
        return title or '新对话'
