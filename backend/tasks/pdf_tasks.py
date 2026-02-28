"""
PDF 异步处理任务 (MinerU-first)

解析流程:
    1. MinerU 云端解析: 上传 PDF → 获取 content_list_v2.json → 结构化段落/图片/表格/公式
    2. 解析结果写入 DB (按页写入，前端可轮询进度)
    3. RAG 向量化

回退:
    如果 MinerU 未配置或失败，降级使用 PyMuPDF 逐页解析段落 + 图片元数据。

状态机:
        pending → processing → completed / failed
"""
import os
import logging
import uuid
from pathlib import Path
from celery_app import celery

from core.database import db
from repository.sql_repo import SQLRepository
from repository.object_repo import object_storage
from utils import pdf_engine

logger = logging.getLogger(__name__)

# 状态常量 
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def _resolve_filepath(file_hash: str, upload_folder: str) -> str:
    """
    解析 PDF 文件路径。
    优先读本地 upload_folder，其次从 COS 下载。
    """
    # 1. 本地磁盘
    candidate = os.path.join(upload_folder, file_hash)
    if os.path.exists(candidate):
        return candidate

    # 2. COS 下载
    if object_storage.config.enabled:
        # 使用临时文件防止并发写冲突
        tmp_candidate = f"{candidate}.tmp.{uuid.uuid4().hex}"
        try:
            if object_storage.download_file(f"pdffile/{file_hash}", tmp_candidate):
                # 原子替换 
                os.replace(tmp_candidate, candidate)
                logger.info(f"Downloaded {file_hash} from COS to {candidate}")
                return candidate
        except Exception as e:
            logger.warning(f"Failed to download {file_hash} from COS: {e}")
        finally:
            # 清理残留临时文件
            if os.path.exists(tmp_candidate):
                try:
                    os.remove(tmp_candidate)
                except OSError:
                    pass

    raise FileNotFoundError(f"PDF file not found: {file_hash}")

# =================== Celery Task =======================

class _SyncTaskStub:
    """同步执行时模拟 Celery Task 的 self 对象。"""
    class request:
        id = "sync-task"
    @staticmethod
    def update_state(**kwargs):
        pass
    @staticmethod
    def retry(exc=None):
        if exc:
            raise exc
        raise RuntimeError("Task failed")


def process_pdf_sync(file_hash: str, upload_folder: str, filename: str, page_count: int, user_id=None):
    """
    同步版本的 PDF 处理。当 Redis/Celery 不可用时使用。
    """
    stub = _SyncTaskStub()
    stub.request.id = f"sync-{file_hash[:8]}"
    return _process_pdf_impl(stub, file_hash, upload_folder, filename, page_count, user_id)


@celery.task(bind=True, name="tasks.pdf_tasks.process_pdf", max_retries=3, default_retry_delay=60)
def process_pdf(self, file_hash: str, upload_folder: str, filename: str, page_count: int, user_id: uuid.UUID = None):
    """Celery 异步版本的 PDF 处理。"""
    return _process_pdf_impl(self, file_hash, upload_folder, filename, page_count, user_id)


