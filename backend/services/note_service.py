"""
笔记服务层：处理笔记的增删改查业务逻辑
"""
import uuid
import json
import logging
from typing import List, Dict, Optional, Any
from ..repository.sql_repo import SQLRepository
from ..model.db.doc_models import UserNote

logger = logging.getLogger(__name__)

class NoteService:
    def __init__(self, db_repo: SQLRepository):
        self.repo = db_repo

    def add_note(self, user_id: str, file_hash: str, content: str, 
                 keywords: List[str] = None, meta_data: Dict = None) -> int:
        """
        添加笔记
        :param user_id: 用户ID (str)
        :param file_hash: 全局文件Hash
        :param content: 笔记内容 (Markdown 或 JSON字符串)
        :param keywords: 关键词
        :param meta_data: 额外元数据 (如 color, position, type)
        :return: 笔记的唯一 ID (int)
        """
        # 1. 处理 User ID
        try:
            if user_id == 'default':
                u_uuid = uuid.UUID('00000000-0000-0000-0000-000000000000')
            else:
                u_uuid = uuid.UUID(user_id)
        except ValueError:
            logger.error(f"Invalid user_id format: {user_id}")
            raise ValueError("Invalid user_id format")

        # 2. 确保 UserPaper 存在
        # 笔记必须关联到一个 UserPaper (用户书架上的书)
        user_paper = self.repo.get_user_paper(u_uuid, file_hash)
        if not user_paper:
            logger.info(f"UserPaper not found for user {user_id} and file {file_hash}, creating new.")
            # 如果没有标题，可以用默认值
            user_paper = self.repo.create_user_paper(u_uuid, file_hash, title="Reference Document")

        # 3. 保存到数据库
        note = self.repo.add_note(
            user_paper_id=user_paper.id,
            content=content,
            keywords=keywords or []
        )
        
        logger.info(f"Note created with ID: {note.id}")
        return note.id

    def delete_note(self, note_id: int) -> bool:
        """
        删除笔记
        :param note_id: 笔记ID
        :return: 是否成功
        """
        try:
            self.repo.delete_note(note_id)
            logger.info(f"Note deleted: {note_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting note {note_id}: {e}")
            return False

    def update_note_content(self, note_id: int, content: Optional[str] = None,  keywords: Optional[List[str]] = None) -> bool:
        """
        修改笔记
        :param note_id: 笔记ID
        :param content: 新内容
        :param keywords: 新关键词
        :return: 是否成功
        """

        self.repo.update_note(note_id, content=content, keywords=keywords)
        return True

    def get_notes(self, user_id: str, file_hash: str) -> List[Dict]:
        """
        获取用户针对某文件的所有笔记
        :return: 笔记字典列表
        """
        try:
            if user_id == 'default':
                u_uuid = uuid.UUID('00000000-0000-0000-0000-000000000000')
            else:
                u_uuid = uuid.UUID(user_id)
        except ValueError:
            return []

        user_paper = self.repo.get_user_paper(u_uuid, file_hash)
        if not user_paper:
            return []

        notes = self.repo.get_notes(user_paper.id)
        
        result = []
        for n in notes:
            # 尝试解析 JSON content 以便前端更好使用
            content_val = n.content
            is_json = False
            try:
                parsed = json.loads(n.content)
                if isinstance(parsed, dict) or isinstance(parsed, list):
                    content_val = parsed
                    is_json = True
            except:
                pass
            
            result.append({
                "id": n.id,
                "content": content_val,
                "keywords": n.keywords,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
                "is_json": is_json
            })
            
        return result

    def get_note_by_id(self, note_id: int) -> Optional[Dict]:
        """
        根据ID获取单条笔记详情
        :param note_id: 笔记ID
        :return: 笔记详情或 None
        """
        note = self.repo.get_note_by_id(note_id)
        if not note:
            return None
            
        content_val = note.content
        is_json = False
        try:
            parsed = json.loads(note.content)
            if isinstance(parsed, (dict, list)):
                content_val = parsed
                is_json = True
        except:
            pass
            
        return {
            "id": note.id,
            "user_paper_id": str(note.user_paper_id),
            "content": content_val,
            "keywords": note.keywords,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            "is_json": is_json
        }
