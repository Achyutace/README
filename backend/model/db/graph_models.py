from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Table, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .base import Base

# 关联表 

# 1. 论文 <-> 图谱节点 (代表这篇论文包含这个核心关键词)
paper_node_link = Table(
    'paper_node_link', Base.metadata,
    Column('user_paper_id', Uuid, ForeignKey('user_papers.id', ondelete="CASCADE"), primary_key=True),
    Column('graph_node_id', Uuid, ForeignKey('graph_nodes.id', ondelete="CASCADE"), primary_key=True)
)

# 2. 笔记 <-> 图谱节点 (代表这条笔记关联了这个核心关键词)
note_node_link = Table(
    'note_node_link', Base.metadata,
    Column('user_note_id', Integer, ForeignKey('user_notes.id', ondelete="CASCADE"), primary_key=True),
    Column('graph_node_id', Uuid, ForeignKey('graph_nodes.id', ondelete="CASCADE"), primary_key=True)
)

# 3. 论文 <-> 图谱项目 (论文属于哪个图谱上下文)
graph_paper_association = Table(
    'graph_paper_association', Base.metadata,
    Column('graph_id', Uuid, ForeignKey('user_graph_projects.id', ondelete="CASCADE"), primary_key=True),
    Column('user_paper_id', Uuid, ForeignKey('user_papers.id', ondelete="CASCADE"), primary_key=True)
)


# 实体表

class UserGraphProject(Base):
    """
    用户知识图谱项目表
    """
    __tablename__ = "user_graph_projects"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="graph_projects")
    
    # 包含的节点
    nodes = relationship("GraphNode", back_populates="project", cascade="all, delete-orphan")
    
    # 包含的边
    edges = relationship("GraphEdge", back_populates="project", cascade="all, delete-orphan")

    # 包含的论文 (上下文)
    papers = relationship("UserPaper", secondary=graph_paper_association, back_populates="included_in_graphs")


class GraphNode(Base):
    """
    图谱节点表 (Keyword)
    """
    __tablename__ = "graph_nodes"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid, ForeignKey("user_graph_projects.id"), nullable=False, index=True)
    
    # 节点核心信息 (即关键词)
    label = Column(String(255), nullable=False, comment="显示的关键词，如 'Transformer'")
    
    # 节点属性 (摘要)
    properties = Column(Text, nullable=True, comment="JSON string for UI props: color, size, etc.")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    project = relationship("UserGraphProject", back_populates="nodes")
    
    # 关联到哪些论文 (M2M)
    linked_papers = relationship("UserPaper", secondary=paper_node_link, back_populates="linked_graph_nodes")
    
    # 关联到哪些笔记 (M2M)
    linked_notes = relationship("UserNote", secondary=note_node_link, back_populates="linked_graph_nodes")
    
    # 一个项目内关键词不能重复
    __table_args__ = (
        UniqueConstraint('project_id', 'label', name='uix_project_node_label'),
    )


class GraphEdge(Base):
    """
    图谱边表
    """
    __tablename__ = "graph_edges"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid, ForeignKey("user_graph_projects.id"), nullable=False, index=True)
    
    source_node_id = Column(Uuid, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(Uuid, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    
    # 关系类型 TODO
    # 建议在代码层或数据库层做 Enum 约束，例如: 
    # 'is_a' (是...), 'part_of' (属于...), 'related_to' (相关), 'causes' (导致), 'supports' (支持)
    relation_type = Column(String(50), nullable=False, default="related_to")
    
    # 边的权重或描述 (可选)
    description = Column(String(255), nullable=True, comment="具体关系描述")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    project = relationship("UserGraphProject", back_populates="edges")
    source_node = relationship("GraphNode", foreign_keys=[source_node_id])
    target_node = relationship("GraphNode", foreign_keys=[target_node_id])
