"""
全局 API 异常类

所有 APIError 子类会被 app.py 中的 @app.errorhandler(APIError) 自动捕获,
返回统一格式: {"code": "...", "error": "..."}
"""


class APIError(Exception):
    """所有 API 异常的基类"""
    status_code = 500
    code = "SERVER_ERROR"

    def __init__(self, message="Internal server error", code=None, status_code=None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self):
        return {"code": self.code, "error": self.message}


class BadRequestError(APIError):
    """400 — 请求参数错误"""
    status_code = 400
    code = "BAD_REQUEST"


class UnauthorizedError(APIError):
    """401 — 认证失败"""
    status_code = 401
    code = "UNAUTHORIZED"


class NotFoundError(APIError):
    """404 — 资源未找到"""
    status_code = 404
    code = "NOT_FOUND"
