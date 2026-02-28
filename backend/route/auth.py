"""
认证路由 (注册 / 登录 / 刷新令牌 / 获取当前用户)

所有认证接口都挂载在 /api/auth 前缀下
"""

from flask import Blueprint, request, jsonify, g
from core.database import db
from repository.sql_repo import SQLRepository
from core.security import (
    jwt_required,
)
from utils.validators import validate_registration_data, validate_login_data
from services.auth_service import AuthService
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

    # 1. 纯函数校验
    is_valid, err_code, err_msg = validate_registration_data(username, email, password)
    if not is_valid:
        return jsonify({'code': err_code, 'error': err_msg}), 400

    db_session = db.session
    try:
        auth_svc = AuthService(SQLRepository(db_session))
        res_data, err_code, err_msg = auth_svc.register_user(username, email, password)

        if err_code:
            return jsonify({'code': err_code, 'error': err_msg}), 400

        response = jsonify({
            'message': 'Registration successful',
            'user': res_data['user'],
            'accessToken': res_data['accessToken'],
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

    # 1. 纯函数校验
    is_valid, err_code, err_msg = validate_login_data(email, password)
    if not is_valid:
        return jsonify({'code': err_code, 'error': err_msg}), 400

    db_session = db.session
    try:
        auth_svc = AuthService(SQLRepository(db_session))
        res_data, err_code, err_msg = auth_svc.login_user(email, password)

        if err_code:
            return jsonify({'code': err_code, 'error': err_msg}), 401

        response = jsonify({
            'message': 'Login successful',
            'user': res_data['user'],
            'accessToken': res_data['accessToken'],
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

    auth_svc = AuthService(SQLRepository(db.session))
    res_data, err_code, err_msg = auth_svc.refresh_token(refresh_token)

    if err_code:
        return jsonify({'code': err_code, 'error': err_msg}), 401

    return jsonify(res_data)


# ==================== 获取当前用户信息 ====================

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    获取当前已登录用户的信息 (需要有效 Access Token)
    """
    auth_svc = AuthService(SQLRepository(db.session))
    res_data, err_code, err_msg = auth_svc.get_current_user_info(g.user_id)

    if err_code:
        return jsonify({'code': err_code, 'error': err_msg}), 404

    return jsonify(res_data)
