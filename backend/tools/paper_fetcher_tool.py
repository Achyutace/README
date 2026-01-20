"""
工具 C: 特定论文精读（Paper Fetcher）

目标：当 Agent 发现某篇新论文很重要时，能够"抓过来读"
实现：根据 Paper ID 下载并解析 PDF
"""

import os
import tempfile
import requests
from typing import Optional, Dict
import fitz  # PyMuPDF
from langchain.tools import Tool


class PaperFetcherTool:
    """论文抓取工具 - 下载并快速解析论文"""
    
    def __init__(self, max_pages: int = 10, max_tokens: int = 4000):
        """
        Args:
            max_pages: 最多解析的页数（防止论文过长）
            max_tokens: 最大返回 Token 数（粗略估计）
        """
        self.max_pages = max_pages
        self.max_tokens = max_tokens
        self.temp_dir = tempfile.gettempdir()
    
    def fetch_and_parse(self, paper_id: str, sections: Optional[list] = None) -> Dict:
        """
        抓取并解析论文
        
        Args:
            paper_id: 论文 ID（格式：arxiv:2301.12345）
            sections: 要提取的章节（如 ['abstract', 'introduction', 'conclusion']）
                      如果为 None，则提取前 N 页或摘要
        
        Returns:
            {
                'paper_id': '...',
                'title': '...',
                'abstract': '...',
                'key_sections': {...},
                'full_text': '...' (截断的完整文本)
            }
        """
        # 提取 ArXiv ID
        if paper_id.startswith('arxiv:'):
            arxiv_id = paper_id.replace('arxiv:', '')
        else:
            arxiv_id = paper_id
        
        # 下载 PDF
        pdf_path = self._download_pdf(arxiv_id)
        
        if not pdf_path:
            return {
                'error': f'无法下载论文 {paper_id}',
                'paper_id': paper_id
            }
        
        try:
            # 解析 PDF
            parsed_data = self._parse_pdf(pdf_path, sections)
            parsed_data['paper_id'] = paper_id
            
            return parsed_data
        
        finally:
            # 清理临时文件
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    
    def _download_pdf(self, arxiv_id: str) -> Optional[str]:
        """下载 ArXiv PDF"""
        pdf_url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'
        
        try:
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            # 保存到临时文件
            temp_path = os.path.join(self.temp_dir, f'{arxiv_id}.pdf')
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            return temp_path
        
        except Exception as e:
            print(f"Download error: {e}")
            return None
    
    def _parse_pdf(self, pdf_path: str, sections: Optional[list] = None) -> Dict:
        """解析 PDF 并提取内容"""
        doc = fitz.open(pdf_path)
        
        # 提取标题（从第一页）
        first_page = doc[0]
        text = first_page.get_text()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        title = lines[0] if lines else 'Untitled'
        
        # 提取摘要和关键章节
        abstract = self._extract_abstract(doc)
        key_sections = {}
        
        if sections:
            for section in sections:
                content = self._extract_section(doc, section)
                if content:
                    key_sections[section] = content
        
        # 提取前 N 页的完整文本（截断）
        full_text_parts = []
        char_count = 0
        max_chars = self.max_tokens * 4  # 粗略估计：1 token ≈ 4 字符
        
        pages_count = len(doc)  # 在关闭前获取页数

        for i, page in enumerate(doc):
            if i >= self.max_pages:
                break

            page_text = page.get_text()
            if char_count + len(page_text) > max_chars:
                # 截断
                remaining = max_chars - char_count
                full_text_parts.append(page_text[:remaining] + '\n...[截断]')
                break

            full_text_parts.append(page_text)
            char_count += len(page_text)

        doc.close()

        return {
            'title': title,
            'abstract': abstract,
            'key_sections': key_sections,
            'full_text': '\n\n'.join(full_text_parts),
            'pages_extracted': min(pages_count, self.max_pages)
        }
    
    def _extract_abstract(self, doc: fitz.Document) -> str:
        """提取摘要"""
        # 在前几页中查找 "Abstract" 关键词
        for page in doc[:3]:
            text = page.get_text()
            
            # 查找 Abstract 章节
            if 'abstract' in text.lower():
                lines = text.split('\n')
                abstract_started = False
                abstract_lines = []
                
                for line in lines:
                    line_lower = line.lower().strip()
                    
                    if 'abstract' in line_lower:
                        abstract_started = True
                        continue
                    
                    if abstract_started:
                        # 停止条件：遇到下一个章节标题
                        if line_lower.startswith('1.') or line_lower.startswith('introduction'):
                            break
                        
                        if line.strip():
                            abstract_lines.append(line.strip())
                
                if abstract_lines:
                    return ' '.join(abstract_lines)[:1000]  # 限制长度
        
        return '未找到摘要'
    
    def _extract_section(self, doc: fitz.Document, section_name: str) -> str:
        """提取特定章节"""
        section_patterns = {
            'introduction': r'(1\.?\s*)?(introduction|background)',
            'method': r'(\d+\.?\s*)?(method|methodology|approach)',
            'experiments': r'(\d+\.?\s*)?(experiment|evaluation|results)',
            'conclusion': r'(\d+\.?\s*)?(conclusion|discussion)',
        }
        
        pattern = section_patterns.get(section_name.lower())
        if not pattern:
            return ''
        
        import re
        
        section_text = []
        section_started = False
        
        for page in doc:
            text = page.get_text()
            lines = text.split('\n')
            
            for line in lines:
                line_lower = line.lower().strip()
                
                # 检查是否匹配章节标题
                if re.match(pattern, line_lower, re.IGNORECASE):
                    section_started = True
                    continue
                
                if section_started:
                    # 停止条件：遇到下一个数字开头的章节
                    if re.match(r'^\d+\.', line_lower) and len(line_lower) < 100:
                        break
                    
                    if line.strip():
                        section_text.append(line.strip())
                    
                    # 限制长度
                    if len(' '.join(section_text)) > 2000:
                        break
            
            if len(' '.join(section_text)) > 2000:
                break
        
        return ' '.join(section_text)
    
    def as_langchain_tool(self) -> Tool:
        """转换为 LangChain Tool 格式"""
        return Tool(
            name="fetch_paper",
            description=(
                "下载并快速阅读一篇 ArXiv 论文。"
                "适用于：1) Agent 发现某篇论文与用户问题高度相关；"
                "2) 需要了解某篇论文的核心内容（摘要、方法、结论）；"
                "3) 对比多篇论文的方法或结果。"
                "输入：论文 ID（格式：arxiv:2301.12345）。"
                "输出：论文的标题、摘要和关键章节内容。"
                "注意：这是一个重型操作，会下载并解析 PDF，请谨慎使用。"
            ),
            func=lambda paper_id: self._format_result(self.fetch_and_parse(paper_id))
        )
    
    def _format_result(self, result: Dict) -> str:
        """格式化结果为字符串"""
        if 'error' in result:
            return result['error']
        
        formatted = [
            f"论文标题: {result.get('title', 'Unknown')}",
            f"\n摘要:\n{result.get('abstract', 'N/A')}",
        ]
        
        if result.get('key_sections'):
            formatted.append("\n关键章节:")
            for section, content in result['key_sections'].items():
                formatted.append(f"\n{section.upper()}:\n{content[:500]}...")
        
        formatted.append(f"\n已提取页数: {result.get('pages_extracted', 0)}")
        
        return '\n'.join(formatted)


# 便捷函数
def create_paper_fetcher_tool(max_pages: int = 10, max_tokens: int = 4000) -> PaperFetcherTool:
    """创建论文抓取工具实例"""
    return PaperFetcherTool(max_pages=max_pages, max_tokens=max_tokens)
