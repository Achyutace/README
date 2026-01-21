"""
高亮的路由：点击高亮后后台存储这部分高亮数据；用户切换PDF后返回对应论文的高亮数据
"""
import json
from flask import Blueprint, request, jsonify, current_app, g
from models.database import Database  

# 定义蓝图
highlight_bp = Blueprint('highlight', __name__, url_prefix='/api/highlight')


class HighlightLogic:
    """
    坐标系转换和数据清洗
    """

    @staticmethod
    def normalize_coordinates(rects: list, page_width: float, page_height: float) -> list:
        """
        [核心逻辑] 坐标归一化
        将前端 PDF.js 的绝对坐标 (x, y, w, h) 转换为 相对坐标 (x0%, y0%, x1%, y1%)
        
        Args:
            rects: 前端传来的矩形列表 (Pixels)
            page_width: 当前页面渲染宽度 (Pixels)
            page_height: 当前页面渲染高度 (Pixels)
            
        Returns:
            归一化后的矩形列表 (0.0 - 1.0)
        """
        normalized = []
        
        # 防止除以零错误
        if not page_width or not page_height:
            return rects

        for r in rects:
            # 兼容 PDF.js 可能传来的不同字段名 (x/left, y/top)
            x = float(r.get('x', r.get('left', 0)))
            y = float(r.get('y', r.get('top', 0)))
            w = float(r.get('width', 0))
            h = float(r.get('height', 0))
            
            # 转换为相对坐标 (0.0 - 1.0)
            # 格式: x0, y0, x1, y1
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
        用于在列表中快速定位或生成缩略图
        """
        if not normalized_rects:
            return {}
            
        x0 = min(r['x0'] for r in normalized_rects)
        y0 = min(r['y0'] for r in normalized_rects)
        x1 = max(r['x1'] for r in normalized_rects)
        y1 = max(r['y1'] for r in normalized_rects)
        
        return {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1}

# ==========================================
# Router Layer: 接口定义
# ==========================================

def get_file_hash(pdf_id: str) -> str:
    """辅助函数：通过 PdfService 获取路径并计算 Hash"""
    try:
        # g.pdf_service 需要在 app.py 的 before_request 中挂载
        filepath = g.pdf_service.get_filepath(pdf_id)
        return Database.calculate_file_hash(filepath)
    except Exception as e:
        current_app.logger.error(f"Hash calculation failed for {pdf_id}: {e}")
        return None

@highlight_bp.route('/', methods=['POST'])
def create_highlight():
    """
    创建高亮
    
    Request Body:
    {
        "pdfId": "uuid...",
        "page": 1,
        "rects": [{"x": 100, "y": 100, "width": 50, "height": 20}], // PDF.js getClientRects()
        "pageWidth": 800,  // 当前 Canvas 宽度
        "pageHeight": 1200, // 当前 Canvas 高度
        "text": "选中的文本内容",
        "color": "#FFFF00",
        "comment": "可选注释"
    }
    """
    data = request.get_json()
    
    # 1. 参数校验
    required_fields = ['pdfId', 'page', 'rects', 'pageWidth', 'pageHeight']
    if not all(k in data for k in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        pdf_id = data['pdfId']
        
        # 2. ID 映射 (PDF ID -> File Hash)
        file_hash = get_file_hash(pdf_id)
        if not file_hash:
            return jsonify({'error': 'PDF file not found'}), 404

        # 3. [Service Logic] 坐标转换 (Pixel -> Relative)
        # 这一步确保了高亮位置与屏幕分辨率无关
        normalized_rects = HighlightLogic.normalize_coordinates(
            data['rects'], 
            data['pageWidth'], 
            data['pageHeight']
        )
        
        # 4. 计算主包围盒 (Union BBox)
        union_bbox = HighlightLogic.calculate_union_bbox(normalized_rects)

        # 5. 构造存储数据
        # 我们将详细的 rects 封装在 bbox 字段中，以便前端能精确还原多行高亮
        storage_bbox = {
            'union': union_bbox,   # 用于索引或简单显示
            'rects': normalized_rects # 用于精确渲染
        }

        # 6. 持久化存储
        highlight_id = current_app.storage_service.add_highlight(
            file_hash=file_hash,
            user_id=g.user_id,
            page_number=data['page'],
            highlighted_text=data.get('text', '[Image/Area]'),
            bbox=storage_bbox, # 存入 JSON 对象
            color=data.get('color', '#FFFF00'),
            comment=data.get('comment', '')
        )

        return jsonify({
            'success': True,
            'id': highlight_id,
            'rects': normalized_rects, # 返回相对坐标供前端立即更新
            'message': 'Highlight created'
        })

    except Exception as e:
        current_app.logger.error(f"Error creating highlight: {e}")
        return jsonify({'error': str(e)}), 500

@highlight_bp.route('/<pdf_id>', methods=['GET'])
def get_highlights(pdf_id):
    """
    获取某 PDF 的所有高亮
    返回的数据包含相对坐标 (0.0 - 1.0)，前端需乘以当前 Canvas 尺寸进行渲染
    """
    try:
        file_hash = get_file_hash(pdf_id)
        if not file_hash:
            return jsonify({'error': 'PDF file not found'}), 404

        # 可选：按页筛选
        page = request.args.get('page', type=int)

        # 从数据库获取
        highlights = current_app.storage_service.get_highlights(
            file_hash=file_hash,
            page_number=page
        )
        
        return jsonify(highlights)

    except Exception as e:
        current_app.logger.error(f"Error fetching highlights: {e}")
        return jsonify({'error': str(e)}), 500

@highlight_bp.route('/<int:highlight_id>', methods=['DELETE'])
def delete_highlight(highlight_id):
    """删除高亮"""
    try:
        current_app.storage_service.delete_highlight(highlight_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@highlight_bp.route('/<int:highlight_id>', methods=['PUT'])
def update_highlight(highlight_id):
    """更新高亮 (颜色或注释)"""
    data = request.get_json()
    try:
        current_app.storage_service.update_highlight(
            highlight_id=highlight_id,
            color=data.get('color'),
            comment=data.get('comment')
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500