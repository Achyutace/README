from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .base import Base
from .graph_models import graph_paper_association, paper_node_link, note_node_link

# ==========================================
# 全局文件
# ==========================================

class GlobalFile(Base):
    """
    物理文件表：存储 PDF 文件的物理属性。
    注：所有上传同一份 PDF (Hash相同) 的用户共享此条目。
    """
    __tablename__ = "global_files"

    # 文件哈希(pdfID)
    file_hash = Column(String(64), primary_key=True, comment="文件的SHA256值")
    
    # 存储
    file_path = Column(String, nullable=False, comment="OSS/S3上的存储路径 key")
    file_size = Column(Integer, comment="文件字节大小")
    total_pages = Column(Integer, default=0, comment="PDF 总页数")
    
    # Celery 任务跟踪
    task_id = Column(String(64), nullable=True, index=True, comment="Celery 异步任务 ID")
    current_page = Column(Integer, default=0, comment="当前已解析到的页码 (用于进度追踪)")
    process_status = Column(String(20), default="pending")  # pending -> processing -> completed / failed
    error_message = Column(Text, nullable=True)
    
    # 元数据
    metadata_info = Column(JSONB, default={}, comment="PDF原生元数据: author, publish_date, doi")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="最后被访问/引用的时间 (用于GC)")
    
    # 关系
    paragraphs = relationship("PdfParagraph", back_populates="file", cascade="all, delete-orphan")
    images = relationship("PdfImage", back_populates="file", cascade="all, delete-orphan")
    ref_user_papers = relationship("UserPaper", back_populates="global_file")


class PdfParagraph(Base):
    """
    段落内容表：解析后的段落文本+翻译
    """
    __tablename__ = "pdf_paragraphs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_hash = Column(String(64), ForeignKey("global_files.file_hash"), nullable=False, index=True)
    
    page_number = Column(Integer, nullable=False)
    paragraph_index = Column(Integer, nullable=False, comment="该页第几个段落")
    
    # 文本内容
    original_text = Column(Text, nullable=False)
    translation_text = Column(Text, nullable=True, comment="翻译好的文本(可选)")
    
    # 坐标信息
    bbox = Column(JSONB, comment="[x, y, w, h] 归一化坐标")

    # 复合唯一索引
    __table_args__ = (
        UniqueConstraint('file_hash', 'page_number', 'paragraph_index', name='uix_para_loc'),
    )
    
    file = relationship("GlobalFile", back_populates="paragraphs")


class PdfImage(Base):
    """
    图片元数据表：坐标和描述
    """
    __tablename__ = "pdf_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_hash = Column(String(64), ForeignKey("global_files.file_hash"), nullable=False, index=True)
    
    page_number = Column(Integer, nullable=False)
    image_index = Column(Integer, nullable=False)
    
    # 坐标
    bbox = Column(JSONB, nullable=False, comment="[x, y, w, h]")

    # 存储路径
    image_path = Column(String, nullable=True, comment="OSS/S3上的存储路径 key")
    
    # 检索周边文字得到的图片描述，用于搜索
    caption = Column(Text, nullable=True)
    
    file = relationship("GlobalFile", back_populates="images")


class UserPaper(Base):
    """
    用户文献表
    """
    __tablename__ = "user_papers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    file_hash = Column(String(64), ForeignKey("global_files.file_hash"), nullable=False)
    
    # 个性化信息
    title = Column(String(255), nullable=False, comment="用户自定义标题")
    read_status = Column(String(20), default="unread", comment="阅读状态: unread, reading, finished")
    tags = Column(ARRAY(String), default=[], comment="用户标签")
    
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    last_read_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 软删除 
    is_deleted = Column(Boolean, default=False, comment="逻辑删除标记")
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment="逻辑删除时间")

    # 关系
    user = relationship("User", back_populates="papers")
    global_file = relationship("GlobalFile", back_populates="ref_user_papers")
    notes = relationship("UserNote", back_populates="user_paper", cascade="all, delete-orphan")
    highlights = relationship("UserHighlight", back_populates="user_paper", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user_paper")
    
    # 属于哪些图谱项目
    included_in_graphs = relationship("UserGraphProject", secondary=graph_paper_association, back_populates="papers")
    # 关联了哪些图谱节点 (Keyword)
    linked_graph_nodes = relationship("GraphNode", secondary=paper_node_link, back_populates="linked_papers")
    __table_args__ = (UniqueConstraint('user_id', 'file_hash', name='uix_user_file'),)

class UserNote(Base):
    """用户笔记"""
    __tablename__ = "user_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_paper_id = Column(UUID(as_uuid=True), ForeignKey("user_papers.id"), nullable=False, index=True)
    
    title = Column(String(255), nullable=True, comment="笔记标题")
    content = Column(Text, nullable=False) # 笔记内容(Markdown)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    keywords = Column(ARRAY(String), default=[], comment="笔记关键词/标签")

    user_paper = relationship("UserPaper", back_populates="notes")
    linked_graph_nodes = relationship("GraphNode", secondary=note_node_link, back_populates="linked_notes")


class UserHighlight(Base):
    """用户高亮"""
    __tablename__ = "user_highlights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_paper_id = Column(UUID(as_uuid=True), ForeignKey("user_papers.id"), nullable=False, index=True)
    
    page_number = Column(Integer, nullable=False)
    selected_text = Column(Text, nullable=True)
    
    # 高亮区域列表
    rects = Column(JSONB, nullable=False, comment="[{x,y,w,h}, {x,y,w,h}]")
    color = Column(String(20), default="#FFFF00")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user_paper = relationship("UserPaper", back_populates="highlights")
