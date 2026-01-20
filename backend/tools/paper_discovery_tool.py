"""
工具 B: 论文发现（Paper Discovery）

目标：寻找本地库里没有的论文
实现：对接 Semantic Scholar 和 ArXiv API
"""

import os
import re
from typing import List, Dict, Optional
import arxiv
from langchain.tools import Tool


class PaperDiscoveryTool:
    """论文发现工具 - 使用 ArXiv 和 Semantic Scholar API"""
    
    def __init__(self, max_results: int = 5):
        """
        Args:
            max_results: 每次搜索的最大结果数
        """
        self.max_results = max_results
        self.arxiv_client = arxiv.Client()
    
    def search_arxiv(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """
        在 ArXiv 上搜索论文
        
        Args:
            query: 搜索查询（关键词、作者、标题等）
            max_results: 返回结果数量
        
        Returns:
            [
                {
                    'paper_id': 'arxiv:2301.12345',
                    'title': '...',
                    'authors': ['Author 1', 'Author 2'],
                    'abstract': '...',
                    'published': '2023-01-15',
                    'url': 'https://arxiv.org/abs/2301.12345',
                    'pdf_url': 'https://arxiv.org/pdf/2301.12345.pdf',
                    'source': 'arxiv'
                },
                ...
            ]
        """
        max_results = max_results or self.max_results
        
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results = []
            for paper in self.arxiv_client.results(search):
                # 提取 ArXiv ID
                arxiv_id = paper.entry_id.split('/abs/')[-1]
                
                results.append({
                    'paper_id': f'arxiv:{arxiv_id}',
                    'title': paper.title,
                    'authors': [author.name for author in paper.authors],
                    'abstract': paper.summary[:500] + '...' if len(paper.summary) > 500 else paper.summary,
                    'published': paper.published.strftime('%Y-%m-%d'),
                    'url': paper.entry_id,
                    'pdf_url': paper.pdf_url,
                    'source': 'arxiv'
                })
            
            return results
        
        except Exception as e:
            print(f"ArXiv search error: {e}")
            return self._demo_search(query)
    
    def search_by_keywords(self, keywords: List[str], max_results: Optional[int] = None) -> List[Dict]:
        """
        按关键词搜索论文
        
        Args:
            keywords: 关键词列表
            max_results: 返回结果数量
        
        Returns:
            论文列表
        """
        # 构建查询字符串
        query = ' AND '.join([f'"{kw}"' for kw in keywords])
        return self.search_arxiv(query, max_results)
    
    def get_paper_by_id(self, paper_id: str) -> Optional[Dict]:
        """
        根据论文 ID 获取详细信息
        
        Args:
            paper_id: 论文 ID（格式：arxiv:2301.12345）
        
        Returns:
            论文详细信息
        """
        # 提取 ArXiv ID
        if paper_id.startswith('arxiv:'):
            arxiv_id = paper_id.replace('arxiv:', '')
        else:
            arxiv_id = paper_id
        
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(self.arxiv_client.results(search))
            
            return {
                'paper_id': f'arxiv:{arxiv_id}',
                'title': paper.title,
                'authors': [author.name for author in paper.authors],
                'abstract': paper.summary,
                'published': paper.published.strftime('%Y-%m-%d'),
                'url': paper.entry_id,
                'pdf_url': paper.pdf_url,
                'source': 'arxiv'
            }
        
        except Exception as e:
            print(f"Get paper error: {e}")
            return None
    
    def _demo_search(self, query: str) -> List[Dict]:
        """演示模式：返回模拟搜索结果"""
        return [
            {
                'paper_id': 'arxiv:2301.00001',
                'title': f'Recent Advances in {query}',
                'authors': ['John Doe', 'Jane Smith'],
                'abstract': f'本文综述了{query}领域的最新进展，包括方法、应用和未来方向...',
                'published': '2023-01-01',
                'url': 'https://arxiv.org/abs/2301.00001',
                'pdf_url': 'https://arxiv.org/pdf/2301.00001.pdf',
                'source': 'arxiv_demo'
            },
            {
                'paper_id': 'arxiv:2302.00002',
                'title': f'A Novel Approach to {query}',
                'authors': ['Alice Brown', 'Bob Wilson'],
                'abstract': f'我们提出了一种新的方法来解决{query}中的关键问题，实验表明...',
                'published': '2023-02-15',
                'url': 'https://arxiv.org/abs/2302.00002',
                'pdf_url': 'https://arxiv.org/pdf/2302.00002.pdf',
                'source': 'arxiv_demo'
            }
        ]
    
    def as_langchain_tool(self) -> Tool:
        """转换为 LangChain Tool 格式"""
        return Tool(
            name="search_papers",
            description=(
                "在 ArXiv 上搜索学术论文。"
                "适用于：1) 查找特定主题的相关论文；"
                "2) 寻找某个作者的最新工作；"
                "3) 探索某个领域的前沿研究。"
                "输入：搜索查询字符串（可以是关键词、作者名或论文主题）。"
                "输出：包含论文标题、作者、摘要、发表日期和链接的论文列表。"
            ),
            func=lambda q: self._format_results(self.search_arxiv(q))
        )
    
    def _format_results(self, results: List[Dict]) -> str:
        """格式化结果为字符串"""
        if not results:
            return "未找到相关论文。"
        
        formatted = []
        for i, paper in enumerate(results, 1):
            authors_str = ', '.join(paper['authors'][:3])
            if len(paper['authors']) > 3:
                authors_str += ' et al.'
            
            formatted.append(
                f"[{i}] {paper['title']}\n"
                f"    作者: {authors_str}\n"
                f"    发表: {paper['published']}\n"
                f"    摘要: {paper['abstract'][:200]}...\n"
                f"    链接: {paper['url']}\n"
                f"    PDF: {paper['pdf_url']}\n"
            )
        
        return "\n".join(formatted)


# 便捷函数
def create_paper_discovery_tool(max_results: int = 5) -> PaperDiscoveryTool:
    """创建论文发现工具实例"""
    return PaperDiscoveryTool(max_results=max_results)
