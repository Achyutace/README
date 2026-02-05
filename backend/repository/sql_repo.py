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
from ..model.db.chat_models import ChatSession, ChatMessage
from ..model.db.user_models import User
from ..model.db.graph_models import (
    UserGraphProject, GraphNode, GraphEdge,
    graph_paper_association, paper_node_link, note_node_link
)

class SQLRepository:
    def __init__(self, db: Session):
        self.db = db

    # ==================== User Management ====================
    
    def get_user_by_name(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_user(self, username: str, email: str, password_hash: str) -> User:
        user = User(username=username, email=email, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ==================== PDF / File Management ====================

    def get_global_file(self, file_hash: str) -> Optional[GlobalFile]:
        stmt = select(GlobalFile).where(GlobalFile.file_hash == file_hash)
        return self.db.execute(stmt).scalar_one_or_none()
        
    def create_global_file(self, file_hash: str, file_path: str, file_size: int = 0, page_count: int = 0, metadata: Dict = None) -> GlobalFile:
        # Check if exists to avoid duplication errors if called concurrently (simple check)
        existing = self.get_global_file(file_hash)
        if existing:
            return existing
            
        global_file = GlobalFile(
            file_hash=file_hash,
            file_path=file_path,
            file_size=file_size,
            page_count=page_count,
            metadata_info=metadata or {},
            process_status="PENDING" 
        )
        self.db.add(global_file)
        self.db.commit()
        self.db.refresh(global_file)
        return global_file

    def get_user_paper(self, user_id: uuid.UUID, file_hash: str) -> Optional[UserPaper]:
        stmt = select(UserPaper).where(
            and_(UserPaper.user_id == user_id, UserPaper.file_hash == file_hash)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_user_paper(self, user_id: uuid.UUID, file_hash: str, title: str) -> UserPaper:
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
        stmt = select(UserPaper).where(UserPaper.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(UserPaper.is_deleted == False)
        stmt = stmt.order_by(desc(UserPaper.added_at)).limit(limit)
        return self.db.execute(stmt).scalars().all()

    def delete_user_paper(self, user_id: uuid.UUID, file_hash: str, hard_delete: bool = False) -> bool:
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
        stmt = update(GlobalFile).where(GlobalFile.file_hash == file_hash).values(
            process_status=status,
            error_message=error
        )
        self.db.execute(stmt)
        self.db.commit()

    # ==================== Content Persistence (Paragraphs, Images) ====================

    def save_paragraphs(self, file_hash: str, paragraphs: List[Dict]):
        """
        paragraphs: List of dicts with keys: page_number, paragraph_index, original_text, bbox
        """
        # Using bulk insert or individual adds
        # Check for existing to avoid duplicates? Or assume clean state?
        # Generally we might want to clear existing paragraphs for this file/page before insert if re-processing
        # For now, just append/insert
        
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

    def save_images(self, file_hash: str, images: List[Dict]):
        """
        images: List of dicts with keys: page_number, image_index, bbox, caption
        """
        objects = []
        for img in images:
            obj = PdfImage(
                file_hash=file_hash,
                page_number=img.get("page_number"),
                image_index=img.get("image_index"),
                bbox=img.get("bbox"),
                caption=img.get("caption")
            )
            objects.append(obj)
            
        if objects:
            self.db.add_all(objects)
            self.db.commit()

    def get_paragraphs(self, file_hash: str, page_number: Optional[int] = None) -> List[PdfParagraph]:
        stmt = select(PdfParagraph).where(PdfParagraph.file_hash == file_hash)
        if page_number is not None:
            stmt = stmt.where(PdfParagraph.page_number == page_number)
        
        stmt = stmt.order_by(PdfParagraph.page_number, PdfParagraph.paragraph_index)
        return self.db.execute(stmt).scalars().all()

    def update_paragraph_translation(self, file_hash: str, page_number: int, paragraph_index: int, translation: str):
        stmt = update(PdfParagraph).where(
            and_(
                PdfParagraph.file_hash == file_hash,
                PdfParagraph.page_number == page_number,
                PdfParagraph.paragraph_index == paragraph_index
            )
        ).values(translation_text=translation)
        self.db.execute(stmt)
        self.db.commit()

    def get_images(self, file_hash: str, page_number: Optional[int] = None) -> List[PdfImage]:
        stmt = select(PdfImage).where(PdfImage.file_hash == file_hash)
        if page_number is not None:
            stmt = stmt.where(PdfImage.page_number == page_number)
        stmt = stmt.order_by(PdfImage.page_number, PdfImage.image_index)
        return self.db.execute(stmt).scalars().all()

    # ==================== Notes ====================

    def add_note(self, user_paper_id: uuid.UUID, page_number: int, content: str, keywords: List[str] = None) -> UserNote:
        note = UserNote(
            user_paper_id=user_paper_id,
            page_number=page_number,
            content=content,
            keywords=keywords or []
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_notes(self, user_paper_id: uuid.UUID, page_number: Optional[int] = None) -> List[UserNote]:
        stmt = select(UserNote).where(UserNote.user_paper_id == user_paper_id)
        if page_number is not None:
            stmt = stmt.where(UserNote.page_number == page_number)
        stmt = stmt.order_by(UserNote.created_at)
        return self.db.execute(stmt).scalars().all()

    def update_note(self, note_id: int, content: str = None, keywords: List[str] = None):
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
        stmt = delete(UserNote).where(UserNote.id == note_id)
        self.db.execute(stmt)
        self.db.commit()

    # ==================== Highlights ====================

    def add_highlight(self, user_paper_id: uuid.UUID, page_number: int, rects: List[Dict], selected_text: str = None, color: str = "#FFFF00") -> UserHighlight:
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
        stmt = select(UserHighlight).where(UserHighlight.user_paper_id == user_paper_id)
        if page_number is not None:
            stmt = stmt.where(UserHighlight.page_number == page_number)
        return self.db.execute(stmt).scalars().all()

    def delete_highlight(self, highlight_id: int):
        stmt = delete(UserHighlight).where(UserHighlight.id == highlight_id)
        self.db.execute(stmt)
        self.db.commit()
        
    def update_highlight(self, highlight_id: int, color: str = None):
        # Update logic if needed
        if color:
            stmt = update(UserHighlight).where(UserHighlight.id == highlight_id).values(color=color)
            self.db.execute(stmt)
            self.db.commit()

    # ==================== Chat ====================

    def create_chat_session(self, session_id: uuid.UUID, user_id: uuid.UUID, user_paper_id: Optional[uuid.UUID] = None, title: str = "New Chat") -> ChatSession:
        session = ChatSession(
            id=session_id,
            user_id=user_id,
            user_paper_id=user_paper_id,
            title=title
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_chat_session(self, session_id: uuid.UUID) -> Optional[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        return self.db.execute(stmt).scalar_one_or_none()
        
    def list_chat_sessions(self, user_id: uuid.UUID, limit: int = 50) -> List[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(desc(ChatSession.updated_at)).limit(limit)
        return self.db.execute(stmt).scalars().all()

    def update_chat_session_title(self, session_id: uuid.UUID, title: str):
        stmt = update(ChatSession).where(ChatSession.id == session_id).values(title=title)
        self.db.execute(stmt)
        self.db.commit()
        
    def delete_chat_session(self, session_id: uuid.UUID):
        stmt = delete(ChatSession).where(ChatSession.id == session_id)
        self.db.execute(stmt)
        self.db.commit()

    def add_chat_message(self, session_id: uuid.UUID, role: str, content: str, citations: List[Dict] = None) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_chat_history(self, session_id: uuid.UUID, limit: int = 20) -> List[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(asc(ChatMessage.created_at))
        # Logic to limit? Usually chat history is fine to fetch all or paginate. 
        # If limiting, we usually want the *latest* N messages.
        if limit:
            # Efficient pagination for chat history usually involves getting last N.
            # But order_by asc means we get first N. 
            # To get last N: order by desc, limit, then reverse.
            # For simplicity, if limit is small, fetch all is okay-ish or subquery.
            pass
            
        return self.db.execute(stmt).scalars().all()

    # ==================== Graph Knowledge Base ====================

    # --- Project ---
    def create_graph_project(self, user_id: uuid.UUID, name: str, description: str = None) -> UserGraphProject:
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
        stmt = select(UserGraphProject).where(UserGraphProject.id == project_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_graph_projects(self, user_id: uuid.UUID) -> List[UserGraphProject]:
        stmt = select(UserGraphProject).where(UserGraphProject.user_id == user_id).order_by(desc(UserGraphProject.updated_at))
        return self.db.execute(stmt).scalars().all()

    def update_graph_project(self, project_id: uuid.UUID, name: str = None, description: str = None):
        if not name and not description:
            return
        
        values = {}
        if name: values['name'] = name
        if description: values['description'] = description
        
        stmt = update(UserGraphProject).where(UserGraphProject.id == project_id).values(**values)
        self.db.execute(stmt)
        self.db.commit()

    def delete_graph_project(self, project_id: uuid.UUID):
        stmt = delete(UserGraphProject).where(UserGraphProject.id == project_id)
        self.db.execute(stmt)
        self.db.commit()

    # --- Graph Nodes ---
    def create_graph_node(self, project_id: uuid.UUID, label: str, properties: str = None) -> GraphNode:
        # Check if exists in project? UniqueConstraint should handle it, but maybe we want to return existing
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
            # Handle uniqueness violation gracefully if needed
            self.db.rollback()
            stmt = select(GraphNode).where(and_(GraphNode.project_id == project_id, GraphNode.label == label))
            node = self.db.execute(stmt).scalar_one()
            
        return node
        
    def list_graph_nodes(self, project_id: uuid.UUID) -> List[GraphNode]:
        stmt = select(GraphNode).where(GraphNode.project_id == project_id)
        return self.db.execute(stmt).scalars().all()
        
    def delete_graph_node(self, node_id: uuid.UUID):
        stmt = delete(GraphNode).where(GraphNode.id == node_id)
        self.db.execute(stmt)
        self.db.commit()

    # --- Graph Edges ---
    def create_graph_edge(self, project_id: uuid.UUID, source: uuid.UUID, target: uuid.UUID, relation: str = "related_to", desc: str = None) -> GraphEdge:
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
        stmt = select(GraphEdge).where(GraphEdge.project_id == project_id)
        return self.db.execute(stmt).scalars().all()
        
    def delete_graph_edge(self, edge_id: uuid.UUID):
        stmt = delete(GraphEdge).where(GraphEdge.id == edge_id)
        self.db.execute(stmt)
        self.db.commit()

    # --- Associations ---
    
    def add_paper_to_project(self, project_id: uuid.UUID, user_paper_id: uuid.UUID):
        # M2M table insert
        stmt = insert(graph_paper_association).values(graph_id=project_id, user_paper_id=user_paper_id)
        stmt = stmt.on_conflict_do_nothing()
        self.db.execute(stmt)
        self.db.commit()

    def remove_paper_from_project(self, project_id: uuid.UUID, user_paper_id: uuid.UUID):
        stmt = delete(graph_paper_association).where(
            and_(
                graph_paper_association.c.graph_id == project_id,
                graph_paper_association.c.user_paper_id == user_paper_id
            )
        )
        self.db.execute(stmt)
        self.db.commit()

    def link_node_to_paper(self, node_id: uuid.UUID, user_paper_id: uuid.UUID):
        stmt = insert(paper_node_link).values(graph_node_id=node_id, user_paper_id=user_paper_id)
        stmt = stmt.on_conflict_do_nothing()
        self.db.execute(stmt)
        self.db.commit()

    def link_node_to_note(self, node_id: uuid.UUID, note_id: int):
        stmt = insert(note_node_link).values(graph_node_id=node_id, user_note_id=note_id)
        stmt = stmt.on_conflict_do_nothing()
        self.db.execute(stmt)
        self.db.commit()

