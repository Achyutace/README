"""
PDF 服务  —— 异步处理
上传:
    1. 计算 Hash → 查重 (秒传)
    2. 保存文件到本地 + 上传 COS
    3. 写入 DB (status=pending)
    4. 派发 Celery 异步任务 (分页解析 + RAG)
    5. 立即返回 {task_id, status: "processing"}
查询:
    1. 获取pdf指定页面的段落数据(支持全文和全页面)
    2. 获取pdf元数据
    3. 获取pdf图片(支持指定页面指定图片(id))
    4. 获取pdf源文件
"""
import os
import uuid
import hashlib
import logging
from werkzeug.utils import secure_filename

from core.database import SessionLocal
from repository.sql_repo import SQLRepository
from repository.object_repo import object_storage
from utils import pdf_engine

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
    
    def _get_repo(self):
        """辅助方法：获取 DB session 和 Repository 实例"""
        db = SessionLocal()
        return db, SQLRepository(db)

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
                # COS Key 就是 pdf_id
                if object_storage.download_file(pdf_id, candidate):
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

    @staticmethod
    def calculate_stream_hash(stream) -> str:
        """计算文件流的 SHA256 Hash"""
        sha256 = hashlib.sha256()
        for chunk in iter(lambda: stream.read(8192), b""):
            sha256.update(chunk)
        stream.seek(0)
        return sha256.hexdigest()

    # ===================== 上传逻辑核心: 上传 + 触发异步 =====================

    def upload_and_dispatch(self, file, file_hash: str, user_id, filename: str) -> dict:
        """
        上传 PDF 并触发异步处理任务。

        Args:
            file:      上传的文件对象
            file_hash: SHA256 哈希
            user_id:   用户 ID (uuid.UUID 类型)
            filename:  原始文件名

        Returns:
            dict: 包含 pdf_id, task_id, status, pageCount, exists 等信息
        """
        from tasks.pdf_tasks import process_pdf  

        pdf_id = file_hash
        safe_filename = secure_filename(filename)

        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        # 数据库查重
        db, repo = self._get_repo()
        try:
            gf = repo.get_global_file(pdf_id)
            if gf:
                # 文件已存在于系统中，添加UserPaper 关联
                repo.create_user_paper(
                    user_id=user_id,
                    file_hash=pdf_id,
                    title=safe_filename,
                )

                if gf.process_status == "completed":
                    # 已完成解析 → 秒传
                    logger.info(f"[Upload] File {pdf_id} already completed, instant return")
                    return {
                        "pdf_id": pdf_id,
                        "task_id": gf.task_id,
                        "status": "completed",
                        "pageCount": gf.total_pages or 0,
                        "filename": safe_filename,
                        "exists": True,
                    }

                if gf.process_status == "processing":
                    # 正在处理中 → 返回当前任务信息，前端继续轮询
                    logger.info(f"[Upload] File {pdf_id} still processing, task_id={gf.task_id}")
                    return {
                        "pdf_id": pdf_id,
                        "task_id": gf.task_id,
                        "status": "processing",
                        "pageCount": gf.total_pages or 0,
                        "filename": safe_filename,
                        "exists": True,
                    }

                # pending / failed → 重新触发任务
                logger.info(f"[Upload] File {pdf_id} status={gf.process_status}, will re-dispatch")
        except Exception as e:
            logger.error(f"[Upload] DB check failed: {e}")
        finally:
            db.close()

        # 保存文件到本地
        filepath = os.path.join(self.upload_folder, pdf_id)
        if not os.path.exists(filepath):
            file.save(filepath)
            logger.info(f"[Upload] Saved file to {filepath}")
        else:
            logger.info(f"[Upload] File already on disk: {filepath}")

        # 上传到 COS
        if object_storage.config.enabled:
            try:
                with open(filepath, 'rb') as f:
                    object_storage.upload_file(f, pdf_id)
                logger.info(f"[Upload] Uploaded {pdf_id} to COS")
            except Exception as e:
                logger.error(f"[Upload] COS upload failed: {e}")

        # 获取页数
        try:
            page_count = pdf_engine.get_page_count(filepath)
        except Exception as e:
            logger.error(f"[Upload] Failed to get page count: {e}")
            page_count = 0

        # 写入 / 更新 GlobalFile (pending)
        db, repo = self._get_repo()
        try:
            file_size = os.path.getsize(filepath)
            gf = repo.get_global_file(pdf_id)
            if gf:
                # 更新已有记录
                gf.process_status = "pending"
                gf.error_message = None
                gf.total_pages = page_count
                gf.current_page = 0
                db.commit()
            else:
                repo.create_global_file(
                    file_hash=pdf_id,
                    file_path=pdf_id,  # COS key = pdf_id
                    file_size=file_size,
                    total_pages=page_count,
                )

            # 创建 UserPaper 关联
            try:
                repo.create_user_paper(
                    user_id=user_id,
                    file_hash=pdf_id,
                    title=safe_filename,
                )
            except Exception:
                pass  
        except Exception as e:
            logger.error(f"[Upload] DB write failed: {e}")
            db.rollback()
        finally:
            db.close()

        # 派发 Celery 异步任务
        new_task_id = str(uuid.uuid4())
        task = process_pdf.apply_async(
            args=[pdf_id, self.upload_folder, safe_filename, page_count, str(user_id)],
            task_id=new_task_id, 
        )
        task_id = task.id

        # 回写 task_id 到 DB
        db, repo = self._get_repo()
        try:
            repo.update_pdf_task(pdf_id, task_id)
        except Exception as e:
            logger.warning(f"[Upload] Failed to save task_id: {e}")
        finally:
            db.close()

        # 更新内存注册表
        self.pdf_registry[pdf_id] = {
            'id': pdf_id,
            'filename': safe_filename,
            'filepath': filepath,
            'pageCount': page_count,
        }

        logger.info(f"[Upload] Dispatched task {task_id} for {pdf_id}")

        return {
            "pdf_id": pdf_id,
            "task_id": task_id,
            "status": "processing",
            "pageCount": page_count,
            "filename": safe_filename,
            "exists": False,
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
        db, repo = self._get_repo()
        try:
            progress = repo.get_process_progress(pdf_id)
            if not progress:
                return {"status": "not_found", "error": "PDF not found"}

            status = progress["status"]       # pending / processing / completed / failed
            current_page = progress["current_page"]
            total_pages = progress["total_pages"]
            error_msg = progress.get("error")

            # 拉取已解析的段落 (from_page ~ current_page)
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
        finally:
            db.close()

    def _format_paragraph(self, p, pdf_id: str) -> dict:
        """格式化段落数据"""
        para_id = pdf_engine.make_paragraph_id(pdf_id, p.page_number, p.paragraph_index)
        return {
            "id": para_id,
            "page": p.page_number,
            "bbox": p.bbox,
            "content": p.original_text,
            "wordCount": len(p.original_text.split()) if p.original_text else 0,
            "translation": p.translation_text,
        }

    # ================= 读取接口 =========================

    def get_info(self, pdf_id: str) -> dict:
        """
        获取 PDF 元数据。
        """
        db, repo = self._get_repo()
        try:
            gf = repo.get_global_file(pdf_id)
            if gf:
                return {
                    'id': gf.file_hash,
                    'pageCount': gf.total_pages,
                    'metadata': gf.metadata_info or {}
                }
        except Exception as e:
            logger.warning(f"DB lookup failed for {pdf_id}: {e}")
        finally:
            db.close()

        filepath = self.get_filepath(pdf_id)
        return pdf_engine.get_pdf_info(pdf_id, filepath)

    def get_paragraph(self, pdf_id: str, page_number: int = None, paragraph_index: int = None) -> dict:
        """获取段落文本"""
        filepath = self.get_filepath(pdf_id)

        page_numbers = [page_number] if page_number else None
        paragraphs = pdf_engine.parse_paragraphs(filepath, pdf_id, page_numbers=page_numbers)

        if paragraph_index is not None:
            paragraphs = [p for p in paragraphs if p['index'] == paragraph_index]

        full_text = "\n\n".join([p['content'] for p in paragraphs])

        blocks = []
        for p in paragraphs:
            x, y, w, h = p['bbox']
            blocks.append({
                'text': p['content'],
                'pageNumber': p['page'],
                'bbox': [x, y, x + w, y + h]
            })

        return {
            'text': full_text,
            'blocks': blocks
        }

# ============== 图片 ========================

    def get_images_list(self, pdf_id: str) -> list[dict]:
        """获取图片元数据列表"""
        """
        db, repo = self._get_repo()
        try:
            db_imgs = repo.get_images(pdf_id)
            if db_imgs and len(db_imgs) > 0:
                result = []
                for img in db_imgs:
                    image_index = img.image_index
                    image_id = pdf_engine.make_image_id(pdf_id, image_index)
                    result.append({
                        "id": image_id,
                        "page": img.page_number,
                        "bbox": img.bbox
                    })
                return result
        except Exception as e:
            logger.warning(f"Failed to fetch images from DB for {pdf_id}: {e}")
        finally:
            db.close()

        try:
            filepath = self.get_filepath(pdf_id)
            images_list = pdf_engine.get_images_list(filepath, pdf_id)

            db, repo = self._get_repo()
            try:
                images_to_save = []
                for img in images_list:
                    images_to_save.append({
                        "page_number": img['page'],
                        "image_index": img['index'],
                        "bbox": img['bbox'],
                        "caption": ""
                    })
                repo.save_images(pdf_id, images_to_save)
                logger.info(f"Recovered and saved {len(images_to_save)} images meta for {pdf_id}")
            except Exception as save_err:
                logger.error(f"Failed to save recovered images to DB for {pdf_id}: {save_err}")
            finally:
                db.close()

            return images_list

        except Exception as e:
            logger.error(f"Error fetching images list for {pdf_id}: {e}")
            return []
        """
        pass
    
    def get_image_data(self, image_id: str) -> dict:
        """获取图片 Base64 数据"""
        """
        try:
            pdf_id, image_index = pdf_engine.parse_image_id(image_id)
            filepath = self.get_filepath(pdf_id)
            result = pdf_engine.get_image_data(filepath, image_index)
            if result:
                result['id'] = image_id
            return result
        except Exception as e:
            logger.error(f"Error fetching image data {image_id}: {e}")
            return None
        """
        pass