def _process_pdf_impl(task_self, file_hash: str, upload_folder: str, filename: str, page_count: int, user_id=None):
    """
    PDF 全流程异步处理任务 (MinerU-first)。

    优先使用 MinerU 云端 API 提取全部结构化内容（段落/图片/表格/公式），
    如果 MinerU 未配置或失败，则降级使用 PyMuPDF 逐页解析。

    Args:
        file_hash:     pdf_id
        upload_folder: 用户上传目录绝对路径
        filename:      原始文件名
        page_count:    页数
        user_id:       用户 ID (UUID)
    """
    task_id = task_self.request.id
    logger.info(f"[Task {task_id}] Start processing PDF {filename} ({file_hash}), pages={page_count}, user={user_id}")

    from celery_app import get_worker_app
    with get_worker_app().app_context():
        try:
            filepath = _resolve_filepath(file_hash, upload_folder)
            _update_status(file_hash, STATUS_PROCESSING, task_id=task_id)

            mineru_success = False

            # ================== 尝试 MinerU 全量解析 ==================
            from services.mineru_service import MinerUService
            if MinerUService.is_configured():
                task_self.update_state(state="PROGRESS", meta={
                    "current_page": 0,
                    "total_pages": page_count,
                    "phase": "mineru_parsing",
                })

                try:
                    mineru_success = _run_mineru_full_parse(
                        file_hash, filepath, upload_folder, page_count, task_id, task_self
                    )
                except Exception as e:
                    logger.warning(f"[Task {task_id}] MinerU full parse failed, falling back to PyMuPDF: {e}")
                    mineru_success = False

            # ================== PyMuPDF 回退 ==================
            if not mineru_success:
                logger.info(f"[Task {task_id}] Using PyMuPDF fallback for parsing")
                _run_pymupdf_fallback(file_hash, filepath, page_count, task_id, task_self)

            # ================== RAG 向量化 ==================
            task_self.update_state(state="PROGRESS", meta={
                "current_page": page_count,
                "total_pages": page_count,
                "phase": "vectorizing",
            })

            try:
                target_user_uuid = None
                if user_id:
                    target_user_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
                else:
                    logger.warning(f"[Task {task_id}] Missing user_id for PDF processing.")

                if target_user_uuid:
                    _run_rag_indexing_from_db(file_hash, task_id, target_user_uuid)
                else:
                    logger.error(f"[Task {task_id}] Skipped RAG indexing due to invalid/missing user_id.")
            except Exception as e:
                logger.error(f"[Task {task_id}] RAG indexing failed: {e}")

            # ====================== 完成 ======================
            _update_status(file_hash, STATUS_COMPLETED)
            logger.info(f"[Task {task_id}] PDF {file_hash} processing completed")
            return {"status": STATUS_COMPLETED, "file_hash": file_hash, "total_pages": page_count}

        except FileNotFoundError as e:
            _update_status(file_hash, STATUS_FAILED, error=str(e))
            raise

        except Exception as exc:
            _update_status(file_hash, STATUS_FAILED, error=str(exc))
            logger.error(f"[Task {task_id}] Unexpected error: {exc}")
            raise task_self.retry(exc=exc)


# ================== 辅助函数 ========================

def _update_status(file_hash: str, status: str, task_id: str = None, error: str = None):
    """更新 GlobalFile 的处理状态"""
    from celery_app import get_worker_app
    with get_worker_app().app_context():
        repo = SQLRepository(db.session)
        try:
            gf = repo.get_global_file(file_hash)
            if gf:
                gf.process_status = status
                if task_id:
                    gf.task_id = task_id
                if error:
                    gf.error_message = error
                elif status != STATUS_FAILED:
                    gf.error_message = None
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to update status for {file_hash}: {e}")
            db.session.rollback()


def _update_progress(file_hash: str, current_page: int):
    """更新当前已解析到的页码"""
    from celery_app import get_worker_app
    with get_worker_app().app_context():
        repo = SQLRepository(db.session)
        try:
            gf = repo.get_global_file(file_hash)
            if gf:
                gf.current_page = current_page
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to update progress for {file_hash}: {e}")
            db.session.rollback()


def _clear_old_parse_data(file_hash: str, task_id: str):
    """清除旧的解析数据（段落/图片/公式），防止重复解析时数据叠加。"""
    from model.db.doc_models import PdfParagraph, PdfImage, PdfFormula
    from sqlalchemy import delete

    try:
        db.session.execute(delete(PdfParagraph).where(PdfParagraph.file_hash == file_hash))
        db.session.execute(delete(PdfImage).where(PdfImage.file_hash == file_hash))
        db.session.execute(delete(PdfFormula).where(PdfFormula.file_hash == file_hash))
        db.session.commit()
        logger.info(f"[Task {task_id}] Cleared old parse data for {file_hash}")
    except Exception as e:
        logger.warning(f"[Task {task_id}] Failed to clear old parse data: {e}")
        db.session.rollback()


# ================== MinerU 全量解析 ========================

