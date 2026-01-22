"""
聊天会话管理 (纯逻辑层)
解耦后：不再直接操作数据库，只负责数据格式化、校验和转换。
"""

from datetime import datetime
from typing import List, Dict, Optional


class ChatService:
    def __init__(self):
        """
        初始化聊天服务
        """
        pass

    def format_session_info(self, session: Dict, message_count: int) -> Dict:
        """
        将数据库的会话对象转换为前端格式
        """
        return {
            'id': session['session_id'],
            'pdfId': session.get('file_hash'),
            'title': session['title'],
            'createdAt': session['created_time'],
            'updatedAt': session['updated_time'],
            'messageCount': message_count
        }

    def format_session_list(self, sessions: List[Dict]) -> List[Dict]:
        """
        格式化会话列表
        """
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

    def format_message(self,
                       message_id: int,
                       role: str,
                       content: str,
                       citations: Optional[List[dict]] = None,
                       steps: Optional[List[str]] = None,
                       metadata: Optional[dict] = None) -> dict:
        """
        构建返回给前端的消息对象
        """
        return {
            'id': message_id,
            'role': role,
            'content': content,
            'citations': citations or [],
            'steps': steps or [],
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat()
        }

    def format_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        格式化消息列表（从数据库格式转为前端格式）
        """
        result = []
        for m in messages:
            result.append({
                'id': m['id'],
                'role': m['role'],
                'content': m['content'],
                'citations': m.get('citations', []),
                'created_time': m['created_time']
            })
        return result

    def process_history_for_agent(self, messages: List[dict], limit: int = 10) -> List[dict]:
        """
        处理符合 Agent 接口要求的对话历史格式
        Args:
            messages: 数据库原始消息列表
            limit: 限制条数
        """
        # 只取角色和内容，并限制轮数防止 prompt 过长
        history = [
            {'role': m['role'], 'content': m['content']}
            for m in messages[-limit:]
        ]
        return history

    def generate_default_title(self, first_message: str) -> str:
        """
        根据第一条消息生成默认标题（纯逻辑）
        """
        title = first_message.strip()
        if len(title) > 30:
            title = title[:30] + '...'
        title = title.replace('\n', ' ')
        return title or '新对话'
