"""
PDF 异步处理任务
职责:
    1. 逐页解析 PDF 段落 —— 每解析一页就写入 DB，前端可按页轮询
    2. 解析图片元数据
    3. RAG 向量化
    4. 标记完成 (completed)

状态机:
    pending → processing → completed
                        → failed
"""
import os
import logging
from celery import shared_task

from core.database import SessionLocal
from repository.sql_repo import SQLRepository
from repository.object_repo import object_storage
from utils import pdf_engine

logger = logging.getLogger(__name__)

# ==========================================
# 状态常量 (仅 4 种)
# ==========================================
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def _get_repo():
    """创建一个新的 DB session + Repository"""
    db = SessionLocal()
    return db, SQLRepository(db)


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
        try:
            if object_storage.download_file(file_hash, candidate):
                logger.info(f"Downloaded {file_hash} from COS to {candidate}")
                return candidate
        except Exception as e:
            logger.warning(f"Failed to download {file_hash} from COS: {e}")

    raise FileNotFoundError(f"PDF file not found: {file_hash}")


# ==========================================
# Celery Task
# ==========================================

@shared_task(bind=True, name="tasks.pdf_tasks.process_pdf",
             max_retries=3, default_retry_delay=60)
def process_pdf(self, file_hash: str, upload_folder: str,
                filename: str, page_count: int, user_id: str):
    """
    PDF 全流程异步处理任务。

    Args:
        file_hash:     文件 SHA256 (= pdf_id)
        upload_folder: 用户上传目录绝对路径
        filename:      原始文件名
        page_count:    页数 (上传时已获取)
        user_id:       用户 ID
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Start processing PDF {file_hash}, pages={page_count}")

    try:
        # ---------- 0. 定位文件 ----------
        filepath = _resolve_filepath(file_hash, upload_folder)

        # ============================================
        # 阶段 1: 逐页解析段落
        # ============================================
        _update_status(file_hash, STATUS_PROCESSING, task_id=task_id)

        for page_num in range(1, page_count + 1):
            logger.info(f"[Task {task_id}] Parsing page {page_num}/{page_count}")

            # 调用引擎解析单页
            paragraphs = pdf_engine.parse_paragraphs(filepath, file_hash, page_numbers=[page_num])

            # 写入数据库
            if paragraphs:
                db, repo = _get_repo()
                try:
                    paras_to_save = []
                    for p in paragraphs:
                        paras_to_save.append({
                            "page_number": p["page"],
                            "paragraph_index": p["index"],
                            "original_text": p["content"],
                            "bbox": p["bbox"],
                        })
                    repo.save_paragraphs(file_hash, paras_to_save)
                except Exception as e:
                    logger.error(f"[Task {task_id}] Failed to save paragraphs page {page_num}: {e}")
                finally:
                    db.close()

            # 更新已处理页数
            _update_progress(file_hash, page_num)

            # 更新 Celery 任务元信息 (供 AsyncResult.info 查询)
            self.update_state(state="PROGRESS", meta={
                "current_page": page_num,
                "total_pages": page_count,
                "phase": "text_parsing",
            })

        # ============================================
        # 阶段 2: 解析图片元数据
        # ============================================
        # 状态保持 processing，不需要再更新

        try:
            images_list = pdf_engine.get_images_list(filepath, file_hash)
            if images_list:
                db, repo = _get_repo()
                try:
                    images_to_save = []
                    for img in images_list:
                        images_to_save.append({
                            "page_number": img["page"],
                            "image_index": img["index"],
                            "bbox": img["bbox"],
                            "caption": "",
                        })
                    repo.save_images(file_hash, images_to_save)
                    logger.info(f"[Task {task_id}] Saved {len(images_to_save)} images meta")
                except Exception as e:
                    logger.error(f"[Task {task_id}] Failed to save images: {e}")
                finally:
                    db.close()
        except Exception as e:
            logger.warning(f"[Task {task_id}] Image parsing skipped: {e}")

        self.update_state(state="PROGRESS", meta={
            "current_page": page_count,
            "total_pages": page_count,
            "phase": "image_parsing",
        })

        # ============================================
        # 阶段 3: RAG 向量化
        # ============================================
        # 状态保持 processing

        self.update_state(state="PROGRESS", meta={
            "current_page": page_count,
            "total_pages": page_count,
            "phase": "vectorizing",
        })

        try:
            _run_rag_indexing(file_hash, filepath, user_id, task_id)
        except Exception as e:
            logger.warning(f"[Task {task_id}] RAG indexing failed (non-fatal): {e}")

        # ============================================
        # 阶段 4: 完成
        # ============================================
        _update_status(file_hash, STATUS_COMPLETED)

        logger.info(f"[Task {task_id}] PDF {file_hash} processing completed")
        return {
            "status": STATUS_COMPLETED,
            "file_hash": file_hash,
            "total_pages": page_count,
        }

    except FileNotFoundError as e:
        _update_status(file_hash, STATUS_FAILED, error=str(e))
        raise

    except Exception as exc:
        _update_status(file_hash, STATUS_FAILED, error=str(exc))
        logger.error(f"[Task {task_id}] Unexpected error: {exc}")
        # Celery 自动重试
        raise self.retry(exc=exc)


# ==========================================
# 辅助函数
# ==========================================

def _update_status(file_hash: str, status: str, task_id: str = None, error: str = None):
    """更新 GlobalFile 的处理状态"""
    db, repo = _get_repo()
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
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update status for {file_hash}: {e}")
        db.rollback()
    finally:
        db.close()


def _update_progress(file_hash: str, current_page: int):
    """更新当前已解析到的页码"""
    db, repo = _get_repo()
    try:
        gf = repo.get_global_file(file_hash)
        if gf:
            gf.current_page = current_page
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update progress for {file_hash}: {e}")
        db.rollback()
    finally:
        db.close()


def _run_rag_indexing(file_hash: str, filepath: str, user_id: str, task_id: str):
    """
    执行 RAG 向量索引。
    延迟导入以避免循环依赖。
    """
    try:
        from services.rag_service import RAGService
        from pathlib import Path
        from core.config import settings

        chroma_dir = str(Path(filepath).resolve().parent.parent.parent / "storage" / "chroma_db")
        rag_service = RAGService(chroma_dir=chroma_dir)

        if not rag_service.check_exists(file_hash):
            logger.info(f"[Task {task_id}] Starting RAG indexing...")
            result = rag_service.index_paper(
                pdf_path=filepath,
                paper_id=file_hash,
                user_id=user_id,
            )
            if result.get("success"):
                logger.info(f"[Task {task_id}] RAG indexing done. Chunks: {result.get('chunks_created')}")
            else:
                logger.warning(f"[Task {task_id}] RAG indexing failed: {result.get('message')}")
        else:
            logger.info(f"[Task {task_id}] RAG index already exists, skipped.")
    except ImportError as e:
        logger.warning(f"[Task {task_id}] RAG service not available: {e}")
    except Exception as e:
        raise
