from typing import Tuple

def validate_registration_data(username: str, email: str, password: str) -> Tuple[bool, str, str]:
    """验证注册请求参数"""
    if not username or not email or not password:
        return False, 'MISSING_FIELDS', 'username, email and password are required'
    if len(password) < 6:
        return False, 'PASSWORD_TOO_SHORT', 'Password must be at least 6 characters'
    return True, '', ''

def validate_login_data(email: str, password: str) -> Tuple[bool, str, str]:
    """验证登录请求参数"""
    if not email or not password:
        return False, 'MISSING_FIELDS', 'email and password are required'
    return True, '', ''
