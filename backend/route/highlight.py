"""
高亮路由：保存/获取/删除/更新高亮
"""
from flask import Blueprint, request, jsonify, current_app, g
from core.security import jwt_required
from route.utils import HighlightLogic

# 定义蓝图
highlight_bp = Blueprint('highlight', __name__, url_prefix='/api/highlight')


# ==================== 路由接口 ====================

@highlight_bp.route('', methods=['POST'])
@jwt_required()
def create_highlight():
    """
    创建高亮

    Request Body:
    {
        "pdfId": "file_hash...",
        "page": 1,
        "rects": [{"x": 100, "y": 100, "width": 50, "height": 20}],
        "pageWidth": 800,
        "pageHeight": 1200,
        "text": "选中的文本内容",
        "color": "#FFFF00"
    }
    """
    data = request.get_json()

    # 1. 参数校验
    required_fields = ['pdfId', 'page', 'rects', 'pageWidth', 'pageHeight', 'text', 'color']
    if not all(k in data for k in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    pdf_id = data['pdfId']   # pdf_id == file_hash

    # 2. 坐标归一化
    normalized_rects = HighlightLogic.normalize_coordinates(
        data['rects'],
        data['pageWidth'],
        data['pageHeight']
    )

    # 3. 持久化
    note_svc = g.note_service
    highlight_id = note_svc.add_highlight(
        user_id=g.user_id,
        file_hash=pdf_id,
        page_number=data['page'],
        rects=normalized_rects,
        selected_text=data.get('text', ''),
        color=data.get('color', '#FFFF00')
    )

    if highlight_id is None:
        return jsonify({'error': 'Paper not in user library'}), 404

    return jsonify({
        'success': True,
        'id': highlight_id,
        'rects': normalized_rects,
        'message': 'Highlight created'
    })


@highlight_bp.route('', methods=['GET'])
@jwt_required()
def get_highlights():
    """
    获取某 PDF 的所有高亮
    返回归一化坐标 (0.0 - 1.0), 前端需乘以当前 Canvas 尺寸渲染

    Query Params:
        pdfId: str (必填, PDF 文件 Hash)
        page:  int (可选, 按页筛选)
    """
    pdf_id = request.args.get('pdfId')
    if not pdf_id:
        return jsonify({'error': 'Missing required query parameter: pdfId'}), 400

    page = request.args.get('page', type=int)

    note_svc = g.note_service
    highlights = note_svc.get_highlights(
        user_id=g.user_id,
        file_hash=pdf_id,
        page_number=page
    )

    return jsonify({
        'success': True,
        'highlights': highlights,
        'total': len(highlights)
    })


@highlight_bp.route('/<int:highlight_id>', methods=['DELETE'])
@jwt_required()
def delete_highlight(highlight_id):
    """删除高亮"""
    note_svc = g.note_service
    note_svc.delete_highlight(highlight_id)
    return jsonify({'success': True})


@highlight_bp.route('/<int:highlight_id>', methods=['PUT'])
@jwt_required()
def update_highlight(highlight_id):
    """更新高亮 (颜色)"""
    data = request.get_json()
    note_svc = g.note_service
    note_svc.update_highlight(
        highlight_id=highlight_id,
        color=data.get('color')
    )
    return jsonify({'success': True})