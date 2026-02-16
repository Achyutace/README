"""
路由层公共工具函数
1. 段落 ID 解析
2. 高亮坐标归一化
"""
from utils.pdf_engine import parse_paragraph_id as _parse_paragraph_id


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
