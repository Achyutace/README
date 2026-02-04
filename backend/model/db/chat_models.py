from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .base import Base

# ==========================================
# 3. 对话交互层 (Interaction Layer)
# ==========================================

class ChatSession(Base):
    """
    对话会话
    """
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # 可选：绑定特定论文。如果为空，则是"全库对话"模式
    user_paper_id = Column(UUID(as_uuid=True), ForeignKey("user_papers.id"), nullable=True)
    
    title = Column(String(255), default="New Chat")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user_paper = relationship("UserPaper", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """对话消息"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    
    role = Column(String(20), nullable=False) # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    
    # RAG 引用源：非常重要
    # 存储: [{ "source_type": "vector", "id": "vec_123", "text": "...", "score": 0.8 }, 
    #       { "source_type": "graph", "id": "node_456", "name": "Transformer" }]
    citations = Column(JSONB, nullable=True) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    session = relationship("ChatSession", back_populates="messages")
