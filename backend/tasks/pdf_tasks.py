"""
PDF 异步处理任务
1. 先逐页解析 PDF 段落 + 解析图片元数据：每解析一页就写入 DB，前端可按页轮询
2. 通过 MinerU API 提取高质量图�?表格资产
3. 再逐段落向量化
状态机:
    pending �?processing �?completed / failed
"""
import os
import shutil
import logging
import uuid
from pathlib import Path
from celery_app import celery

from core.database import db
from repository.sql_repo import SQLRepository
from repository.object_repo import object_storage
from utils import pdf_engine

logger = logging.getLogger(__name__)

# 状态常�?
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def _resolve_filepath(file_hash: str, upload_folder: str) -> str:
    """
    解析 PDF 文件路径�?
    优先读本�?upload_folder，其次从 COS 下载�?
    """
    # 1. 本地磁盘
    candidate = os.path.join(upload_folder, file_hash)
    if os.path.exists(candidate):
        return candidate

    # 2. COS 下载
    if object_storage.config.enabled:
        # 使用临时文件防止并发写冲�?
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

@celery.task(bind=True, name="tasks.pdf_tasks.process_pdf",
             max_retries=3, default_retry_delay=60)

def process_pdf(self, file_hash: str, upload_folder: str, filename: str, page_count: int, user_id: uuid.UUID = None):
    """
    PDF 全流程异步处理任务�?

    Args:
        file_hash:     pdf_id
        upload_folder: 用户上传目录绝对路径
        filename:      原始文件�?
        page_count:    页数 
        user_id:       用户 ID (UUID)
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Start processing PDF {filename} ({file_hash}), pages={page_count}, user={user_id}")

    from celery_app import get_worker_app
    with get_worker_app().app_context():
        try:
            filepath = _resolve_filepath(file_hash, upload_folder)

            # ================= 逐页解析段落 + 图片元数�?===========================
            _update_status(file_hash, STATUS_PROCESSING, task_id=task_id)

            for page_num in range(1, page_count + 1):
                logger.info(f"[Task {task_id}] Processing page {page_num}/{page_count}")

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

                # 解析图片元数�?
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
                            logger.info(f"[Task {task_id}] Saved {len(images_to_save)} images for page {page_num}")
                        except Exception as e:
                            logger.error(f"[Task {task_id}] Failed to save images page {page_num}: {e}")
                            db.session.rollback()
                except Exception as e:
                    logger.warning(f"[Task {task_id}] Image parsing skipped for page {page_num}: {e}")

                # 更新进度
                _update_progress(file_hash, page_num)

                # 更新 Celery 任务元信�?
                self.update_state(state="PROGRESS", meta={
                    "current_page": page_num,
                    "total_pages": page_count,
                    "phase": "parsing",
                })

        # ===================== 逐段落向量化 =======================
            # ---- MinerU 图片/表格高质量提�?----
            self.update_state(state="PROGRESS", meta={
                "current_page": page_count,
                "total_pages": page_count,
                "phase": "mineru_extracting",
            })

            try:
                _run_mineru_extraction(file_hash, filepath, upload_folder, task_id)
            except Exception as e:
                # MinerU 失败不影响主流程，降级为只有 PyMuPDF 的基础图片元数�?
                logger.warning(f"[Task {task_id}] MinerU extraction failed (non-fatal): {e}")

            self.update_state(state="PROGRESS", meta={
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
            raise self.retry(exc=exc)


# ================== 辅助函数 ========================

def _update_status(file_hash: str, status: str, task_id: str = None, error: str = None):
    """更新 GlobalFile 的处理状�?""
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
    """更新当前已解析到的页�?""
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


def _run_rag_indexing_from_db(file_hash: str, task_id: str, user_id: uuid.UUID):
    """使用数据库中的已解析段落执行 RAG 向量索引�?""
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


def _run_mineru_extraction(file_hash: str, filepath: str, upload_folder: str, task_id: str):
    """
    使用 MinerU 云端 API 提取 PDF 中的高质量图片和表格�?
    并将结果持久化到数据库和本地存储�?
    """
    from services.mineru_service import MinerUService

    if not MinerUService.is_configured():
        logger.info(f"[Task {task_id}] MinerU not configured, skipping image/table extraction.")
        return

    svc = MinerUService()

    # MinerU 结果缓存目录: uploads 同级�?cache/mineru/<file_hash>
    cache_root = Path(upload_folder).parent / "cache" / "mineru"
    output_dir = cache_root / file_hash
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[Task {task_id}] Starting MinerU extraction for {file_hash}...")
    assets = svc.extract_assets(filepath, file_hash, str(output_dir))

    image_files = assets.get("images", [])
    table_files = assets.get("tables", [])
    logger.info(
        f"[Task {task_id}] MinerU extracted {len(image_files)} images, "
        f"{len(table_files)} tables for {file_hash}."
    )

    # ---- 保存图片到数据库 ----
    if image_files:
        repo = SQLRepository(db.session)
        try:
            images_to_save = []
            for idx, img_path in enumerate(image_files):
                page_number = MinerUService.guess_page_number(img_path)
                # 存储路径: mineru/<file_hash>/images/<filename>
                relative_path = f"mineru/{file_hash}/images/{img_path.name}"
                images_to_save.append({
                    "page_number": page_number,
                    "image_index": idx,
                    "bbox": [],
                    "caption": "",
                    "image_path": relative_path,
                })
            repo.save_images(file_hash, images_to_save)
            logger.info(f"[Task {task_id}] Saved {len(images_to_save)} MinerU images to DB.")
        except Exception as e:
            logger.error(f"[Task {task_id}] Failed to save MinerU images to DB: {e}")
            db.session.rollback()

    # ---- 保存表格到本地存�?----
    if table_files:
        from app import app
        tables_root = Path(app.config['STORAGE_ROOT']) / 'tables' / file_hash
        tables_root.mkdir(parents=True, exist_ok=True)
        for idx, table_path in enumerate(table_files):
            page_number = MinerUService.guess_page_number(table_path)
            ext = table_path.suffix.lower() or ".html"
            dest_name = f"page_{page_number}_table_{idx}{ext}"
            dest_path = tables_root / dest_name
            try:
                shutil.copy2(str(table_path), str(dest_path))
            except Exception as e:
                logger.warning(f"[Task {task_id}] Failed to copy table {table_path}: {e}")
        logger.info(f"[Task {task_id}] Saved {len(table_files)} MinerU tables to {tables_root}.")

