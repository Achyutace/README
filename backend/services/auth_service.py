"""
认证业务逻辑服务
"""

import uuid
from typing import Dict, Tuple, Optional
from repository.sql_repo import SQLRepository
from core.security import hash_password, verify_password, create_tokens, decode_refresh_token


class AuthService:
    """认证业务逻辑服务类，分离路由与数据库操作"""
    def __init__(self, repo: SQLRepository):
        self.repo = repo

    def register_user(self, username: str, email: str, password: str) -> Tuple[Optional[Dict], Optional[str], Optional[str]]:
        # 检查邮箱是否已注册
        if self.repo.get_user_by_email(email):
            return None, 'EMAIL_EXISTS', 'Email already registered'

        # 检查用户名是否已占用
        if self.repo.get_user_by_name(username):
            return None, 'USERNAME_TAKEN', 'Username already taken'

        pwd_hash = hash_password(password)
        from core.database import db
        try:
            user = self.repo.create_user(username=username, email=email, password_hash=pwd_hash)
            db.session.commit()
            tokens = create_tokens(str(user.id))
            
            return {
                'user': {
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                },
                'accessToken': tokens['accessToken'],
                'refreshToken': tokens['refreshToken']
            }, None, None
        except Exception as e:
            db.session.rollback()
            return None, 'REGISTRATION_FAILED', str(e)

    def login_user(self, email: str, password: str) -> Tuple[Optional[Dict], Optional[str], Optional[str]]:
        user = self.repo.get_user_by_email(email)
        if not user:
            # 防御时间盲注
            hash_password(password)
            return None, 'INVALID_CREDENTIALS', 'Invalid email or password'
            
        if not verify_password(password, user.password_hash):
            return None, 'INVALID_CREDENTIALS', 'Invalid email or password'
            
        tokens = create_tokens(str(user.id))
        return {
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
            },
            'accessToken': tokens['accessToken'],
            'refreshToken': tokens['refreshToken']
        }, None, None

    def refresh_token(self, refresh_token: str) -> Tuple[Optional[Dict], Optional[str], Optional[str]]:
        user_id_str = decode_refresh_token(refresh_token)
        user = self.repo.get_user_by_id(uuid.UUID(user_id_str))
        
        if not user:
            return None, 'USER_NOT_FOUND', 'User not found'
            
        tokens = create_tokens(str(user.id))
        return {
            'accessToken': tokens['accessToken']
        }, None, None

    def get_current_user_info(self, user_id: uuid.UUID) -> Tuple[Optional[Dict], Optional[str], Optional[str]]:
        user = self.repo.get_user_by_id(user_id)
        if not user:
            return None, 'USER_NOT_FOUND', 'User not found'
            
        return {
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'createdAt': user.created_at.isoformat() if user.created_at else None,
            }
        }, None, None
