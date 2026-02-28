"""
MinerU 云端 API 服务 —— PDF 全量解析引擎

工作流程：
  1. 通过批量文件上传接口获取预签名 URL
  2. PUT 上传本地 PDF 到 OSS
  3. 轮询任务状态，直到 done / failed
  4. 下载结果 ZIP 并解压
  5. 解析 content_list_v2.json 提取结构化内容（段落/图片/表格/公式/标题）
  6. 读取 full.md 获取完整 Markdown

使用方式::

    svc = MinerUService()
    # 提取结构化内容
    result = svc.extract_and_parse("/path/to/file.pdf", "abc123", "/path/to/cache")
    # result = {
    #     "page_count": 16,
    #     "paragraphs": [{"page": 1, "index": 0, "content": "...", "bbox": [...]}],
    #     "images":     [{"page": 1, "index": 0, "path": "images/xx.jpg", "caption": "...", "bbox": [...]}],
    #     "tables":     [{"page": 5, "index": 0, "path": "images/xx.jpg", "caption": "...", "bbox": [...]}],
    #     "formulas":   [{"page": 3, "index": 0, "latex": "...", "bbox": [...]}],
    #     "markdown":   "# Title\n\n...",
    # }
"""

import io
import json
import re
import time
import zipfile
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
_API_BASE = "https://mineru.net/api/v4"
_POLL_INTERVAL = 5           # 轮询间隔（秒）
_POLL_TIMEOUT = 600          # 最大等待（秒）
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp", ".svg"}
_TABLE_EXTS = {".html", ".csv", ".xlsx", ".latex", ".tex"}

# content_list_v2 中需要忽略的类型（页码、页眉页脚等噪音）
_SKIP_TYPES = {"page_number", "page_header", "page_aside_text", "page_footnote"}


