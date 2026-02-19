"""
安全模块 — JWT 校验 & 用户鉴权

职责:
1. 密码哈希 / 校验 (bcrypt)
2. JWT 令牌签发 (access + refresh)
3. 从请求上下文中提取当前用户 ID
4. Re-export jwt_required 供路由层直接使用
"""

import uuid
import bcrypt
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token as _decode_token,
    jwt_required,                   # noqa: F401 
    verify_jwt_in_request,
    get_jwt_identity,
)


# ==================== 密码 ====================

def hash_password(plain_password: str) -> str:
    """将明文密码哈希为 bcrypt 字符串"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ==================== 令牌 ====================

def create_tokens(user_id: str) -> dict:
    """
    为指定用户签发 access_token + refresh_token。

    Returns:
        {"accessToken": "...", "refreshToken": "..."}
    """
    return {
        "accessToken": create_access_token(identity=user_id),
        "refreshToken": create_refresh_token(identity=user_id),
    }


def decode_refresh_token(token: str) -> str:
    """
    解码 refresh token，返回其中的 user_id (字符串)。
    若 token 无效 / 过期，flask_jwt_extended 会自动抛出异常。
    """
    payload = _decode_token(token)
    return payload["sub"]


# ==================== 用户身份 ====================

def try_get_current_user_id() -> uuid.UUID | None:
    """
    尝试从当前请求的 JWT 中解析 user_id。
    - 成功: 返回 UUID
    - 无 token / token 无效: 返回 None（适用于公开接口）
    """
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity:
            return uuid.UUID(identity)
    except Exception:
        pass
    return None