def _run_mineru_full_parse(
    file_hash: str,
    filepath: str,
    upload_folder: str,
    page_count: int,
    task_id: str,
    task_self,
) -> bool:
    """
    使用 MinerU 云端 API 进行全量 PDF 解析。
    解析 content_list_v2.json 获取段落/图片/表格/公式并写入数据库。

    Returns:
        True 表示成功，False 表示失败需回退。
    """
    from services.mineru_service import MinerUService

    svc = MinerUService()

    # MinerU 结果缓存目录
    cache_root = Path(upload_folder).parent / "cache" / "mineru"
    output_dir = cache_root / file_hash
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[Task {task_id}] Starting MinerU full parse for {file_hash}...")

    # 1. 上传 + 轮询 + 下载 + 解析 content_list_v2.json
    result = svc.extract_and_parse(filepath, file_hash, str(output_dir))

    paragraphs = result.get("paragraphs", [])
    images = result.get("images", [])
    tables = result.get("tables", [])
    formulas = result.get("formulas", [])
    actual_pages = result.get("page_count", page_count)

    logger.info(
        f"[Task {task_id}] MinerU parsed: {actual_pages} pages, "
        f"{len(paragraphs)} paragraphs, {len(images)} images, "
        f"{len(tables)} tables, {len(formulas)} formulas"
    )

    if not paragraphs and not images:
        logger.warning(f"[Task {task_id}] MinerU returned empty content, falling back.")
        return False

    # 2. 清除旧的解析数据
    _clear_old_parse_data(file_hash, task_id)

    # 3. content_list_v2.json 中 images/ 的实际根目录
    content_json = svc._find_content_json(Path(output_dir))
    content_root = content_json.parent if content_json else Path(output_dir)

    # 4. 按页逐批写入数据库（模拟进度更新，前端可轮询）
    pages_set = sorted(set(p["page"] for p in paragraphs))
    for page_num in range(1, actual_pages + 1):
        # 写入段落
        page_paras = [p for p in paragraphs if p["page"] == page_num]
        if page_paras:
            repo = SQLRepository(db.session)
            try:
                paras_to_save = [
                    {
                        "page_number": p["page"],
                        "paragraph_index": p["index"],
                        "original_text": p["content"],
                        "bbox": p["bbox"],
                    }
                    for p in page_paras
                ]
                repo.save_paragraphs(file_hash, paras_to_save)
            except Exception as e:
                logger.error(f"[Task {task_id}] Failed to save MinerU paragraphs page {page_num}: {e}")
                db.session.rollback()

        # 更新进度
        _update_progress(file_hash, page_num)
        task_self.update_state(state="PROGRESS", meta={
            "current_page": page_num,
            "total_pages": actual_pages,
            "phase": "mineru_parsing",
        })

    # 5. 写入图片
    if images:
        repo = SQLRepository(db.session)
        try:
            images_to_save = []
            for img in images:
                # image_path 存储: 相对于 content_root 的路径
                # 读取时需要 content_root / path 才能定位文件
                relative_path = img.get("path", "")
                images_to_save.append({
                    "page_number": img["page"],
                    "image_index": img["index"],
                    "bbox": img.get("bbox", []),
                    "caption": img.get("caption", ""),
                    "image_path": f"mineru/{file_hash}/{relative_path}" if relative_path else "",
                })
            repo.save_images(file_hash, images_to_save)
            logger.info(f"[Task {task_id}] Saved {len(images_to_save)} MinerU images to DB.")
        except Exception as e:
            logger.error(f"[Task {task_id}] Failed to save MinerU images to DB: {e}")
            db.session.rollback()

    # 6. 写入表格（作为图片类型存入 PdfImage，caption 带 [table] 前缀）
    if tables:
        repo = SQLRepository(db.session)
        try:
            tables_to_save = []
            for tbl in tables:
                relative_path = tbl.get("path", "")
                caption = tbl.get("caption", "")
                tables_to_save.append({
                    "page_number": tbl["page"],
                    "image_index": len(images) + tbl["index"],  # 避免与图片 index 冲突
                    "bbox": tbl.get("bbox", []),
                    "caption": f"[table] {caption}" if caption else "[table]",
                    "image_path": f"mineru/{file_hash}/{relative_path}" if relative_path else "",
                })
            repo.save_images(file_hash, tables_to_save)
            logger.info(f"[Task {task_id}] Saved {len(tables_to_save)} MinerU tables to DB.")
        except Exception as e:
            logger.error(f"[Task {task_id}] Failed to save MinerU tables to DB: {e}")
            db.session.rollback()

    # 7. 写入公式
    if formulas:
        repo = SQLRepository(db.session)
        try:
            formulas_to_save = [
                {
                    "page_number": f["page"],
                    "formula_index": f["index"],
                    "bbox": f.get("bbox", []),
                    "latex_content": f["latex"],
                }
                for f in formulas
            ]
            repo.save_formulas(file_hash, formulas_to_save)
            logger.info(f"[Task {task_id}] Saved {len(formulas_to_save)} MinerU formulas to DB.")
        except Exception as e:
            logger.error(f"[Task {task_id}] Failed to save MinerU formulas to DB: {e}")
            db.session.rollback()

    return True


