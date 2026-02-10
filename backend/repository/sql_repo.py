from typing import List, Dict, Optional, Any, Union
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, update, func, and_, desc, asc
from sqlalchemy.dialects.postgresql import insert

# Using relative imports suitable for the package structure
from ..model.db.base import Base
from ..model.db.doc_models import (
    GlobalFile, PdfParagraph, PdfImage, UserPaper, 
    UserNote, UserHighlight
)
from ..model.db.chat_models import ChatSession, ChatMessage, ChatAttachment
from ..model.db.user_models import User
from ..model.db.graph_models import (
    UserGraphProject, GraphNode, GraphEdge,
    graph_paper_association, paper_node_link, note_node_link
)

class SQLRepository:
    def __init__(self, db: Session):
        self.db = db

    # ==================== 用户管理 ====================
    
    def get_user_by_name(self, username: str) -> Optional[User]:
        """根据用户名获取用户信息"""
        stmt = select(User).where(User.username == username)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """根据用户 ID 获取用户信息"""
        stmt = select(User).where(User.id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_user(self, username: str, email: str, password_hash: str) -> User:
        """创建新用户"""
        user = User(username=username, email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ==================== PDF 管理 ====================

    def get_global_file(self, file_hash: str) -> Optional[GlobalFile]:
        """根据文件哈希值获取全局文件记录"""
        stmt = select(GlobalFile).where(GlobalFile.file_hash == file_hash)
        return self.db.execute(stmt).scalar_one_or_none()
        
    def create_global_file(self, file_hash: str, file_path: str, file_size: int = 0, total_pages: int = 0, metadata: Dict = None) -> GlobalFile:
        """创建全局文件记录（如果已存在则返回现有记录）"""
        existing = self.get_global_file(file_hash)
        if existing:
            return existing
            
        global_file = GlobalFile(
            file_hash=file_hash,
            file_path=file_path,
            file_size=file_size,
            total_pages=total_pages,
            metadata_info=metadata or {},
            process_status="pending" 
        )
        self.db.add(global_file)
        self.db.commit()
        self.db.refresh(global_file)
        return global_file

    def get_user_paper(self, user_id: uuid.UUID, file_hash: str) -> Optional[UserPaper]:
        """获取用户的论文关联记录"""
        stmt = select(UserPaper).where(
            and_(UserPaper.user_id == user_id, UserPaper.file_hash == file_hash)
        )
        return self.db.execute(stmt).scalar_one_or_none() # 出现多条记录则抛异常

    def create_user_paper(self, user_id: uuid.UUID, file_hash: str, title: str) -> UserPaper:
        """创建用户与论文的关联记录"""
        existing = self.get_user_paper(user_id, file_hash)
        if existing:
            return existing
            
        user_paper = UserPaper(
            user_id=user_id,
            file_hash=file_hash,
            title=title,
            read_status="unread"
        )
        self.db.add(user_paper)
        self.db.commit()
        self.db.refresh(user_paper)
        return user_paper
        
    def list_user_papers(self, user_id: uuid.UUID, limit: int = 100, include_deleted: bool = False) -> List[UserPaper]:
        """列出用户的所有论文"""
        stmt = select(UserPaper).where(UserPaper.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(UserPaper.is_deleted == False)
        stmt = stmt.order_by(desc(UserPaper.added_at)).limit(limit)
        return self.db.execute(stmt).scalars().all()

    def delete_user_paper(self, user_id: uuid.UUID, file_hash: str, hard_delete: bool = False) -> bool:
        """删除用户的论文（默认为软删除）"""
        stmt = select(UserPaper).where(
            and_(UserPaper.user_id == user_id, UserPaper.file_hash == file_hash)
        )
        user_paper = self.db.execute(stmt).scalar_one_or_none()
        
        if not user_paper:
            return False
            
        if hard_delete:
            self.db.delete(user_paper)
        else:
            user_paper.is_deleted = True
            user_paper.deleted_at = func.now()
            
        self.db.commit()
        return True
        
    def restore_user_paper(self, user_id: uuid.UUID, file_hash: str) -> bool:
        """恢复被软删除的论文"""
        stmt = select(UserPaper).where(
            and_(UserPaper.user_id == user_id, UserPaper.file_hash == file_hash)
        )
        user_paper = self.db.execute(stmt).scalar_one_or_none()
        
        if user_paper and user_paper.is_deleted:
            user_paper.is_deleted = False
            user_paper.deleted_at = None
            self.db.commit()
            return True
        return False
        
    def update_pdf_status(self, file_hash: str, status: str, error: str = None):
        """更新全局文件的解析处理状态"""
        stmt = update(GlobalFile).where(GlobalFile.file_hash == file_hash).values(
            process_status=status,
            error_message=error
        )
        self.db.execute(stmt)
        self.db.commit()

    def update_pdf_task(self, file_hash: str, task_id: str):
        """绑定 Celery 任务 ID 到全局文件"""
        stmt = update(GlobalFile).where(GlobalFile.file_hash == file_hash).values(
            task_id=task_id
        )
        self.db.execute(stmt)
        self.db.commit()

    def get_process_progress(self, file_hash: str) -> dict:
        """
        获取 PDF 处理进度，返回 {status, task_id, current_page, total_pages, error}
        """
        gf = self.get_global_file(file_hash)
        if not gf:
            return None
        return {
            "status": gf.process_status,
            "task_id": gf.task_id,
            "current_page": gf.current_page or 0,
            "total_pages": gf.total_pages or 0,
            "error": gf.error_message,
        }

    def get_global_file_by_task_id(self, task_id: str) -> Optional[GlobalFile]:
        """根据 Celery 任务 ID 查找全局文件"""
        stmt = select(GlobalFile).where(GlobalFile.task_id == task_id)
        return self.db.execute(stmt).scalar_one_or_none()

    # ==================== PDF 段落 ====================

    def save_paragraphs(self, file_hash: str, paragraphs: List[Dict]):
        """
        批量保存PDF段落信息
        paragraphs: 包含 page_number, paragraph_index, original_text, bbox 的字典列表
        """
        objects = []
        for p in paragraphs:
            obj = PdfParagraph(
                file_hash=file_hash,
                page_number=p.get("page_number"),
                paragraph_index=p.get("paragraph_index"),
                original_text=p.get("original_text", ""),
                bbox=p.get("bbox")
            )
            objects.append(obj)
            
        if objects:
            self.db.add_all(objects)
            self.db.commit()

    def get_paragraphs(self, file_hash: str, page_number: Optional[int] = None, paragraph_index: Optional[int] = None) -> List[PdfParagraph]:
        """按文件哈希、页码或段落索引获取段落"""
        stmt = select(PdfParagraph).where(PdfParagraph.file_hash == file_hash)
        if page_number is not None:
            stmt = stmt.where(PdfParagraph.page_number == page_number)
        if paragraph_index is not None:
            stmt = stmt.where(PdfParagraph.paragraph_index == paragraph_index)
        
        stmt = stmt.order_by(PdfParagraph.page_number, PdfParagraph.paragraph_index)
        return self.db.execute(stmt).scalars().all()

    def get_paragraphs_range(self, file_hash: str, start_page: int, end_page: int) -> List[PdfParagraph]:
        """获取指定页码范围内的段落 (Inclusive)"""
        stmt = select(PdfParagraph).where(
            and_(
                PdfParagraph.file_hash == file_hash,
                PdfParagraph.page_number >= start_page,
                PdfParagraph.page_number <= end_page
            )
        ).order_by(PdfParagraph.page_number, PdfParagraph.paragraph_index)
        return self.db.execute(stmt).scalars().all()

    def get_paragraph_translations(self, file_hash: str, page_number: Optional[int] = None, paragraph_index: Optional[int] = None) -> List[Optional[str]]:
        """按文件哈希、页码或段落索引获取翻译文本列表"""
        stmt = select(PdfParagraph.translation_text).where(PdfParagraph.file_hash == file_hash)
        if page_number is not None:
            stmt = stmt.where(PdfParagraph.page_number == page_number)
        if paragraph_index is not None:
            stmt = stmt.where(PdfParagraph.paragraph_index == paragraph_index)
            
        stmt = stmt.order_by(PdfParagraph.page_number, PdfParagraph.paragraph_index)
        return self.db.execute(stmt).scalars().all()

    def update_paragraph_translation(self, file_hash: str, page_number: int, paragraph_index: int, translation: str):
        """更新段落的翻译内容"""
        stmt = update(PdfParagraph).where(
            and_(
                PdfParagraph.file_hash == file_hash,
                PdfParagraph.page_number == page_number,
                PdfParagraph.paragraph_index == paragraph_index
            )
        ).values(translation_text=translation)
        self.db.execute(stmt)
        self.db.commit()

    def get_paragraph_text_by_y(self, file_hash: str, page_number: int, y_coord: float) -> Optional[str]:
        """根据纵坐标获取所在页面的段落文本内容"""
        paragraphs = self.get_paragraphs(file_hash, page_number)
        for p in paragraphs:
            if p.bbox and isinstance(p.bbox, list) and len(p.bbox) >= 4:
                # bbox: [x, y, w, h]
                py = p.bbox[1]
                ph = p.bbox[3]
                if py <= y_coord <= (py + ph):
                    return p.original_text
        return None

    # ==================== PDF 图片 ====================

    def save_images(self, file_hash: str, images: List[Dict]):
        """
        批量保存PDF图片信息
        images: 包含 page_number, image_index, bbox, caption, image_path 的字典列表
        """
        objects = []
        for img in images:
            obj = PdfImage(
                file_hash=file_hash,
                page_number=img.get("page_number"),
                image_index=img.get("image_index"),
                bbox=img.get("bbox"),
                caption=img.get("caption"),
                image_path=img.get("image_path")
            )
            objects.append(obj)
            
        if objects:
            self.db.add_all(objects)
            self.db.commit()

    def get_images(self, file_hash: str, page_number: Optional[int] = None, image_index: Optional[int] = None) -> List[PdfImage]:
        """按文件哈希、页码或图片索引获取图片信息"""
        stmt = select(PdfImage).where(PdfImage.file_hash == file_hash)
        if page_number is not None:
            stmt = stmt.where(PdfImage.page_number == page_number)
        if image_index is not None:
            stmt = stmt.where(PdfImage.image_index == image_index)
        stmt = stmt.order_by(PdfImage.page_number, PdfImage.image_index)
        return self.db.execute(stmt).scalars().all()

    # ==================== 笔记 ====================

    def add_note(self, user_paper_id: uuid.UUID, content: str, keywords: List[str] = None) -> UserNote:
        """添加用户笔记"""
        note = UserNote(
            user_paper_id=user_paper_id,
            content=content,
            keywords=keywords or []
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_notes(self, user_paper_id: uuid.UUID) -> List[UserNote]:
        """按用户论文ID获取笔记"""
        stmt = select(UserNote).where(UserNote.user_paper_id == user_paper_id)
        stmt = stmt.order_by(UserNote.created_at)
        return self.db.execute(stmt).scalars().all()

    def update_note(self, note_id: int, content: str = None, keywords: List[str] = None):
        """更新笔记内容或关键词"""
        stmt = update(UserNote).where(UserNote.id == note_id)
        values = {}
        if content is not None:
            values['content'] = content
        if keywords is not None:
            values['keywords'] = keywords
            
        if values:
            stmt = stmt.values(**values)
            self.db.execute(stmt)
            self.db.commit()

    def delete_note(self, note_id: int):
        """删除指定笔记"""
        stmt = delete(UserNote).where(UserNote.id == note_id)
        self.db.execute(stmt)
        self.db.commit()

    # ==================== 高亮 ====================

    def add_highlight(self, user_paper_id: uuid.UUID, page_number: int, rects: List[Dict], selected_text: str = None, color: str = "#FFFF00") -> UserHighlight:
        """添加文本高亮记录"""
        highlight = UserHighlight(
            user_paper_id=user_paper_id,
            page_number=page_number,
            rects=rects, # JSONB
            selected_text=selected_text,
            color=color
        )
        self.db.add(highlight)
        self.db.commit()
        self.db.refresh(highlight)
        return highlight

    def get_highlights(self, user_paper_id: uuid.UUID, page_number: Optional[int] = None) -> List[UserHighlight]:
        """获取论文的高亮记录"""
        stmt = select(UserHighlight).where(UserHighlight.user_paper_id == user_paper_id)
        if page_number is not None:
            stmt = stmt.where(UserHighlight.page_number == page_number)
        return self.db.execute(stmt).scalars().all()

    def delete_highlight(self, highlight_id: int):
        """删除指定高亮记录"""
        stmt = delete(UserHighlight).where(UserHighlight.id == highlight_id)
        self.db.execute(stmt)
        self.db.commit()
        
    def update_highlight(self, highlight_id: int, color: str = None):
        """更新高亮颜色"""
        # Update logic if needed
        if color:
            stmt = update(UserHighlight).where(UserHighlight.id == highlight_id).values(color=color)
            self.db.execute(stmt)
            self.db.commit()

    # ==================== 聊天 ====================

    def create_chat_session(self, session_id: uuid.UUID, user_id: uuid.UUID, file_hash: str = None, title: str = "New Chat") -> ChatSession:
        """创建新的聊天会话"""
        session = ChatSession(
            id=session_id,
            user_id=user_id,
            user_paper_id=file_hash,
            title=title
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def get_chat_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Optional[ChatSession]:
        """获取指定用户的聊天会话"""
        stmt = select(ChatSession).where(
            and_(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()
        
    def list_chat_sessions(self, user_id: uuid.UUID, file_hash: Optional[str] = None, limit: int = 50) -> List[ChatSession]:
        """列出用户的聊天会话列表"""
        stmt = select(ChatSession).where(ChatSession.user_id == user_id)
        if file_hash:
            stmt = stmt.where(ChatSession.file_hash == file_hash)
        stmt = stmt.order_by(desc(ChatSession.updated_at)).limit(limit)
        return self.db.execute(stmt).scalars().all()
    
    def update_chat_session_title(self, session_id: uuid.UUID, user_id: uuid.UUID, title: str) -> bool:
        """更新聊天会话标题"""
        stmt = update(ChatSession).where(
            and_(ChatSession.id == session_id, ChatSession.user_id == user_id)
        ).values(title=title)
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount > 0
        
    def delete_chat_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> int:
        """删除聊天会话及其所有消息"""
        session = self.get_chat_session(session_id, user_id)
        if not session:
            return 0
        # 删除消息 
        del_msgs_stmt = delete(ChatMessage).where(ChatMessage.session_id == session_id)
        self.db.execute(del_msgs_stmt)
        # 删除会话
        stmt = delete(ChatSession).where(
            and_(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount
    
    def add_chat_message(self, session_id: uuid.UUID, user_id: uuid.UUID, role: str, content: str, citations: List[Dict] = None, attachments: List[Dict] = None) -> ChatMessage:
        """向会话中添加一条聊天消息"""
        stmt = select(ChatSession.id).where(and_(ChatSession.id == session_id, ChatSession.user_id == user_id))
        exists = self.db.execute(stmt).scalar_one_or_none()
        if not exists:
             raise ValueError(f"Session {session_id} not found for user {user_id}")

        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations or []
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)

        # 处理附件
        if attachments:
            for att_data in attachments:
                attachment = ChatAttachment(
                    message_id=msg.id,
                    category=att_data.get('category'),
                    file_path=att_data.get('file_path'),
                    data=att_data.get('data') or {}
                )
                self.db.add(attachment)
            self.db.commit()
            self.db.refresh(msg)
            
        return msg
    def get_chat_history(self, session_id: uuid.UUID, user_id: uuid.UUID) -> List[ChatMessage]:
        """获取指定会话的所有历史消息"""
        stmt = select(ChatMessage).join(ChatSession).where(
            and_(
                ChatMessage.session_id == session_id,
                ChatSession.user_id == user_id
            )
        ).order_by(asc(ChatMessage.created_at))
        return self.db.execute(stmt).scalars().all()
    
    # ==================== 图知识库 ====================

    # --- 项目 ---
    def create_graph_project(self, user_id: uuid.UUID, name: str, description: str = None) -> UserGraphProject:
        """创建新的图谱项目"""
        project = UserGraphProject(
            user_id=user_id,
            name=name,
            description=description
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_graph_project(self, project_id: uuid.UUID) -> Optional[UserGraphProject]:
        """获取指定 ID 的图谱项目"""
        stmt = select(UserGraphProject).where(UserGraphProject.id == project_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_graph_projects(self, user_id: uuid.UUID) -> List[UserGraphProject]:
        """列出用户的所有图谱项目"""
        stmt = select(UserGraphProject).where(UserGraphProject.user_id == user_id).order_by(desc(UserGraphProject.updated_at))
        return self.db.execute(stmt).scalars().all()

    def update_graph_project(self, project_id: uuid.UUID, name: str = None, description: str = None):
        """更新图谱项目的名称或描述"""
        if not name and not description:
            return
        
        values = {}
        if name: values['name'] = name
        if description: values['description'] = description
        
        stmt = update(UserGraphProject).where(UserGraphProject.id == project_id).values(**values)
        self.db.execute(stmt)
        self.db.commit()

    def delete_graph_project(self, project_id: uuid.UUID):
        """删除指定图谱项目"""
        stmt = delete(UserGraphProject).where(UserGraphProject.id == project_id)
        self.db.execute(stmt)
        self.db.commit()

    # --- 图节点 ---
    def create_graph_node(self, project_id: uuid.UUID, label: str, properties: str = None) -> GraphNode:
        """在项目中创建新节点"""
        node = GraphNode(
            project_id=project_id,
            label=label,
            properties=properties
        )
        self.db.add(node)
        try:
            self.db.commit()
            self.db.refresh(node)
        except Exception: 
            self.db.rollback()
            stmt = select(GraphNode).where(and_(GraphNode.project_id == project_id, GraphNode.label == label))
            node = self.db.execute(stmt).scalar_one()
            
        return node
        
    def list_graph_nodes(self, project_id: uuid.UUID) -> List[GraphNode]:
        """获取项目内的所有节点"""
        stmt = select(GraphNode).where(GraphNode.project_id == project_id)
        return self.db.execute(stmt).scalars().all()
        
    def delete_graph_node(self, node_id: uuid.UUID):
        """删除指定节点"""
        stmt = delete(GraphNode).where(GraphNode.id == node_id)
        self.db.execute(stmt)
        self.db.commit()

    # --- 图边 ---
    def create_graph_edge(self, project_id: uuid.UUID, source: uuid.UUID, target: uuid.UUID, relation: str = "related_to", desc: str = None) -> GraphEdge:
        """在项目中创建连接两个节点的边"""
        edge = GraphEdge(
            project_id=project_id,
            source_node_id=source,
            target_node_id=target,
            relation_type=relation,
            description=desc
        )
        self.db.add(edge)
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def list_graph_edges(self, project_id: uuid.UUID) -> List[GraphEdge]:
        """获取项目内的所有边"""
        stmt = select(GraphEdge).where(GraphEdge.project_id == project_id)
        return self.db.execute(stmt).scalars().all()
        
    def delete_graph_edge(self, edge_id: uuid.UUID):
        """删除指定边"""
        stmt = delete(GraphEdge).where(GraphEdge.id == edge_id)
        self.db.execute(stmt)
        self.db.commit()

    # --- 关联关系 ---
    
    def add_paper_to_project(self, project_id: uuid.UUID, user_paper_id: uuid.UUID):
        """将论文关联到图谱项目"""
        # M2M table insert
        stmt = insert(graph_paper_association).values(graph_id=project_id, user_paper_id=user_paper_id)
        stmt = stmt.on_conflict_do_nothing()
        self.db.execute(stmt)
        self.db.commit()

    def remove_paper_from_project(self, project_id: uuid.UUID, user_paper_id: uuid.UUID):
        """从图谱项目中移除论文关联"""
        stmt = delete(graph_paper_association).where(
            and_(
                graph_paper_association.c.graph_id == project_id,
                graph_paper_association.c.user_paper_id == user_paper_id
            )
        )
        self.db.execute(stmt)
        self.db.commit()

    def link_node_to_paper(self, node_id: uuid.UUID, user_paper_id: uuid.UUID):
        """建立节点与论文的链接记录"""
        stmt = insert(paper_node_link).values(graph_node_id=node_id, user_paper_id=user_paper_id)
        stmt = stmt.on_conflict_do_nothing()
        self.db.execute(stmt)
        self.db.commit()

    def link_node_to_note(self, node_id: uuid.UUID, note_id: int):
        """建立节点与笔记的链接记录"""
        stmt = insert(note_node_link).values(graph_node_id=node_id, user_note_id=note_id)
        stmt = stmt.on_conflict_do_nothing()
        self.db.execute(stmt)
        self.db.commit()

