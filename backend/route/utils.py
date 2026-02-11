"""
路由层公共工具函数
1. JWT 鉴权辅助
2. 段落 ID 解析
3. 高亮坐标归一化
"""
import uuid as _uuid
from functools import wraps
from flask import g, jsonify, current_app, request
from utils.pdf_engine import parse_paragraph_id as _parse_paragraph_id
from utils.jwt_handler import decode_token
import jwt as pyjwt


# ==================== JWT 配置辅助 ====================

def get_jwt_secret() -> str:
    """
    从 core.config.settings 或 app.config 中获取 JWT 密钥。
    必须在 config.yaml 中配置 jwt.secret, 否则使用不安全的默认值。
    """
    try:
        from core.config import settings
        if hasattr(settings, 'jwt') and settings.jwt:
            return settings.jwt.secret
        secret = getattr(settings, 'jwt_secret', None)
        if secret:
            return secret
    except Exception:
        pass
    # 回退：从 app.config 读取
    return current_app.config.get('JWT_SECRET', 'change-me-in-config-yaml')


def get_jwt_config():
    """
    获取完整 JWT 配置 (secret, access_expire_minutes, refresh_expire_days)
    """
    try:
        from core.config import settings
        if hasattr(settings, 'jwt') and settings.jwt:
            return {
                'secret': settings.jwt.secret,
                'access_expire_minutes': settings.jwt.access_expire_minutes,
                'refresh_expire_days': settings.jwt.refresh_expire_days,
            }
    except Exception:
        pass
    return {
        'secret': 'change-me-in-config-yaml',
        'access_expire_minutes': 30,
        'refresh_expire_days': 7,
    }


# ==================== 鉴权 ====================

def require_auth(f):
    """
    JWT 鉴权装饰器

    从 Authorization: Bearer <token> 头中解析 Access Token，
    验证签名与有效期，并将 user_id 挂载到 g.user_id (uuid.UUID)。

    失败时返回 401。
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header[7:]  # 去掉 "Bearer " 前缀

        try:
            secret = get_jwt_secret()
            payload = decode_token(token, secret=secret, expected_type='access')
            user_id = payload.get('sub')
            if not user_id:
                return jsonify({'error': 'Invalid token payload'}), 401

            # 将用户 ID 挂载到请求上下文
            g.user_id = _uuid.UUID(user_id)
            g.user_id_str = user_id

        except pyjwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except pyjwt.InvalidTokenError as e:
            return jsonify({'error': f'Invalid token: {str(e)}'}), 401
        except ValueError:
            return jsonify({'error': 'Invalid user ID in token'}), 401

        return f(*args, **kwargs)
    return decorated


# ==================== ID 解析 ====================

def parse_paragraph_id(paragraph_id: str):
    """
    从 paragraph_id 中解析出页码和段落索引
    委托给 pdf_engine.parse_paragraph_id

    Returns:
        (page_number, paragraph_index) 或 (None, None) 解析失败时
    """
    result = _parse_paragraph_id(paragraph_id)
    if result:
        return result['page_number'], result['index']
    return None, None


# ==================== 高亮坐标工具 ====================

class HighlightLogic:
    """
    坐标系转换和数据清洗（纯计算，不涉及 DB）
    """

    @staticmethod
    def normalize_coordinates(rects: list, page_width: float, page_height: float) -> list:
        """
        将前端 PDF.js 的绝对坐标 (x, y, w, h) 转换为相对坐标 (x0%, y0%, x1%, y1%)

        Args:
            rects: 前端传来的矩形列表 (Pixels)
            page_width: 当前页面渲染宽度 (Pixels)
            page_height: 当前页面渲染高度 (Pixels)

        Returns:
            归一化后的矩形列表 (0.0 - 1.0)
        """
        normalized = []
        if not page_width or not page_height:
            return rects

        for r in rects:
            x = float(r.get('x', r.get('left', 0)))
            y = float(r.get('y', r.get('top', 0)))
            w = float(r.get('width', 0))
            h = float(r.get('height', 0))

            n_rect = {
                'x0': round(x / page_width, 4),
                'y0': round(y / page_height, 4),
                'x1': round((x + w) / page_width, 4),
                'y1': round((y + h) / page_height, 4)
            }
            normalized.append(n_rect)

        return normalized

    @staticmethod
    def calculate_union_bbox(normalized_rects: list) -> dict:
        """
        计算多个矩形的并集（外包围盒）
        """
        if not normalized_rects:
            return {}

        x0 = min(r['x0'] for r in normalized_rects)
        y0 = min(r['y0'] for r in normalized_rects)
        x1 = max(r['x1'] for r in normalized_rects)
        y1 = max(r['y1'] for r in normalized_rects)

        return {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1}
