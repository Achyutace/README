"""
认证路由 (注册 / 登录 / 刷新令牌 / 获取当前用户)

所有认证接口都挂载在 /api/auth 前缀下
"""

from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token as jwt_decode_token,
    jwt_required,
)
from core.database import SessionLocal
from repository.sql_repo import SQLRepository
from utils.jwt_handler import hash_password, verify_password

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
        return jsonify({'code': 'MISSING_BODY', 'error': 'Missing request body'}), 400

    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    # 参数校验
    if not username or not email or not password:
        return jsonify({'code': 'MISSING_FIELDS', 'error': 'username, email and password are required'}), 400

    if len(password) < 6:
        return jsonify({'code': 'PASSWORD_TOO_SHORT', 'error': 'Password must be at least 6 characters'}), 400

    db = SessionLocal()
    try:
        repo = SQLRepository(db)

        # 检查邮箱是否已注册
        if repo.get_user_by_email(email):
            return jsonify({'code': 'EMAIL_EXISTS', 'error': 'Email already registered'}), 400

        # 检查用户名是否已占用
        if repo.get_user_by_name(username):
            return jsonify({'code': 'USERNAME_TAKEN', 'error': 'Username already taken'}), 400

        # 创建用户
        pwd_hash = hash_password(password)
        user = repo.create_user(username=username, email=email, password_hash=pwd_hash)

        # 签发令牌
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

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
        return jsonify({'code': 'MISSING_BODY', 'error': 'Missing request body'}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'code': 'MISSING_FIELDS', 'error': 'email and password are required'}), 400

    db = SessionLocal()
    try:
        repo = SQLRepository(db)
        user = repo.get_user_by_email(email)

        if not user or not verify_password(password, user.password_hash):
            return jsonify({'code': 'INVALID_CREDENTIALS', 'error': 'Invalid email or password'}), 401

        # 签发令牌
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

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
        return jsonify({'code': 'MISSING_TOKEN', 'error': 'refreshToken is required'}), 400

    refresh_token = data['refreshToken']

    payload = jwt_decode_token(refresh_token)
    user_id = payload['sub']

    # 验证用户仍然存在
    import uuid as _uuid
    db = SessionLocal()
    try:
        repo = SQLRepository(db)
        user = repo.get_user_by_id(_uuid.UUID(user_id))
        if not user:
            return jsonify({'code': 'USER_NOT_FOUND', 'error': 'User not found'}), 401
    finally:
        db.close()

    # 签发新的 Access Token
    new_access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'accessToken': new_access_token,
    })


# ==================== 获取当前用户信息 ====================

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    获取当前已登录用户的信息 (需要有效 Access Token)
    """
    db = SessionLocal()
    try:
        repo = SQLRepository(db)
        user = repo.get_user_by_id(g.user_id)

        if not user:
            return jsonify({'code': 'USER_NOT_FOUND', 'error': 'User not found'}), 404

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
