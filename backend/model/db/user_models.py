from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .base import Base

class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    papers = relationship("UserPaper", back_populates="user")
    graph_projects = relationship("UserGraphProject", back_populates="user")
