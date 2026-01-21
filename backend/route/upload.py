"""
上传论文: PDF存在磁盘；数据库中异步加入PDF元数据和PDF段落解析文本数据；触发PDF的RAG索引异步流程
"""
import os
import threading
from flask import Blueprint, request, jsonify, current_app, g
from models.database import Database
from services.pdf_service import PdfService  # 导入类以便在线程中实例化

# 定义蓝图
upload_bp = Blueprint('upload', __name__, url_prefix='/api/pdf')

def async_process_pdf(app, pdf_id, file_hash, user_id, upload_folder, cache_folder, 
                      paragraphs, filepath, filename, page_count):
    """
    后台异步任务：
    1. 持久化元数据和段落到数据库 (StorageService)
    2. 执行 RAG 索引 (RAGService)
    
    Args:
        app: Flask 应用实例 (用于获取上下文)
        pdf_id: PDF ID (通常等于 file_hash)
        file_hash: 文件内容 Hash
        user_id: 用户 ID
        upload_folder: 用户上传目录
        cache_folder: 用户缓存目录
        paragraphs: 已解析的段落列表
        filepath: PDF 文件路径
        filename: PDF 文件名
        page_count: PDF 页数
    """
    with app.app_context():
        try:
            current_app.logger.info(f"[Async] Starting background processing for {pdf_id}...")
            
            # 获取全局单例服务
            storage_service = current_app.storage_service
            rag_service = current_app.rag_service

            # ==========================================
            # 步骤 A: 存入数据库 (IO密集型)
            # ==========================================
            current_app.logger.info(f"[Async] Persisting data to database for {pdf_id}...")
            storage_service.persist_pdf_parsing(
                file_path=filepath,
                file_hash=file_hash,
                filename=filename, 
                page_count=page_count,
                paragraphs=paragraphs,
                user_id=user_id
            )
            
            # ==========================================
            # 步骤 B: RAG 索引 (AI计算密集型)
            # ==========================================
            # 检查是否已存在索引，避免重复计算 Embedding
            if not rag_service.check_exists(file_hash):
                current_app.logger.info(f"[Async] Starting RAG indexing for {pdf_id}...")
                index_result = rag_service.index_paper(
                    pdf_path=filepath,
                    paper_id=pdf_id,
                    user_id=user_id
                )
                
                if index_result['success']:
                    current_app.logger.info(f"[Async] All tasks completed. RAG Chunks: {index_result['chunks_created']}")
                else:
                    current_app.logger.error(f"[Async] RAG indexing failed: {index_result['message']}")
            else:
                current_app.logger.info(f"[Async] RAG index already exists for {pdf_id}. Skipped.")
                
        except Exception as e:
            current_app.logger.error(f"[Async] Background processing exception for {pdf_id}: {str(e)}")

@upload_bp.route('/upload', methods=['POST'])
def upload_pdf():
    """
    上传 PDF 文件接口
    
    流程：
    1. 接收文件流
    2. 计算 Hash (作为唯一 ID)
    3. 保存到磁盘 (PdfService 处理秒传逻辑)
    4. 解析段落 (同步执行，返回段落ID给前端)
    5. 启动异步线程 (存库 -> RAG)
    6. 立即返回结果（包含段落数据）
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
        # 获取当前请求上下文中的服务
        # g.pdf_service 在 app.py 中初始化
        pdf_service = g.pdf_service
        user_id = g.user_id
        
        # 记录路径以便传给异步线程 (线程中无法访问 g)
        upload_folder = pdf_service.upload_folder
        cache_folder = pdf_service.cache_folder
        
        # 2. 计算文件 Hash
        # 读取流计算 hash，作为文件的唯一标识 (pdf_id)
        file_hash = Database.calculate_stream_hash(file.stream)
        file.stream.seek(0) # 重置指针，否则保存时文件为空
        
        # 3. 保存到磁盘
        # save_and_process 内部会检查文件是否存在 (秒传)
        # 返回: { id, filename, pageCount, exists }
        result = pdf_service.save_and_process(file, file_hash)
        pdf_id = result['id'] # 这里 pdf_id == file_hash
        
        # 4. 同步解析段落 
        current_app.logger.info(f"[Sync] Parsing paragraphs for {pdf_id}...")
        paragraphs = pdf_service.parse_paragraphs(pdf_id)
        
        # 获取文件路径和元数据
        filepath = pdf_service.get_filepath(pdf_id)
        filename = result['filename']
        page_count = result['pageCount']
        
        # 5. 启动异步任务 (数据库持久化 + RAG 索引)
        # 即使是秒传 (result['exists'] is True)，我们也触发异步任务
        # 因为数据库记录或 RAG 索引可能被删除了，需要重新检查/补全
        
        # 获取真实的 app 实例 (current_app 是代理，不能直接传给线程)
        app = current_app._get_current_object()
        
        thread = threading.Thread(
            target=async_process_pdf,
            args=(app, pdf_id, file_hash, user_id, upload_folder, cache_folder,
                  paragraphs, filepath, filename, page_count)
        )
        thread.start()

        # 6. 立即返回
        response_data = {
            'id': pdf_id,
            'filename': result['filename'],
            'pageCount': result['pageCount'],
            'userId': user_id,
            'fileHash': file_hash,
            'paragraphs': paragraphs,  # 新增：返回段落数据
            'status': 'processing', # 告知前端后台正在处理
            'isNewUpload': not result.get('exists', False)
        }
        
        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

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