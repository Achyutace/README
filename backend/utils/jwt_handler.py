"""
JWT 认证工具模块

提供:
1. 密码哈希与校验 (bcrypt)
2. Access Token / Refresh Token 的签发与验证 (PyJWT)
"""

import jwt
import bcrypt
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any


# ==================== 默认配置 ====================

_DEFAULT_SECRET = "change-me-in-config-yaml"   # 仅作回退，生产环境必须在 config.yaml 中配置
_DEFAULT_ACCESS_EXPIRE_MINUTES = 30
_DEFAULT_REFRESH_EXPIRE_DAYS = 7
_ALGORITHM = "HS256"


# ==================== 密码工具 ====================

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


# ==================== Token 工具 ====================

def create_access_token(
    user_id: uuid.UUID,
    secret: str = _DEFAULT_SECRET,
    expires_minutes: int = _DEFAULT_ACCESS_EXPIRE_MINUTES,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    签发 Access Token

    Payload 结构:
        sub  — 用户 UUID (字符串)
        type — "access"
        exp  — 过期时间
        iat  — 签发时间
        jti  — 唯一 Token ID
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": now + timedelta(minutes=expires_minutes),
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def create_refresh_token(
    user_id: uuid.UUID,
    secret: str = _DEFAULT_SECRET,
    expires_days: int = _DEFAULT_REFRESH_EXPIRE_DAYS,
) -> str:
    """
    签发 Refresh Token (仅用于换取新 Access Token)
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": now + timedelta(days=expires_days),
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_token(
    token: str,
    secret: str = _DEFAULT_SECRET,
    expected_type: str = "access",
) -> Dict[str, Any]:
    """
    解码并验证 JWT Token

    Args:
        token: JWT 字符串
        secret: 签名密钥
        expected_type: 期望的 token 类型 ("access" / "refresh")

    Returns:
        解码后的 payload 字典

    Raises:
        jwt.ExpiredSignatureError  — token 已过期
        jwt.InvalidTokenError     — token 无效或类型不匹配
    """
    payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])

    # 校验 token 类型
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"Expected token type '{expected_type}', got '{payload.get('type')}'"
        )

    return payload
