import uuid
import logging
from datetime import datetime, timedelta
from core.database import db

logger = logging.getLogger(__name__)

def dispatch_pdf_task(gf, pdf_id: str, upload_folder: str, filename: str, page_count: int, user_id=None, is_restart: bool = False) -> str:
    """
    统一更新 GlobalFile 状态为 pending 并启动 Celery 任务。
    返回新的 task_id。
    """
    from tasks.pdf_tasks import process_pdf
    tag = "[Restart]" if is_restart else "[Ingest]"
    
    new_task_id = str(uuid.uuid4())
    gf.process_status = "pending"
    gf.error_message = None
    gf.current_page = 0
    gf.updated_at = datetime.now()
    gf.task_id = new_task_id
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"{tag} DB transaction failed: {e}")
        raise e
        
    try:
        process_pdf.apply_async(
            args=[pdf_id, upload_folder, filename, page_count, user_id],
            kwargs={"is_restart": is_restart},
            task_id=new_task_id,
        )
        logger.info(f"{tag} Dispatched Celery task {new_task_id} for {pdf_id} (user={user_id})")
    except Exception as e:
        logger.error(f"{tag} Failed to dispatch Celery task for {pdf_id}: {e}")
        gf.process_status = "failed"
        gf.error_message = f"Task dispatch failed: {str(e)}"
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        raise e
        
    return new_task_id

def check_and_restart_stuck_task(gf, pdf_id: str, upload_folder: str, timeout_minutes: int, user_id=None) -> bool:
    """
    检查判断任务是否卡死并重启。
    如果卡死并重启，返回 True，否则返回 False。
    """
    is_stuck = False
    if gf.process_status in ("pending", "processing") and gf.updated_at:
        if datetime.now() - gf.updated_at > timedelta(minutes=timeout_minutes):
            is_stuck = True
            
    if not is_stuck:
        return False
        
    logger.warning(f"[Ingest/Poll] Task {gf.task_id} for {pdf_id} stuck > {timeout_minutes}m. Restarting.")
    
    page_count = gf.total_pages or 0
    try:
        dispatch_pdf_task(
            gf=gf,
            pdf_id=pdf_id,
            upload_folder=upload_folder,
            filename=f"{pdf_id}.pdf",
            page_count=page_count,
            user_id=user_id,
            is_restart=True
        )
        return True
    except Exception:
        return False
