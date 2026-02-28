"""
文献管理相关路由 (Library Management)

负责处理用户书架上的文献元数据、标签以及管理操作：
- GET /api/library/ : 获取文献列表
- GET /api/library/<pdf_id>/info : 获取单篇文献元数据
- POST /api/library/<pdf_id>/tags : 添加标签
- DELETE /api/library/<pdf_id>/tags/<tag> : 移除标签
- GET /api/library/<pdf_id>/source : 获取 PDF 源文件流 (支持预览)
- DELETE /api/library/<pdf_id> : 从书架移除文献 (软删除)
"""
from flask import Blueprint, request, jsonify, g, current_app, send_file
from core.security import jwt_required
from core.exceptions import NotFoundError
from core.logging import get_logger

logger = get_logger(__name__)

# 定义蓝图，前缀为 /api/library
library_bp = Blueprint('library', __name__, url_prefix='/api/library')

@library_bp.route('/', methods=['GET'])
@jwt_required()
def list_user_papers():
    """获取当前用户的文献库列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 50, type=int)
    group = request.args.get('group')
    keyword = request.args.get('keyword')

    library_service = current_app.library_service
    result = library_service.get_user_papers(
        user_id=g.user_id,
        page=page,
        page_size=page_size,
        group_filter=group,
        keyword=keyword
    )
    return jsonify(result)

@library_bp.route('/<pdf_id>/info', methods=['GET'])
@jwt_required()
def get_pdf_info(pdf_id):
    """获取 PDF 元数据"""
    try:
        info = g.pdf_service.get_info(pdf_id)
        return jsonify(info)
    except FileNotFoundError:
        raise NotFoundError('PDF not found')

@library_bp.route('/<pdf_id>/tags', methods=['POST'])
@jwt_required()
def add_pdf_tag(pdf_id):
    """为文档添加标签"""
    data = request.get_json() or {}
    tag = data.get('tag')
    if not tag:
        return jsonify({'error': 'Tag is required'}), 400

    library_service = current_app.library_service
    success = library_service.set_paper_group(
        pdf_id=pdf_id,
        user_id=g.user_id,
        group_name=tag
    )
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to add tag or tag already exists'}), 500

@library_bp.route('/<pdf_id>/tags/<tag>', methods=['DELETE'])
@jwt_required()
def remove_pdf_tag(pdf_id, tag):
    """移除文档的标签"""
    library_service = current_app.library_service
    success = library_service.remove_paper_group(
        pdf_id=pdf_id,
        user_id=g.user_id,
        group_name=tag
    )
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to remove tag or tag not found'}), 500

@library_bp.route('/<pdf_id>/source', methods=['GET'])
@jwt_required()
def get_pdf_source(pdf_id):
    """
    获取 PDF 源文件流 (支持浏览器直接预览/渲染)
    """
    try:
        file_obj = g.pdf_service.get_file_obj(pdf_id)
        return send_file(
            file_obj,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f"{pdf_id}.pdf"
        )
    except FileNotFoundError:
        raise NotFoundError('PDF file not found')


@library_bp.route('/<pdf_id>', methods=['DELETE'])
@jwt_required()
def delete_pdf(pdf_id):
    """从书架移除文献 (解除关联)"""
    library_service = current_app.library_service
    success = library_service.delete_pdf(pdf_id, g.user_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to delete literature'}), 500
