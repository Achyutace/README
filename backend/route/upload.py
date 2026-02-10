"""
上传论文 & 任务状态查询

上传接口:
    POST /api/pdf/upload
    流程: 计算 Hash → 查重(秒传) → 存磁盘 → COS → 写 DB(pending) → 派发 Celery → 返回 task_id + pdfid

任务状态轮询接口:
    GET /api/pdf/<pdf_id>/status?from_page=1
    前端每 2 秒调用一次，获取进度 + 已解析段落(分页增量)

状态定义: pending | processing | completed | failed
"""
import hashlib
from flask import Blueprint, request, jsonify, current_app, g
from services.paper_service import PdfService

# 定义蓝图
upload_bp = Blueprint('upload', __name__, url_prefix='/api/pdf')


def _calculate_stream_hash(stream) -> str:
    """计算文件流的 SHA256 Hash"""
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: stream.read(8192), b""):
        sha256.update(chunk)
    stream.seek(0)
    return sha256.hexdigest()


# ==========================================
# 上传接口
# ==========================================

@upload_bp.route('/upload', methods=['POST'])
def upload_pdf():
    """
    上传 PDF 文件接口 
    1. 接收文件流 + 基础校验
    2. 计算 SHA256 Hash (作为唯一 ID)
    3. 调用 PdfService.upload_and_dispatch:
       - Hash 查重 (秒传)
       - 保存到磁盘 + COS
       - 写入 DB (status=pending)
       - 派发 Celery 异步任务
    4. 立即返回 {pdf_id, task_id, status}

    前端收到 status="processing" 后，每 2 秒轮询 GET /api/pdf/<pdf_id>/status
    """
    # 1. 基础校验
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    try:
        pdf_service: PdfService = g.pdf_service
        user_id = g.user_id  # uuid.UUID, 已在 before_request 中解析并确保存在于 DB

        # 2. 计算文件 Hash
        file_hash = _calculate_stream_hash(file.stream)
        file.stream.seek(0)  

        # 3. 上传 + 派发异步任务
        result = pdf_service.upload_and_dispatch(
            file=file,
            file_hash=file_hash,
            user_id=user_id,      # uuid.UUID 类型
            filename=file.filename,
        )

        # 4. 立即返回
        response_data = {
            'pdfId': result['pdf_id'],
            'taskId': result['task_id'],
            'status': result['status'],       # "processing" | "completed"
            'pageCount': result['pageCount'],
            'filename': result['filename'],
            'userId': str(user_id),        
            'fileHash': file_hash,
            'isNewUpload': not result.get('exists', False),
        }

        current_app.logger.info(
            f"[Upload] pdf_id={result['pdf_id']}, "
            f"task_id={result['task_id']}, "
            f"status={result['status']}, "
            f"user={user_id}"
        )
        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 任务状态轮询接口 ======================

@upload_bp.route('/<pdf_id>/status', methods=['GET'])
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

    try:
        pdf_service: PdfService = g.pdf_service
        result = pdf_service.get_process_status(pdf_id, from_page=from_page)
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Status query error for {pdf_id}: {e}")
        return jsonify({'error': str(e)}), 500


# ================== pdf信息获取接口 ========================

@upload_bp.route('/<pdf_id>/info', methods=['GET'])
def get_pdf_info(pdf_id):
    """获取 PDF 元数据"""
    try:
        info = g.pdf_service.get_info(pdf_id)
        return jsonify(info)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@upload_bp.route('/<pdf_id>/text', methods=['GET'])
def get_pdf_text(pdf_id):
    """获取 PDF 文本"""
    page = request.args.get('page', type=int)
    try:
        result = g.pdf_service.extract_text(pdf_id, page)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/<pdf_id>/paragraphs', methods=['GET'])
def get_pdf_paragraphs(pdf_id):
    """获取 PDF 已解析的段落 (从 DB 读取)"""
    try:
        paragraphs = g.pdf_service.parse_paragraphs(pdf_id)
        return jsonify({'paragraphs': paragraphs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500