"""
认证路由 (注册 / 登录 / 刷新令牌 / 获取当前用户)

所有认证接口都挂载在 /api/auth 前缀下
"""

from flask import Blueprint, request, jsonify, g
from core.database import db
from repository.sql_repo import SQLRepository
from core.security import (
    hash_password,
    verify_password,
    create_tokens,
    decode_refresh_token,
    jwt_required,
)
from core.config import settings

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

    db_session = db.session
    try:
        repo = SQLRepository(db_session)

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
        tokens = create_tokens(str(user.id))

        response = jsonify({
            'message': 'Registration successful',
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
            },
            'accessToken': tokens['accessToken'],
        })

        response.set_cookie(
            'refreshToken',
            tokens['refreshToken'],
            httponly=True,
            samesite='Lax',
            secure=(settings.env == "production"),  
            path='/api/auth/refresh',
            max_age=settings.jwt.refresh_expire_days * 24 * 3600
        )

        return response, 201

    except Exception:
        db_session.rollback()
        raise


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

    db_session = db.session
    try:
        repo = SQLRepository(db_session)
        user = repo.get_user_by_email(email)

        if not user:
            # 防御时间盲注：用户不存在时也执行等量的哈希消耗
            hash_password(password)
            return jsonify({'code': 'INVALID_CREDENTIALS', 'error': 'Invalid email or password'}), 401

        if not verify_password(password, user.password_hash):
            return jsonify({'code': 'INVALID_CREDENTIALS', 'error': 'Invalid email or password'}), 401

        # 签发令牌
        tokens = create_tokens(str(user.id))

        response = jsonify({
            'message': 'Login successful',
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
            },
            'accessToken': tokens['accessToken'],
        })

        response.set_cookie(
            'refreshToken',
            tokens['refreshToken'],
            httponly=True,
            samesite='Lax',
            secure=(settings.env == "production"),
            path='/api/auth/refresh',
            max_age=settings.jwt.refresh_expire_days * 24 * 3600
        )

        return response

    except Exception:
        db_session.rollback()
        raise


# ==================== 刷新令牌 ====================

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """
    使用 Refresh Token 换取新的 Access Token

    Request Body (可选,向后兼容):
    {
        "refreshToken": "..."
    }
    同时也会从 HttpOnly 的 Cookie 中读取 refreshToken。

    Returns:
        200 — 新的 access_token
        401 — refresh token 无效或已过期
    """
    data = request.get_json(silent=True) or {}
    
    # 优先从 cookie 获取，若无尝试从 body（为了向后兼容）
    refresh_token = request.cookies.get('refreshToken') or data.get('refreshToken')

    if not refresh_token:
        return jsonify({'code': 'MISSING_TOKEN', 'error': 'refreshToken is required in Cookie or Body'}), 400

    user_id = decode_refresh_token(refresh_token)

    # 验证用户仍然存在
    import uuid as _uuid
    repo = SQLRepository(db.session)
    user = repo.get_user_by_id(_uuid.UUID(user_id))
    if not user:
        return jsonify({'code': 'USER_NOT_FOUND', 'error': 'User not found'}), 401

    # 签发新的 Access Token
    tokens = create_tokens(str(user.id))

    return jsonify({
        'accessToken': tokens['accessToken'],
    })


# ==================== 获取当前用户信息 ====================

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    获取当前已登录用户的信息 (需要有效 Access Token)
    """
    repo = SQLRepository(db.session)
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