class MinerUService:
    """
    MinerU 云端 API 全量 PDF 解析服务。

    主要用于替代 PyMuPDF 的段落 / 图片 / 表格 / 公式提取。
    PyMuPDF 仅保留用于元数据（page count / dimensions）读取。
    """

    def __init__(self):
        cfg = getattr(settings, "mineru", None)
        self.token: str = cfg.api_token if cfg else ""
        self.model_version: str = (cfg.model_version if cfg else "vlm") or "vlm"
        self._sess: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """返回带自动重试的 requests Session（处理 SSL 抖动）。"""
        if self._sess is None:
            s = requests.Session()
            retry = Retry(
                total=3,
                backoff_factor=2,
                status_forcelist=[502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            # 对阿里云 OSS 域名绕过本地代理（避免 SSL 握手失败）
            s.trust_env = False
            self._sess = s
        return self._sess

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    @staticmethod
    def is_configured() -> bool:
        """MinerU 是否可用（Token 已配置）。"""
        cfg = getattr(settings, "mineru", None)
        return bool(cfg and cfg.api_token)

    def extract_and_parse(
        self,
        pdf_path: str,
        pdf_id: str,
        output_dir: str,
    ) -> Dict[str, Any]:
        """
        主入口：上传 PDF → 等待解析 → 下载解压 → 解析 content_list_v2.json。

        Args:
            pdf_path:   本地 PDF 文件路径
            pdf_id:     PDF 唯一标识（file hash）
            output_dir: 结果解压目标目录

        Returns:
            {
                "page_count":  int,
                "paragraphs":  [{"page", "index", "content", "bbox"}],
                "images":      [{"page", "index", "path", "caption", "bbox"}],
                "tables":      [{"page", "index", "path", "caption", "bbox"}],
                "formulas":    [{"page", "index", "latex", "bbox"}],
                "markdown":    str,
            }
        """
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        # 如果已有缓存结果 (content_list_v2.json 存在)，跳过上传
        content_json = self._find_content_json(output_dir)
        if content_json is None:
            output_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: 上传文件
            batch_id = self._upload_file(pdf_path)
            logger.info(f"[MinerU] 文件已上传, batch_id={batch_id}")

            # Step 2: 轮询
            zip_url = self._poll_batch_result(batch_id, pdf_path.name)
            logger.info(f"[MinerU] 任务完成, zip_url={zip_url}")

            # Step 3: 下载解压
            self._download_and_extract(zip_url, output_dir)
            logger.info(f"[MinerU] 结果已解压到: {output_dir}")

            content_json = self._find_content_json(output_dir)

        if content_json is None:
            raise RuntimeError(f"MinerU 解析完成但未找到 content_list_v2.json: {output_dir}")

        # Step 4: 解析结构化内容
        parsed = self.parse_content_list(content_json, output_dir)

        # Step 5: 读取完整 Markdown
        parsed["markdown"] = self.get_full_markdown(output_dir)

        return parsed

    # ------ 兼容旧接口 ------
    def extract_assets(
        self,
        pdf_path: str,
        pdf_id: str,
        output_dir: str,
    ) -> Dict[str, List[Path]]:
        """向后兼容：仅返回 images/tables 文件路径列表。"""
        result = self.extract_and_parse(pdf_path, pdf_id, output_dir)
        out_path = Path(output_dir)
        images = []
        tables = []
        for img in result.get("images", []):
            p = out_path / img["path"]
            if p.exists():
                images.append(p)
        for tbl in result.get("tables", []):
            p = out_path / tbl["path"]
            if p.exists():
                tables.append(p)
        return {"images": images, "tables": tables}

    # ------------------------------------------------------------------
    # 结构化内容解析
    # ------------------------------------------------------------------

    @staticmethod
    def _find_content_json(output_dir: Path) -> Optional[Path]:
        """在 output_dir 及其子目录中递归查找 content_list_v2.json。"""
        for f in output_dir.rglob("content_list_v2.json"):
            return f
        return None

    @staticmethod
    def _find_file(output_dir: Path, filename: str) -> Optional[Path]:
        """在 output_dir 及其子目录中递归查找指定文件。"""
        for f in output_dir.rglob(filename):
            return f
        return None

    def parse_content_list(self, content_json_path: Path, output_dir: Path) -> Dict[str, Any]:
        """
        解析 content_list_v2.json，提取段落、图片、表格、公式。

        content_list_v2.json 结构：外层是一个 list[list[dict]]，
        第一层索引 = 页码 (0-based)，第二层是该页各内容项。
        每个 item 有 type、content、bbox 字段。

        Returns:
            {
                "page_count":  int,
                "paragraphs":  [{page, index, content, bbox}],
                "images":      [{page, index, path, caption, bbox}],
                "tables":      [{page, index, path, caption, bbox}],
                "formulas":    [{page, index, latex, bbox}],
            }
        """
        with open(content_json_path, "r", encoding="utf-8") as f:
            pages_data: List[List[dict]] = json.load(f)

        # content_json 所在目录（MinerU 的 images/ 相对于此目录）
        content_root = content_json_path.parent

        paragraphs: List[dict] = []
        images: List[dict] = []
        tables: List[dict] = []
        formulas: List[dict] = []

        para_idx_by_page: Dict[int, int] = {}   # page -> running index
        img_global_idx = 0
        tbl_global_idx = 0
        formula_global_idx = 0

        for page_idx, page_items in enumerate(pages_data):
            page_num = page_idx + 1  # 1-based
            para_idx_by_page[page_num] = 0

            for item in page_items:
                item_type = item.get("type", "")
                if item_type in _SKIP_TYPES:
                    continue

                content = item.get("content", {})
                bbox = item.get("bbox", [])

                if item_type in ("paragraph", "title", "list", "code"):
                    text = self._extract_text(content, item_type)
                    if text and len(text.strip()) > 0:
                        idx = para_idx_by_page[page_num]
                        paragraphs.append({
                            "page": page_num,
                            "index": idx,
                            "content": text.strip(),
                            "bbox": bbox,
                        })
                        para_idx_by_page[page_num] = idx + 1

                elif item_type == "image":
                    img_info = self._extract_image_info(content, content_root)
                    img_info["page"] = page_num
                    img_info["index"] = img_global_idx
                    img_info["bbox"] = bbox
                    images.append(img_info)
                    img_global_idx += 1

                elif item_type == "table":
                    tbl_info = self._extract_table_info(content, content_root)
                    tbl_info["page"] = page_num
                    tbl_info["index"] = tbl_global_idx
                    tbl_info["bbox"] = bbox
                    tables.append(tbl_info)
                    tbl_global_idx += 1

                elif item_type == "equation_interline":
                    latex = content.get("math_content", "")
                    if latex:
                        formulas.append({
                            "page": page_num,
                            "index": formula_global_idx,
                            "latex": latex,
                            "bbox": bbox,
                        })
                        formula_global_idx += 1

        logger.info(
            f"[MinerU] 解析完成: {len(pages_data)} 页, "
            f"{len(paragraphs)} 段落, {len(images)} 图片, "
            f"{len(tables)} 表格, {len(formulas)} 公式"
        )

        return {
            "page_count": len(pages_data),
            "paragraphs": paragraphs,
            "images": images,
            "tables": tables,
            "formulas": formulas,
        }

    def get_full_markdown(self, output_dir: Path) -> str:
        """读取 full.md 完整 Markdown 内容。"""
        output_dir = Path(output_dir)
        md_file = self._find_file(output_dir, "full.md")
        if md_file and md_file.exists():
            return md_file.read_text(encoding="utf-8")
        return ""

    # ------------------------------------------------------------------
    # 内容提取辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(content: dict, item_type: str) -> str:
        """
        从 content 字典中提取纯文本。

        不同 type 的 content 结构不同：
        - paragraph: {"paragraph_content": [{"type": "text", "content": "..."}]}
        - title:     {"title_content": [{"type": "text", "content": "..."}], "level": 1}
        - list:      {"list_items": [{"item_content": [{"type": "text", "content": "..."}]}]}
        - code:      {"code_content": "..."} 或类似 paragraph
        """
        parts: List[str] = []

        if item_type == "title":
            for seg in content.get("title_content", []):
                if seg.get("type") == "text":
                    parts.append(seg.get("content", ""))
                elif seg.get("type") == "equation_inline":
                    parts.append(f"${seg.get('content', '')}$")

        elif item_type == "paragraph":
            for seg in content.get("paragraph_content", []):
                if seg.get("type") == "text":
                    parts.append(seg.get("content", ""))
                elif seg.get("type") == "equation_inline":
                    parts.append(f"${seg.get('content', '')}$")

        elif item_type == "list":
            # list 结构: {"list_items": [{"item_content": [{"type": "text", "content": "..."}]}]}
            for item in content.get("list_items", []):
                if isinstance(item, dict):
                    item_parts = []
                    for seg in item.get("item_content", []):
                        if isinstance(seg, dict):
                            item_parts.append(seg.get("content", ""))
                    if item_parts:
                        parts.append(" ".join(item_parts))

        elif item_type == "code":
            code_content = content.get("code_content", "")
            if isinstance(code_content, str):
                parts.append(code_content)
            elif isinstance(code_content, list):
                for seg in code_content:
                    if isinstance(seg, dict):
                        parts.append(seg.get("content", ""))
                    elif isinstance(seg, str):
                        parts.append(seg)
            if not parts:
                for seg in content.get("paragraph_content", []):
                    if seg.get("type") == "text":
                        parts.append(seg.get("content", ""))

        return " ".join(parts)

    @staticmethod
    def _extract_image_info(content: dict, content_root: Path) -> dict:
        """从 image 类型 content 提取图片路径和 caption。"""
        path = ""
        caption = ""

        img_source = content.get("image_source", {})
        if img_source:
            path = img_source.get("path", "")

        # caption 由一系列 text/equation 片段组成
        caption_parts = []
        for seg in content.get("image_caption", []):
            if isinstance(seg, dict):
                caption_parts.append(seg.get("content", ""))
        if caption_parts:
            caption = " ".join(caption_parts).strip()

        return {"path": path, "caption": caption}

    @staticmethod
    def _extract_table_info(content: dict, content_root: Path) -> dict:
        """从 table 类型 content 提取表格图片路径和 caption。"""
        path = ""
        caption = ""

        img_source = content.get("image_source", {})
        if img_source:
            path = img_source.get("path", "")

        caption_parts = []
        for seg in content.get("table_caption", []):
            if isinstance(seg, dict):
                caption_parts.append(seg.get("content", ""))
        if caption_parts:
            caption = " ".join(caption_parts).strip()

        return {"path": path, "caption": caption}

    # ------------------------------------------------------------------
    # API 交互
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        if not self.token:
            raise RuntimeError(
                "MinerU API Token 未配置。"
                "请在 config.yaml 的 mineru.api_token 中填写。"
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _upload_file(self, pdf_path: Path) -> str:
        """
        通过 /file-urls/batch 接口获取预签名上传链接，
        再 PUT 文件到 OSS。

        Returns:
            batch_id
        """
        url = f"{_API_BASE}/file-urls/batch"
        payload = {
            "files": [{"name": pdf_path.name}],
            "model_version": self.model_version,
            "enable_table": True,
        }

        resp = self._get_session().post(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        body = resp.json()

        if body.get("code") != 0:
            raise RuntimeError(f"MinerU 申请上传链接失败: {body.get('msg', body)}")

        batch_id = body["data"]["batch_id"]
        file_urls = body["data"]["file_urls"]

        if not file_urls:
            raise RuntimeError("MinerU 返回空的上传链接列表")

        # PUT 上传二进制（OSS 可能存在 SSL 握手问题，关闭验证并重试）
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        with open(pdf_path, "rb") as f:
            put_resp = self._get_session().put(
                file_urls[0], data=f, timeout=300, verify=False
            )

        if put_resp.status_code != 200:
            raise RuntimeError(
                f"文件上传到 OSS 失败, status={put_resp.status_code}, "
                f"body={put_resp.text[:200]}"
            )

        return batch_id

    def _poll_batch_result(self, batch_id: str, filename: str) -> str:
        """
        轮询 /extract-results/batch/{batch_id} 直到完成。

        Returns:
            full_zip_url
        """
        url = f"{_API_BASE}/extract-results/batch/{batch_id}"
        get_headers = {"Authorization": self._headers()["Authorization"]}

        deadline = time.time() + _POLL_TIMEOUT

        while time.time() < deadline:
            resp = self._get_session().get(url, headers=get_headers, timeout=30)
            resp.raise_for_status()
            body = resp.json()

            if body.get("code") != 0:
                raise RuntimeError(f"MinerU 查询任务失败: {body.get('msg', body)}")

            results = body["data"].get("extract_result", [])
            if not results:
                time.sleep(_POLL_INTERVAL)
                continue

            result = results[0]
            state = result.get("state", "")

            if state == "done":
                zip_url = result.get("full_zip_url", "")
                if not zip_url:
                    raise RuntimeError("MinerU 任务完成但未返回 zip URL")
                return zip_url

            if state == "failed":
                err = result.get("err_msg", "未知错误")
                raise RuntimeError(f"MinerU 解析失败: {err}")

            # pending / running / converting / waiting-file → 继续等待
            progress = result.get("extract_progress", {})
            extracted = progress.get("extracted_pages", "?")
            total = progress.get("total_pages", "?")
            logger.info(f"[MinerU] 进度: {state} ({extracted}/{total})")

            time.sleep(_POLL_INTERVAL)

        raise TimeoutError(f"MinerU 任务超时 ({_POLL_TIMEOUT}s), batch_id={batch_id}")

    # ------------------------------------------------------------------
    # 文件处理
    # ------------------------------------------------------------------

    def _download_and_extract(self, zip_url: str, output_dir: Path):
        """下载 ZIP 并解压到 output_dir。"""
        resp = self._get_session().get(zip_url, stream=True, timeout=300, verify=False)
        resp.raise_for_status()

        zip_bytes = io.BytesIO(resp.content)
        with zipfile.ZipFile(zip_bytes) as zf:
            zf.extractall(output_dir)
