"""
MinerU 云端 API 服务 —— 负责 PDF 图片 / 表格解析

工作流程：
  1. 通过批量文件上传接口获取预签名 URL
  2. PUT 上传本地 PDF 到 OSS
  3. 轮询任务状态，直到 done / failed
  4. 下载结果 ZIP 并解压，提取 images + tables 资产

使用方式::

    svc = MinerUService()
    assets = svc.extract_assets("/path/to/file.pdf", pdf_id="abc123", output_dir="/path/to/cache")
    # assets = {"images": [Path, ...], "tables": [Path, ...]}
"""

import io
import re
import time
import zipfile
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from typing import Dict, List, Optional

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


class MinerUService:
    """
    通过 MinerU 云端 API 解析 PDF 中的图片 / 表格。
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

    def extract_assets(
        self,
        pdf_path: str,
        pdf_id: str,
        output_dir: str,
    ) -> Dict[str, List[Path]]:
        """
        主入口：解析 PDF，返回图片 / 表格文件的本地路径列表。

        Args:
            pdf_path:   本地 PDF 文件路径
            pdf_id:     PDF 唯一标识（file hash）
            output_dir: 结果解压目标目录

        Returns:
            {"images": [Path, ...], "tables": [Path, ...]}
        """
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        # 如果已有缓存结果，直接返回
        if output_dir.exists():
            cached = self._scan_assets(output_dir)
            if cached["images"] or cached["tables"]:
                logger.info(f"[MinerU] 使用缓存结果: {output_dir}")
                return cached

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

        # Step 4: 扫描
        return self._scan_assets(output_dir)

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

    @staticmethod
    def _scan_assets(output_dir: Path) -> Dict[str, List[Path]]:
        """
        扫描解压后的目录，归类 images / tables。

        MinerU 典型结果目录::

            <output_dir>/
              *.md
              *.json
              images/
                *.png / *.jpg
              tables/
                *.html / *.csv
        """
        images: List[Path] = []
        tables: List[Path] = []

        for f in output_dir.rglob("*"):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            parent_name = f.parent.name.lower()

            if parent_name == "images" and ext in _IMAGE_EXTS:
                images.append(f)
            elif parent_name == "tables" and ext in _TABLE_EXTS:
                tables.append(f)
            elif ext in _IMAGE_EXTS and "image" in str(f).lower():
                images.append(f)
            elif ext in _TABLE_EXTS and "table" in str(f).lower():
                tables.append(f)

        images.sort(key=lambda p: p.name)
        tables.sort(key=lambda p: p.name)

        logger.info(f"[MinerU] 扫描结果: {len(images)} 张图片, {len(tables)} 个表格")
        return {"images": images, "tables": tables}

    @staticmethod
    def guess_page_number(file_path: Path) -> int:
        """
        从文件名猜测页码。
        MinerU 输出文件名通常包含页码信息，例如:
          - page_3_image_0.png  → page 3
          - table_5_1.html      → page 5
          - 3_0.png             → page 3
        """
        name = file_path.stem

        # 优先匹配 page_N 模式
        match = re.search(r"page[_-]?(\d+)", name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # 尝试匹配前导数字
        match = re.match(r"(\d+)", name)
        if match:
            return int(match.group(1))

        return 1
