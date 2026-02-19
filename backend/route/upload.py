"""
上传论文 & 任务状态查询 & PDF 信息获取

上传接口:
    POST /api/pdf/upload
    流程: 接收文件 → PdfService.ingest_file (Hash查重/存盘/COS/Celery)
          → LibraryService.bind_paper (绑定到用户书架)
          → 返回 pdf_id + task_id

任务状态轮询接口:
    GET /api/pdf/<pdf_id>/status?from_page=1

状态定义: pending | processing | completed | failed
"""
from flask import Blueprint, request, jsonify, g, send_file
from core.security import jwt_required
from core.exceptions import NotFoundError
from core.logging import get_logger

logger = get_logger(__name__)

# 定义蓝图
upload_bp = Blueprint('upload', __name__, url_prefix='/api/pdf')


# ==========================================
# 上传接口
# ==========================================

@upload_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_pdf():
    """
    上传 PDF 文件接口
    1. 基础校验
    2. 调用 PdfService.ingest_file (内部: Hash查重 → 存盘 → COS → 写DB → Celery)
    3. 调用 LibraryService.bind_paper (绑定到用户书架)
    4. 返回 {pdfId, taskId, status}
    """
    # 1. 基础校验
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    pdf_service = g.pdf_service
    user_id = g.user_id

    # 2. 摄入文件 (Hash + 存盘 + COS + DB + Celery)
    result = pdf_service.ingest_file(
        file_obj=file,
        filename=file.filename,
        user_id=user_id
    )

    pdf_id = result['pdf_id']

    # 3. 绑定到用户书架
    library_service = current_app.library_service
    library_service.bind_paper(
        user_id=user_id,
        pdf_id=pdf_id,
        title=file.filename
    )

    # 4. 立即返回
    response_data = {
        'pdfId': pdf_id,
        'taskId': result.get('task_id'),
        'status': result['status'],
        'pageCount': result.get('pageCount', 0),
        'filename': file.filename,
        'isNewUpload': result.get('is_new', True),
    }

    logger.info(
        f"[Upload] pdf_id={pdf_id}, "
        f"task_id={result.get('task_id')}, "
        f"status={result['status']}, "
        f"user={g.user_id_str}"
    )
    return jsonify(response_data)


# ==================== 任务状态轮询接口 ======================

@upload_bp.route('/<pdf_id>/status', methods=['GET'])
@jwt_required()
def get_task_status(pdf_id):
    """
    获取 PDF 处理进度

    Query Params:
        from_page: int (default=1) — 从第几页开始返回段落

    Returns:
        {
            "status": "pending" | "processing" | "completed" | "failed",
            "currentPage": 5,
            "totalPages": 20,
            "error": null,
            "paragraphs": [...]  // from_page ~ currentPage 的段落
        }
    """
    from_page = request.args.get('from_page', 1, type=int)

    pdf_service = g.pdf_service
    result = pdf_service.get_process_status(pdf_id, from_page=from_page)
    return jsonify(result)


# ================== PDF 信息获取接口 ========================

@upload_bp.route('/<pdf_id>/info', methods=['GET'])
@jwt_required()
def get_pdf_info(pdf_id):
    """获取 PDF 元数据"""
    try:
        info = g.pdf_service.get_info(pdf_id)
        return jsonify(info)
    except FileNotFoundError:
        raise NotFoundError('PDF not found')


@upload_bp.route('/<pdf_id>/paragraphs', methods=['GET'])
@jwt_required()
def get_pdf_paragraphs(pdf_id):
    """获取 PDF 已解析的段落 (从 DB 读取)"""
    page = request.args.get('page', type=int)
    result = g.pdf_service.get_paragraph(pdf_id, pagenumber=page)
    return jsonify({'paragraphs': result})


@upload_bp.route('/<pdf_id>/source', methods=['GET'])
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