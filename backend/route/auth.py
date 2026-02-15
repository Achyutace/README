"""
认证路由 (注册 / 登录 / 刷新令牌 / 获取当前用户)

所有认证接口都挂载在 /api/auth 前缀下
"""

from flask import Blueprint, request, jsonify, g
from core.database import SessionLocal
from repository.sql_repo import SQLRepository
from utils.jwt_handler import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from route.utils import require_auth, get_jwt_secret, get_jwt_config

import jwt as pyjwt   

# 定义蓝图
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# ==================== 注册 ====================

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册

    Request Body:
    {
        "username": "用户名",
        "email": "邮箱",
        "password": "密码"
    }

    Returns:
        201 — 注册成功, 返回 access_token + refresh_token
        400 — 参数缺失 / 邮箱已注册
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400

    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    # 参数校验
    if not username or not email or not password:
        return jsonify({'error': 'username, email and password are required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    db = SessionLocal()
    try:
        repo = SQLRepository(db)

        # 检查邮箱是否已注册
        if repo.get_user_by_email(email):
            return jsonify({'error': 'Email already registered'}), 400

        # 检查用户名是否已占用
        if repo.get_user_by_name(username):
            return jsonify({'error': 'Username already taken'}), 400

        # 创建用户
        pwd_hash = hash_password(password)
        user = repo.create_user(username=username, email=email, password_hash=pwd_hash)

        # 签发令牌
        jwt_conf = get_jwt_config()
        access_token = create_access_token(
            user_id=user.id,
            secret=jwt_conf['secret'],
            expires_minutes=jwt_conf['access_expire_minutes'],
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            secret=jwt_conf['secret'],
            expires_days=jwt_conf['refresh_expire_days'],
        )

        return jsonify({
            'message': 'Registration successful',
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
            },
            'accessToken': access_token,
            'refreshToken': refresh_token,
        }), 201

    except Exception as e:
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500
    finally:
        db.close()


# ==================== 登录 ====================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录

    Request Body:
    {
        "email": "邮箱",
        "password": "密码"
    }

    Returns:
        200 — 登录成功, 返回 access_token + refresh_token
        401 — 邮箱不存在或密码错误
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'email and password are required'}), 400

    db = SessionLocal()
    try:
        repo = SQLRepository(db)
        user = repo.get_user_by_email(email)

        if not user or not verify_password(password, user.password_hash):
            return jsonify({'error': 'Invalid email or password'}), 401

        # 签发令牌
        jwt_conf = get_jwt_config()
        access_token = create_access_token(
            user_id=user.id,
            secret=jwt_conf['secret'],
            expires_minutes=jwt_conf['access_expire_minutes'],
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            secret=jwt_conf['secret'],
            expires_days=jwt_conf['refresh_expire_days'],
        )

        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
            },
            'accessToken': access_token,
            'refreshToken': refresh_token,
        })

    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500
    finally:
        db.close()


# ==================== 刷新令牌 ====================

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """
    使用 Refresh Token 换取新的 Access Token

    Request Body:
    {
        "refreshToken": "..."
    }

    Returns:
        200 — 新的 access_token
        401 — refresh token 无效或已过期
    """
    data = request.get_json()
    if not data or not data.get('refreshToken'):
        return jsonify({'error': 'refreshToken is required'}), 400

    refresh_token = data['refreshToken']
    jwt_conf = get_jwt_config()
    secret = jwt_conf['secret']

    try:
        payload = decode_token(refresh_token, secret=secret, expected_type='refresh')
        user_id = payload['sub']

        # 验证用户仍然存在
        db = SessionLocal()
        try:
            repo = SQLRepository(db)
            import uuid as _uuid
            user = repo.get_user_by_id(_uuid.UUID(user_id))
            if not user:
                return jsonify({'error': 'User not found'}), 401
        finally:
            db.close()

        # 签发新的 Access Token
        new_access_token = create_access_token(
            user_id=user.id,
            secret=secret,
            expires_minutes=jwt_conf['access_expire_minutes'],
        )

        return jsonify({
            'accessToken': new_access_token,
        })

    except pyjwt.ExpiredSignatureError:
        return jsonify({'error': 'Refresh token expired, please login again'}), 401
    except pyjwt.InvalidTokenError as e:
        return jsonify({'error': f'Invalid refresh token: {str(e)}'}), 401


# ==================== 获取当前用户信息 ====================

@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    获取当前已登录用户的信息 (需要有效 Access Token)
    """
    db = SessionLocal()
    try:
        repo = SQLRepository(db)
        user = repo.get_user_by_id(g.user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'createdAt': user.created_at.isoformat() if user.created_at else None,
            }
        })
    finally:
        db.close()