# ================== PyMuPDF 回退解析 ========================

def _run_pymupdf_fallback(
    file_hash: str,
    filepath: str,
    page_count: int,
    task_id: str,
    task_self,
):
    """
    PyMuPDF 逐页解析段落 + 图片元数据（当 MinerU 不可用时使用）。
    """
    _clear_old_parse_data(file_hash, task_id)

    for page_num in range(1, page_count + 1):
        logger.info(f"[Task {task_id}] [PyMuPDF] Processing page {page_num}/{page_count}")

        # 解析段落
        paragraphs = pdf_engine.parse_paragraphs(filepath, file_hash, page_numbers=[page_num])
        if paragraphs:
            repo = SQLRepository(db.session)
            try:
                paras_to_save = [
                    {"page_number": p["page"], "paragraph_index": p["index"],
                     "original_text": p["content"], "bbox": p["bbox"]}
                    for p in paragraphs
                ]
                repo.save_paragraphs(file_hash, paras_to_save)
            except Exception as e:
                logger.error(f"[Task {task_id}] Failed to save paragraphs page {page_num}: {e}")
                db.session.rollback()

        # 解析图片元数据
        try:
            images_list = pdf_engine.get_images_list(filepath, file_hash, page_numbers=[page_num])
            if images_list:
                repo = SQLRepository(db.session)
                try:
                    images_to_save = [
                        {"page_number": img["page"], "image_index": img["index"],
                         "bbox": img["bbox"], "caption": ""}
                        for img in images_list
                    ]
                    repo.save_images(file_hash, images_to_save)
                except Exception as e:
                    logger.error(f"[Task {task_id}] Failed to save images page {page_num}: {e}")
                    db.session.rollback()
        except Exception as e:
            logger.warning(f"[Task {task_id}] Image parsing skipped for page {page_num}: {e}")

        # 更新进度
        _update_progress(file_hash, page_num)
        task_self.update_state(state="PROGRESS", meta={
            "current_page": page_num,
            "total_pages": page_count,
            "phase": "parsing",
        })


def _run_rag_indexing_from_db(file_hash: str, task_id: str, user_id: uuid.UUID):
    """使用数据库中的已解析段落执行 RAG 向量索引。"""
    repo = SQLRepository(db.session)
    try:
        paragraphs = repo.get_paragraphs(file_hash)
        if not paragraphs:
            logger.warning(f"[Task {task_id}] No paragraphs found in DB for {file_hash}, skipping RAG.")
            return

        from services.rag_service import RAGService
        rag_service = RAGService()
        logger.info(f"[Task {task_id}] Starting RAG indexing from DB for user {user_id}...")
        result = rag_service.index_paper_from_db(file_hash=file_hash, paragraphs=paragraphs, user_id=user_id)
        if result.get("success"):
            logger.info(f"[Task {task_id}] RAG indexing done. Chunks: {result.get('chunks_created')}")
        else:
            logger.warning(f"[Task {task_id}] RAG indexing failed: {result.get('message')}")
    except ImportError as e:
        logger.warning(f"[Task {task_id}] RAG service not available: {e}")
    except Exception as e:
        logger.error(f"[Task {task_id}] Error in RAG indexing: {e}")
