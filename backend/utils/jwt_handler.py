"""
密码工具模块

提供:
1. 密码哈希 (bcrypt)
2. 密码校验 (bcrypt)
"""

import bcrypt


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
