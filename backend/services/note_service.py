"""
笔记 & 高亮 服务层：处理笔记和高亮的增删改查业务逻辑
"""
import uuid
import json
import logging
from typing import List, Dict, Optional, Any
from repository.sql_repo import SQLRepository
from model.db.doc_models import UserNote, UserHighlight

from core.database import db
logger = logging.getLogger(__name__)

class NoteService:
    def __init__(self, db_repo: SQLRepository):
        self.repo = db_repo

    def add_note(self, user_id: uuid.UUID, file_hash: str, content: str, title: str = None, 
                 keywords: List[str] = None, meta_data: Dict = None) -> int:
        """
        添加笔记
        :param user_id: 用户ID (UUID)
        :param file_hash: 全局文件Hash
        :param content: 笔记内容
        :param title: 笔记标题
        :param keywords: 关键词
        :param meta_data: 额外元数据
        :return: 笔记的唯一 ID
        """
        # 1. User ID
        u_uuid = user_id

        # 2. 确保 UserPaper 存在
        # 笔记必须关联到一个 UserPaper (用户书架上的书)
        user_paper = self.repo.get_user_paper(u_uuid, file_hash)
        if not user_paper:
            logger.info(f"UserPaper not found for user {user_id} and file {file_hash}, creating new.")
            # 如果没有标题，可以用默认值
            user_paper = self.repo.create_user_paper(u_uuid, file_hash, title="Reference Document")

        # 3. 保存到数据库
        try:
            note = self.repo.add_note(
                user_paper_id=user_paper.id,
                content=content,
                title=title,
                keywords=keywords or []
            )
            db.session.commit()
            logger.info(f"Note created with ID: {note.id}")
            return note.id
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating note: {e}")
            raise

    def delete_note(self, note_id: int) -> bool:
        """
        删除笔记
        :param note_id: 笔记ID
        :return: 是否成功
        """
        try:
            self.repo.delete_note(note_id)
            db.session.commit()
            logger.info(f"Note deleted: {note_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting note {note_id}: {e}")
            return False

    def update_note_content(self, note_id: int, title: Optional[str] = None, content: Optional[str] = None,  keywords: Optional[List[str]] = None) -> bool:
        """
        修改笔记
        :param note_id: 笔记ID
        :param title: 新标题
        :param content: 新内容
        :param keywords: 新关键词
        :return: 是否成功
        """

        try:
            self.repo.update_note(note_id, title=title, content=content, keywords=keywords)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating note {note_id}: {e}")
            return False

    def get_notes(self, user_id: uuid.UUID, file_hash: str) -> List[Dict]:
        """
        获取用户针对某文件的所有笔记
        :return: 笔记字典列表
        """
        u_uuid = user_id
        
        user_paper = self.repo.get_user_paper(u_uuid, file_hash)
        if not user_paper:
            return []

        notes = self.repo.get_notes(user_paper.id)
        
        result = []
        for n in notes:
            result.append({
                "id": n.id,
                "title": n.title,
                "content": n.content,
                "keywords": n.keywords,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
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
            
        return {
            "id": note.id,
            "user_paper_id": str(note.user_paper_id),
            "title": note.title,
            "content": note.content,
            "keywords": note.keywords,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        }
    # ==================== 高亮 ====================

    def _resolve_user_paper_id(self, user_id: uuid.UUID, file_hash: str):
        """内部辅助：解析 user_id (UUID)，查找 UserPaper 关联 ID"""
        u_uuid = user_id
        
        user_paper = self.repo.get_user_paper(u_uuid, file_hash)
        if not user_paper:
            return None
        return user_paper.id

    def add_highlight(self, user_id: uuid.UUID, file_hash: str,
                      page_number: int, rects: List[Dict],
                      selected_text: str = '', color: str = '#FFFF00') -> Optional[int]:
        """
        添加高亮
        :param user_id:   用户 ID (UUID)
        :param file_hash: PDF 文件哈希
        :param page_number: 页码
        :param rects:     归一化坐标列表
        :param selected_text: 选中文本
        :param color:     高亮颜色
        :return: 高亮记录 ID
        """
        user_paper_id = self._resolve_user_paper_id(user_id, file_hash)
        if not user_paper_id:
            logger.warning(f"UserPaper not found: user={user_id}, file={file_hash}")
            return None

        try:
            highlight = self.repo.add_highlight(
                user_paper_id=user_paper_id,
                page_number=page_number,
                rects=rects,
                selected_text=selected_text,
                color=color
            )
            db.session.commit()
            logger.info(f"Highlight created: id={highlight.id}")
            return highlight.id
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding highlight: {e}")
            return None

    def get_highlights(self, user_id: uuid.UUID, file_hash: str,
                       page_number: Optional[int] = None) -> List[Dict]:
        """
        获取高亮列表
        :return: 高亮字典列表
        """
        user_paper_id = self._resolve_user_paper_id(user_id, file_hash)
        if not user_paper_id:
            return []

        highlights = self.repo.get_highlights(user_paper_id, page_number=page_number)

        return [
            {
                "id": h.id,
                "page": h.page_number,
                "rects": h.rects,
                "text": h.selected_text,
                "color": h.color,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in highlights
        ]

    def delete_highlight(self, highlight_id: int) -> bool:
        """删除高亮"""
        try:
            self.repo.delete_highlight(highlight_id)
            db.session.commit()
            logger.info(f"Highlight deleted: {highlight_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting highlight {highlight_id}: {e}")
            return False

    def update_highlight(self, highlight_id: int, color: Optional[str] = None) -> bool:
        """更新高亮颜色"""
        try:
            self.repo.update_highlight(highlight_id, color=color)
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating highlight {highlight_id}: {e}")
            return False
