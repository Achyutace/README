"""
论文抓取工具 - 从 ArXiv 下载并解析论文
"""

import os
import re
import requests
import tempfile
from typing import Dict, Optional
from pathlib import Path

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


class PaperFetcherTool:
    """
    论文抓取工具

    功能：
    - 从 ArXiv 下载 PDF
    - 解析 PDF 内容
    - 提取摘要和关键章节
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Args:
            cache_dir: 缓存目录，用于存储下载的 PDF
        """
        self.cache_dir = cache_dir or tempfile.gettempdir()
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

    def fetch_and_parse(self, arxiv_id: str) -> Dict:
        """
        下载并解析 ArXiv 论文

        Args:
            arxiv_id: ArXiv 论文 ID（如 '2301.00001' 或 'arxiv:2301.00001'）

        Returns:
            {
                'success': bool,
                'arxiv_id': str,
                'title': str,
                'abstract': str,
                'content': str,  # 全文（截断）
                'sections': [...],  # 章节列表
                'error': str (如果失败)
            }
        """
        # 清理 ArXiv ID
        arxiv_id = self._clean_arxiv_id(arxiv_id)

        if not arxiv_id:
            return {
                'success': False,
                'error': 'Invalid ArXiv ID format'
            }

        try:
            # 1. 获取论文元数据
            metadata = self._fetch_metadata(arxiv_id)

            # 2. 下载 PDF
            pdf_path = self._download_pdf(arxiv_id)

            if not pdf_path:
                return {
                    'success': False,
                    'arxiv_id': arxiv_id,
                    'title': metadata.get('title', ''),
                    'abstract': metadata.get('abstract', ''),
                    'content': '',
                    'error': 'Failed to download PDF'
                }

            # 3. 解析 PDF
            content, sections = self._parse_pdf(pdf_path)

            return {
                'success': True,
                'arxiv_id': arxiv_id,
                'title': metadata.get('title', ''),
                'abstract': metadata.get('abstract', ''),
                'content': content[:10000],  # 截断为前 10000 字符
                'sections': sections,
                'pdf_path': pdf_path
            }

        except Exception as e:
            return {
                'success': False,
                'arxiv_id': arxiv_id,
                'error': str(e)
            }

    def _clean_arxiv_id(self, arxiv_id: str) -> Optional[str]:
        """清理并验证 ArXiv ID"""
        if not arxiv_id:
            return None

        # 移除常见前缀
        arxiv_id = arxiv_id.strip()
        arxiv_id = re.sub(r'^(arxiv:|arXiv:|https?://arxiv\.org/abs/)', '', arxiv_id)
        arxiv_id = re.sub(r'^(https?://arxiv\.org/pdf/)', '', arxiv_id)
        arxiv_id = re.sub(r'\.pdf$', '', arxiv_id)

        # 验证格式（支持新旧两种格式）
        # 新格式: YYMM.NNNNN (如 2301.00001)
        # 旧格式: category/YYMMNNN (如 cs.AI/0701001)
        if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', arxiv_id):
            return arxiv_id
        if re.match(r'^[a-z-]+(\.[A-Z]{2})?/\d{7}(v\d+)?$', arxiv_id):
            return arxiv_id

        return None

    def _fetch_metadata(self, arxiv_id: str) -> Dict:
        """从 ArXiv API 获取论文元数据"""
        try:
            import arxiv

            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(search.results(), None)

            if paper:
                return {
                    'title': paper.title,
                    'abstract': paper.summary,
                    'authors': [a.name for a in paper.authors],
                    'published': str(paper.published),
                    'categories': paper.categories
                }
        except Exception as e:
            print(f"Failed to fetch metadata: {e}")

        return {}

    def _download_pdf(self, arxiv_id: str) -> Optional[str]:
        """下载 ArXiv PDF"""
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        pdf_path = os.path.join(self.cache_dir, f"{arxiv_id.replace('/', '_')}.pdf")

        # 如果已缓存，直接返回
        if os.path.exists(pdf_path):
            return pdf_path

        try:
            response = requests.get(pdf_url, timeout=30, stream=True)
            response.raise_for_status()

            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return pdf_path

        except Exception as e:
            print(f"Failed to download PDF: {e}")
            return None

    def _parse_pdf(self, pdf_path: str) -> tuple:
        """
        解析 PDF 内容

        Returns:
            (content: str, sections: List[Dict])
        """
        if not HAS_FITZ:
            return self._parse_pdf_fallback(pdf_path)

        try:
            doc = fitz.open(pdf_path)

            content_parts = []
            sections = []
            current_section = None

            for page_num, page in enumerate(doc, 1):
                text = page.get_text()
                content_parts.append(text)

                # 简单的章节检测
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    # 检测常见的章节标题模式
                    if re.match(r'^(\d+\.?\s+)?(Abstract|Introduction|Related Work|Method|Methodology|Experiment|Results|Discussion|Conclusion|References)s?$', line, re.IGNORECASE):
                        if current_section:
                            sections.append(current_section)
                        current_section = {
                            'title': line,
                            'page': page_num,
                            'content': ''
                        }

            doc.close()

            if current_section:
                sections.append(current_section)

            return '\n'.join(content_parts), sections

        except Exception as e:
            print(f"PDF parsing error: {e}")
            return '', []

    def _parse_pdf_fallback(self, pdf_path: str) -> tuple:
        """不使用 PyMuPDF 的备用解析方法"""
        try:
            import pdfplumber

            content_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ''
                    content_parts.append(text)

            return '\n'.join(content_parts), []

        except ImportError:
            return '', []
        except Exception as e:
            print(f"Fallback PDF parsing error: {e}")
            return '', []

    def get_langchain_tool(self):
        """
        获取 LangChain Tool 格式的工具

        Returns:
            langchain Tool 实例
        """
        from langchain.tools import Tool

        return Tool(
            name="fetch_paper",
            func=lambda arxiv_id: self.fetch_and_parse(arxiv_id),
            description="从 ArXiv 下载并解析论文。输入 ArXiv 论文 ID（如 '2301.00001'），返回论文的标题、摘要和主要内容。"
        )
