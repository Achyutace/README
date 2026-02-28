"""
PDF 服务  —— 异步处理
1. 处理pdf上传：注册文件库，触发异步段落图片解析和向量化
pdf查询：
    1. 获取pdf的段落数据(页面+段落)
    2. 获取pdf元数据
    3. 获取pdf图片(页面+编号)
    4. 获取pdf源文件
    5. 获取/添加pdf翻译(指定页面指定段落)

"""
import os
import uuid
import logging
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import shutil

from core.database import db
from repository.sql_repo import SQLRepository
from repository.object_repo import object_storage
from utils import pdf_engine
from utils.hashing import calculate_stream_hash

logger = logging.getLogger(__name__)

class PdfService:
    def __init__(self, upload_folder: str):
        """
        初始化 PDF 服务
        Args:
            upload_folder: PDF 文件本地缓存/上传目录
        """
        self.upload_folder = upload_folder
        self.pdf_registry: dict[str, dict] = {}
        
        # 确保上传目录存在
        os.makedirs(self.upload_folder, exist_ok=True)

    # ===================== 内部辅助 =====================

    def _find_filepath_by_id(self, pdf_id: str) -> str:
        """
        根据 ID (Hash) 查找本地文件路径。
        策略: 内存注册表 -> 本地磁盘 -> COS 下载
        """
        # 1. 查内存注册表
        if pdf_id in self.pdf_registry:
            path = self.pdf_registry[pdf_id]['filepath']
            if os.path.exists(path):
                return path

        # 2. 查本地磁盘 (uploads/<pdf_id>)
        candidate = os.path.join(self.upload_folder, pdf_id)
        if os.path.exists(candidate):
            return candidate

        # 3. 如果启用 COS，尝试下载到本地
        if object_storage.config.enabled:
            try:
                # COS Key 是 pdffile/{pdf_id}
                if object_storage.download_file(f"pdffile/{pdf_id}", candidate):
                    logger.info(f"Downloaded {pdf_id} from COS to {candidate}")
                    return candidate
            except Exception as e:
                logger.warning(f"Failed to download {pdf_id} from COS: {e}")

        return None

    def get_filepath(self, pdf_id: str) -> str:
        """获取 PDF 的本地绝对路径，如果不存在则远程获取"""
        filepath = self._find_filepath_by_id(pdf_id)
        if filepath:
            return filepath
        raise FileNotFoundError(f"PDF file not found locally or in storage: {pdf_id}")

    from tasks.dispatcher import dispatch_pdf_task, check_and_restart_stuck_task

    def ingest_file(self, file_obj, filename: str, user_id: uuid.UUID = None) -> dict:
        """
        摄入文件：负责查重、存储、更新GlobalFile、触发Celery。
        
        Returns:
            dict: { 
                "pdf_id": str, 
                "task_id": str, 
                "status": str, 
                "pageCount": int, 
                "is_new": bool 
            }
        """
        from tasks.pdf_tasks import process_pdf
        
        STUCK_TIMEOUT_MINUTES = 120  
        
        # 1. 计算文件基础属性
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        file_hash = calculate_stream_hash(file_obj)
        
        pdf_id = file_hash
        safe_filename = secure_filename(filename)
        
        # 2. 检查 GlobalFile 状态 (查重)
        repo = SQLRepository(db.session)
        try:
            gf = repo.get_global_file(pdf_id)
            if gf:
                # 判定当前任务状态
                is_completed = gf.process_status == "completed"
                
                # 检测是否卡死并重启
                restarted = check_and_restart_stuck_task(gf, pdf_id, self.upload_folder, STUCK_TIMEOUT_MINUTES, user_id)
                
                # 任务已完成，或者正在处理且未卡死：直接返回
                # 如果重启了，状态会变成 pending，也应当直接返回
                if is_completed or restarted or (gf.process_status in ("pending", "processing")):
                    logger.info(f"[Ingest] File {pdf_id} exists (status={gf.process_status}). Instant return.")
                    return {
                        "pdf_id": pdf_id,
                        "task_id": gf.task_id,
                        "status": gf.process_status,
                        "pageCount": gf.total_pages or 0,
                        "is_new": False
                    }
                
                logger.info(f"[Ingest] File {pdf_id} status={gf.process_status} (failed), re-dispatching...")
        except Exception as e:
            db.session.rollback()
            raise

        # 3. 物理保存到本地
        filepath = os.path.join(self.upload_folder, pdf_id)
        if not os.path.exists(filepath):
            try:
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                with open(filepath, "wb") as f:
                    shutil.copyfileobj(file_obj, f)
                logger.info(f"[Ingest] Saved file to {filepath}")
            except Exception as e:
                logger.error(f"[Ingest] Failed to save local file {filepath}: {e}")
                raise e
        
        # Get file size for DB record
        file_size = os.path.getsize(filepath)
        
        # 4. 上传到 COS
        if object_storage.config.enabled:
            try:
                # 注意：这里需要重新打开文件流或使用 bytes
                with open(filepath, 'rb') as f:
                    object_storage.upload_file(f, f"pdffile/{pdf_id}")
            except Exception as e:
                logger.error(f"[Ingest] COS upload failed (continuing): {e}")

        # 5. 获取页数和元数据
        page_count = 0
        metadata = {}
        dimensions = []
        try:
            pdf_info = pdf_engine.get_pdf_info(pdf_id, filepath)
            page_count = pdf_info.get('pageCount', 0)
            metadata = pdf_info.get('metadata', {})
            dimensions = pdf_info.get('dimensions', [])
        except Exception:
            pass
            
        # 6. 更新 GlobalFile (Pending) 或 创建
        repo = SQLRepository(db.session)
        try:
            gf = repo.get_global_file(pdf_id)
            if gf:
                # 只更新需要刷新的信息
                gf.total_pages = page_count
                gf.metadata_info = metadata
                gf.dimensions = dimensions
            else:
                # 创建新任务
                gf = repo.create_global_file(
                    file_hash=pdf_id,
                    file_path=pdf_id,
                    file_size=file_size,
                    total_pages=page_count,
                    metadata=metadata,
                    dimensions=dimensions,
                )
            
            # 统一启动异步任务
            new_task_id = dispatch_pdf_task(gf, pdf_id, self.upload_folder, safe_filename, page_count, user_id, is_restart=False)
        except Exception as e:
            raise e

        # 更新内存缓存
        self.pdf_registry[pdf_id] = {
            'id': pdf_id,
            'filepath': filepath
        }
        return {
            "pdf_id": pdf_id,
            "task_id": new_task_id,
            "status": "pending",
            "pageCount": page_count,
            "is_new": True
        }
    # ==================== 进度查询 ======================

    def get_process_status(self, pdf_id: str, from_page: int = 1) -> dict:
        """
        获取 PDF 处理进度及已解析段落 (分页)。

        Args:
            pdf_id:    文件 Hash
            from_page: 从第几页开始返回段落 (1-based)，用于增量拉取

        Returns:
            {
                "status": "pending" | "processing" | "completed" | "failed",
                "currentPage": 5,
                "totalPages": 20,
                "error": null,
                "paragraphs": [...],  // from_page 到 currentPage 的段落
            }
        """
        repo = SQLRepository(db.session)
        try:
            # 获取 GlobalFile 自身以检测卡死情况
            gf = repo.get_global_file(pdf_id)
            if not gf:
                return {"status": "not_found", "error": "PDF not found"}

            # 检测并重启卡死的任务 (阈值 15 分钟)
            check_and_restart_stuck_task(gf, pdf_id, self.upload_folder, timeout_minutes=15)

            # 读取最新状态
            status = gf.process_status
            current_page = gf.current_page or 0
            total_pages = gf.total_pages or 0
            error_msg = gf.error_message

            paragraphs = []
            if current_page > 0 and from_page <= current_page:
                db_paras = repo.get_paragraphs_range(pdf_id, from_page, current_page)
                paragraphs = [self._format_paragraph(p, pdf_id) for p in db_paras]

            return {
                "status": status,
                "currentPage": current_page,
                "totalPages": total_pages,
                "error": error_msg,
                "paragraphs": paragraphs,
            }

        except Exception as e:
            logger.error(f"Failed to get process status for {pdf_id}: {e}")
            return {"status": "error", "error": str(e)}

    def _format_paragraph(self, p, pdf_id: str) -> dict:
        """格式化段落数据"""
        para_id = pdf_engine.make_paragraph_id(pdf_id, p.page_number, p.paragraph_index)

        # 将数据库中 [x, y, w, h] 格式转换为前端期望的具名字段对象
        # 数据库列: bbox JSONB comment="[x, y, w, h] 归一化坐标"
        # 前端类型: { x0, y0, x1, y1, width, height }
        bbox = None
        if p.bbox and isinstance(p.bbox, list) and len(p.bbox) >= 4:
            x, y, w, h = p.bbox[0], p.bbox[1], p.bbox[2], p.bbox[3]
            bbox = {
                "x0": x,
                "y0": y,
                "x1": x + w,
                "y1": y + h,
                "width": w,
                "height": h,
            }

        return {
            "id": para_id,
            "page": p.page_number,
            "bbox": bbox,
            "content": p.original_text,
            "wordCount": len(p.original_text.split()) if p.original_text else 0,
            "translation": p.translation_text,
        }


    # ================= 读取接口 =========================

    def get_info(self, pdf_id: str) -> dict:
        """
        获取 PDF 元数据。
        """
        # 1. 尝试从数据库获取
        repo = SQLRepository(db.session)
        try:
            gf = repo.get_global_file(pdf_id)
            if gf:
                return {
                    'id': gf.file_hash,
                    'pageCount': gf.total_pages,
                    'metadata': gf.metadata_info or {},
                    'dimensions': gf.dimensions or []
                }
        except Exception as e:
            logger.warning(f"DB lookup failed for {pdf_id}: {e}")

        # 2. 数据库没有或获取失败，回退到文件解析
        try:
            filepath = self.get_filepath(pdf_id) 
            
            # 3. 解析文件获取元数据
            return pdf_engine.get_pdf_info(pdf_id, filepath)
        except Exception as e:
            logger.error(f"Failed to get info for {pdf_id}: {e}")
            raise e

    def get_paragraph(self, pdf_id: str, pagenumber: int = None, paraid: int = None) -> list[dict]:
        """
        从数据库获取段落文本信息
        """
        paragraphs = []
        repo = SQLRepository(db.session)
        try:
            db_paras = repo.get_paragraphs(pdf_id, pagenumber, paraid)
            if db_paras:
                for p in db_paras:
                    paragraphs.append(self._format_paragraph(p, pdf_id))
        except Exception as e:
            logger.warning(f"DB lookup paragraphs failed for {pdf_id}: {e}")

        return paragraphs


    def get_file_obj(self, pdf_id: str):
        """
        根据 pdf_id 获取文件对象 (二进制流)
        Returns:
            file_object: 打开的文件对象 (rb模式)，调用者需负责关闭
        """
        filepath = self.get_filepath(pdf_id)
        return open(filepath, 'rb')

