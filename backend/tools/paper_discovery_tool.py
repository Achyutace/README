"""
工具 B: Paper Discovery
目标：寻找本地库里没有的论文
实现：对接 Semantic Scholar 和 ArXiv API
"""

import os
import re
import datetime
import requests
from typing import List, Dict, Optional, Tuple
import arxiv
from langchain.tools import Tool


class PaperDiscoveryTool:
    """论文发现工具 - 查找和补充相关论文信息"""
    
    def __init__(self, max_results: int = 5):
        """
        Args:
            max_results: 每次搜索的最大结果数
        """
        self.max_results = max_results
        self.arxiv_client = arxiv.Client()

    def _calculate_sort_score(self, rank: int, total_results: int, citations: int, published_date: Optional[str]) -> Dict[str, float]:
        """
        计算论文的各项评分指标（不做排序，只提供分数供参考）
        
        Returns:
            包含以下分数的字典：
            - relevance_score: 相关性分数（0-1，基于搜索排名）
            - recency_score: 时效性分数（0-1，越新越高）
            - citation_impact: 引用影响力（对数化的引用数）
        """
        import math
        
        # 相关性分数 (基于搜索API返回的排名)
        relevance_score = 1.0 - (rank / max(total_results, 1))
        
        # 时效性分数
        recency_score = 0.0
        
        if published_date:
            try:
                pub_dt = datetime.datetime.strptime(published_date, '%Y-%m-%d')
                now = datetime.datetime.now()
                days_diff = max(0, (now - pub_dt).days)
                # 1年内: 1.0 -> 0.5, 之后逐渐降低
                recency_score = 1.0 / ((days_diff / 365.0) + 1.0)
            except:
                pass

        # 引用影响力 (对数化)
        citation_impact = math.log(max(citations, 0) + 1)
            
        return {
            'relevance_score': round(relevance_score, 3),
            'recency_score': round(recency_score, 3),
            'citation_impact': round(citation_impact, 2)
        }

    def search_papers(self, query: str, max_results: Optional[int] = None) -> List[Dict]:
        """
        搜索相关论文并补充相关信息 - 统一对外接口
        
        工作流程：
        1. 使用 ArXiv API 进行搜索
        2. 使用 Semantic Scholar 补充引用数据和相关性分数
        3. 返回带有完整信息的论文列表（保持原始顺序）
        
        Args:
            query: 搜索查询（支持自然语言或ArXiv语法）
            max_results: 返回结果数量
        
        Returns:
            论文列表，每个论文包含：
            - paper_id: 论文唯一标识
            - title: 标题
            - authors: 作者列表
            - abstract: 摘要
            - published: 发表日期
            - citations: 引用数
            - relevance_score: 相关性分数（0-1，基于搜索排名）
            - recency_score: 时效性分数（0-1，越新越高）
            - url: 论文链接
            - pdf_url: PDF下载链接
            - source: 数据来源
        """
        max_results = max_results or self.max_results
        
        # Step 1: ArXiv 搜索获取论文
        candidates = self._search_arxiv(query, max_results=max_results)
        
        if not candidates:
            # 如果 ArXiv 没有结果，尝试 Semantic Scholar
            return self._search_semantic_scholar(query, max_results)
        
        # Step 2: 使用 Semantic Scholar 补充引用数据和计算评分
        enriched = self._enrich_with_scores(candidates)
        
        return enriched

    def _search_arxiv(self, query: str, max_results: int) -> List[Dict]:
        """使用 ArXiv API 搜索论文"""
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results = []
            for paper in self.arxiv_client.results(search):
                arxiv_id = paper.entry_id.split('/abs/')[-1]
                
                results.append({
                    'paper_id': f'arxiv:{arxiv_id}',
                    'title': paper.title,
                    'authors': [author.name for author in paper.authors],
                    'abstract': paper.summary[:500] + '...' if len(paper.summary) > 500 else paper.summary,
                    'published': paper.published.strftime('%Y-%m-%d'),
                    'url': paper.entry_id,
                    'pdf_url': paper.pdf_url,
                    'citations': 0,  # 待补充
                    'source': 'arxiv'
                })
            
            return results
        
        except Exception as e:
            print(f"ArXiv search error: {e}")
            return []

    def _enrich_with_scores(self, papers: List[Dict]) -> List[Dict]:
        """使用 Semantic Scholar 批量补充引用数据，并计算各项评分"""
        if not papers:
            return papers
        
        # 准备批量查询的 ID
        s2_ids = []
        for paper in papers:
            raw_id = paper['paper_id'].replace('arxiv:', '').replace('ARXIV:', '')
            s2_ids.append(f"ARXIV:{raw_id}")
        
        # 批量查询 Semantic Scholar
        try:
            response = requests.post(
                "https://api.semanticscholar.org/graph/v1/paper/batch",
                json={"ids": s2_ids},
                params={"fields": "citationCount,publicationDate"},
                timeout=15
            )
            
            if response.status_code == 200:
                s2_data = response.json()
                
                # 补充引用数据并计算评分
                for idx, paper in enumerate(papers):
                    if idx < len(s2_data) and s2_data[idx]:
                        citations = s2_data[idx].get('citationCount', 0)
                        paper['citations'] = citations
                    
                    # 计算各项评分指标
                    scores = self._calculate_sort_score(
                        rank=idx,
                        total_results=len(papers),
                        citations=paper['citations'],
                        published_date=paper['published']
                    )
                    
                    # 添加评分到论文信息中
                    paper['relevance_score'] = scores['relevance_score']
                    paper['recency_score'] = scores['recency_score']
                    paper['citation_impact'] = scores['citation_impact']
        
        except Exception as e:
            print(f"Semantic Scholar enrichment warning: {e}")
            # 即使失败也返回原始数据，添加默认评分
            for idx, paper in enumerate(papers):
                scores = self._calculate_sort_score(
                    rank=idx,
                    total_results=len(papers),
                    citations=paper.get('citations', 0),
                    published_date=paper['published']
                )
                paper['relevance_score'] = scores['relevance_score']
                paper['recency_score'] = scores['recency_score']
                paper['citation_impact'] = scores['citation_impact']
        
        return papers

    def _search_semantic_scholar(self, query: str, max_results: int) -> List[Dict]:
        """使用 Semantic Scholar 搜索（作为备用数据源）"""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,authors,abstract,publicationDate,citationCount,url,openAccessPdf"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return []
                
            data = response.json()
            results = []
            
            for item in data.get('data', []):
                pdf_url = ""
                if item.get('openAccessPdf'):
                    pdf_url = item['openAccessPdf'].get('url', '')
                
                results.append({
                    'paper_id': f"s2:{item.get('paperId', '')}",
                    'title': item.get('title', ''),
                    'authors': [a['name'] for a in item.get('authors', [])],
                    'abstract': (item.get('abstract') or "")[:500] + "...",
                    'published': item.get('publicationDate', ''),
                    'citations': item.get('citationCount', 0),
                    'url': item.get('url', ''),
                    'pdf_url': pdf_url,
                    'source': 'semantic_scholar'
                })
            
            return results
            
        except Exception as e:
            print(f"Semantic Scholar search error: {e}")
            return []

    def get_paper_by_id(self, paper_id: str) -> Optional[Dict]:
        """
        根据论文 ID 获取详细信息
        
        Args:
            paper_id: 论文 ID（格式：arxiv:2301.12345 或 s2:xxxxx）
        
        Returns:
            论文详细信息
        """
        if paper_id.startswith('arxiv:'):
            arxiv_id = paper_id.replace('arxiv:', '')
            
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
                    'citations': 0,
                    'source': 'arxiv'
                }
            
            except Exception as e:
                print(f"Get paper error: {e}")
                return None
        
        return None

    def as_langchain_tool(self) -> Tool:
        """转换为 LangChain Tool 格式"""
        return Tool(
            name="search_papers",
            description=(
                "搜索学术论文并补充相关信息。\n"
                "输入：关键词或自然语言查询（也支持ArXiv语法，如 'cat:cs.CL' 或 'ti:\"transformer\"'）。\n"
                "输出：相关论文列表，包含标题、作者、摘要、发表日期、引用数、相关性评分、时效性评分等完整信息。\n"
                "评分说明：\n"
                "  - relevance_score: 与查询的相关性（0-1）\n"
                "  - recency_score: 论文时效性（0-1，越新越高）\n"
                "  - citation_impact: 引用影响力（对数化的引用数）\n"
                "适用场景：查找特定主题的论文、了解某个领域的研究现状、获取论文的详细信息。"
            ),
            func=self._tool_search
        )
    
    def _tool_search(self, query: str) -> str:
        """LangChain Tool 调用接口"""
        results = self.search_papers(query)
        return self._format_results(results)
    
    def _format_results(self, results: List[Dict]) -> str:
        """格式化结果为可读字符串"""
        if not results:
            return "未找到相关论文。"
        
        formatted = []
        for i, paper in enumerate(results, 1):
            authors_str = ', '.join(paper['authors'][:3])
            if len(paper['authors']) > 3:
                authors_str += ' et al.'
            
            # 构建评分信息
            score_info = f"相关性:{paper.get('relevance_score', 0)}, 时效性:{paper.get('recency_score', 0)}, 引用影响:{paper.get('citation_impact', 0)}"
            
            info = [
                f"[{i}] {paper['title']}",
                f"    作者: {authors_str}",
                f"    发表: {paper.get('published', 'N/A')}",
                f"    引用数: {paper.get('citations', 0)}",
                f"    评分: {score_info}",
                f"    摘要: {paper['abstract'][:200]}...",
                f"    链接: {paper['url']}",
                f"    PDF: {paper.get('pdf_url', 'N/A')}"
            ]
            
            formatted.append('\n'.join(info) + '\n')
        
        return "\n".join(formatted)


# 便捷函数
def create_paper_discovery_tool(max_results: int = 5) -> PaperDiscoveryTool:
    """创建论文发现工具实例"""
    return PaperDiscoveryTool(max_results=max_results)

