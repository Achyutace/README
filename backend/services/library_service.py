"""
文献管理服务：维护 User 与 Paper 的关系
1. 根据user_id获取用户文献+分组
2. 根据user_id获取用户笔记
3. 删除用户文献库中文献
"""
import logging
import uuid
from typing import List, Dict, Any
from sqlalchemy import select, desc, and_

from core.database import SessionLocal
from repository.sql_repo import SQLRepository
from model.db.doc_models import UserPaper

logger = logging.getLogger(__name__)

class LibraryService:
    
    def _get_repo(self):
        """辅助方法：获取 DB session 和 Repository 实例"""
        db = SessionLocal()
        return db, SQLRepository(db)

    def bind_paper(self, user_id: uuid.UUID, pdf_id: str, title: str) -> bool:
        """
        将GlobalFile中注册好的PDF绑定到用户库中。
        """
        db, repo = self._get_repo()
        try:
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)

            # 1. 检查是否已存在 (幂等性)
            existing = repo.get_user_paper(user_id, pdf_id)
            if existing:
                logger.info(f"Paper {pdf_id} already in user {user_id} library.")
                return True

            # 2. 创建关联
            repo.create_user_paper(
                user_id=user_id,
                file_hash=pdf_id,
                title=title
            )
            db.commit()
            logger.info(f"Bound PDF {pdf_id} to User {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error binding PDF {pdf_id} to user {user_id}: {e}")
            return False
        finally:
            db.close()

    def delete_pdf(self, pdf_id: str, user_id) -> bool:
        """删除 PDF (仅解除用户关联，不删除物理文件)"""
        db, repo = self._get_repo()
        try:
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
            success = repo.delete_user_paper(user_id, pdf_id)
            return success
        except Exception as e:
            logger.error(f"Error deleting PDF {pdf_id} for user {user_id}: {e}")
            return False
        finally:
            db.close()

    def set_paper_group(self, pdf_id: str, user_id, group_name: str) -> bool:
        """设置论文分组 (Tags)"""
        db, repo = self._get_repo()
        try:
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
            
            user_paper = repo.get_user_paper(user_id, pdf_id)
            if not user_paper:
                return False
            
            current_tags = list(user_paper.tags) if user_paper.tags else []
            if group_name and group_name not in current_tags:
                current_tags.append(group_name)
                user_paper.tags = current_tags
                db.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting group for PDF {pdf_id}: {e}")
            return False
        finally:
            db.close()

    def remove_paper_group(self, pdf_id: str, user_id, group_name: str) -> bool:
        """移除论文分组 (Tags)"""
        db, repo = self._get_repo()
        try:
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
            
            user_paper = repo.get_user_paper(user_id, pdf_id)
            if not user_paper or not user_paper.tags:
                return False
            
            current_tags = list(user_paper.tags)
            if group_name in current_tags:
                current_tags.remove(group_name)
                user_paper.tags = current_tags
                db.commit()
            return True
        except Exception as e:
            logger.error(f"Error removing group for PDF {pdf_id}: {e}")
            return False
        finally:
            db.close()

    def get_user_papers(self, user_id, page: int = 1, page_size: int = 20, 
                        group_filter: str = None, 
                        keyword: str = None) -> Dict[str, Any]:
        """获取论文列表（含分页、分组筛选、搜索）"""
        db, repo = self._get_repo()
        try:
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
            
            stmt = select(UserPaper).where(
                and_(UserPaper.user_id == user_id, UserPaper.is_deleted == False)
            )
            
            if group_filter:
                stmt = stmt.where(UserPaper.tags.contains([group_filter]))
            
            if keyword:
                stmt = stmt.where(UserPaper.title.ilike(f"%{keyword}%"))
            
            stmt = stmt.order_by(desc(UserPaper.added_at))
            
            offset = (page - 1) * page_size
            items = db.execute(stmt.offset(offset).limit(page_size)).scalars().all()
            
            data = []
            for p in items:
                gf = p.global_file
                data.append({
                    "pdfId": p.file_hash,
                    "title": p.title,
                    "tags": p.tags or [],
                    "addedAt": p.added_at.isoformat() if p.added_at else None,
                    "fileSize": gf.file_size if gf else 0,
                    "totalPages": gf.total_pages if gf else 0,
                    "processStatus": gf.process_status if gf else "unknown",
                    "readStatus": p.read_status
                })
                
            return {
                "items": data,
                "page": page,
                "pageSize": page_size
            }
        except Exception as e:
            logger.error(f"Error getting papers for user {user_id}: {e}")
            return {"items": [], "page": page, "pageSize": page_size}
        finally:
            db.close()

    def get_paper_notes(self, user_id, pdf_id: str) -> List[Dict]:
        """获取论文的所有笔记"""
        db, repo = self._get_repo()
        try:
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
                
            user_paper = repo.get_user_paper(user_id, pdf_id)
            if not user_paper:
                return []
                
            notes = repo.get_notes(user_paper.id)
            return [{
                "id": n.id,
                "content": n.content,
                "keywords": n.keywords or [],
                "createdAt": n.created_at.isoformat() if n.created_at else None,
                "updatedAt": n.updated_at.isoformat() if n.updated_at else None
            } for n in notes]
        except Exception as e:
            logger.error(f"Error getting notes for {pdf_id}: {e}")
            return []
        finally:
            db.close()