"""
工具 A: Web Search
目标：回答"最新进展"、"背景知识"或"某个概念的定义"
实现：对接 Tavily API
"""

from typing import List, Dict, Optional, Literal
from langchain.tools import Tool

from config import settings


class WebSearchTool:
    """网络搜索工具 - 使用 Tavily API"""

    def __init__(self, api_key: Optional[str] = None, max_results: int = 15):
        """
        Args:
            api_key: Tavily API Key
            max_results: 最大返回结果数
        """
        self.api_key = api_key or settings.tavily.api_key
        self.max_results = max_results

        # 初始化 Tavily Client
        if self.api_key:
            try:
                from tavily import TavilyClient
                self.tavily_client = TavilyClient(api_key=self.api_key)
                self.has_client = True
            except ImportError:
                print("Warning: tavily-python not installed. Install with: pip install tavily-python")
                self.tavily_client = None
                self.has_client = False
        else:
            self.tavily_client = None
            self.has_client = False
            print("Warning: Tavily API key not found. Web search will use demo mode.")
    
    def search(self, 
               query: str, 
               time_range: Optional[Literal["day", "week", "month", "year"]] = None,
               topic: Optional[Literal["general", "news"]] = "general",
               include_domains: Optional[List[str]] = None,
               exclude_domains: Optional[List[str]] = None) -> List[Dict]:
        """
        执行网络搜索
        
        Args:
            query: 搜索查询
            time_range: 时间范围限制 ("day", "week", "month", "year")
                       - "day": 最近24小时
                       - "week": 最近一周
                       - "month": 最近一个月
                       - "year": 最近一年
            topic: 搜索主题类型
                  - "general": 通用搜索（默认）
                  - "news": 新闻搜索
            include_domains: 仅搜索这些域名（如 ["arxiv.org", "scholar.google.com"]）
            exclude_domains: 排除这些域名
        
        Returns:
            [
                {
                    'title': '...',
                    'url': '...',
                    'snippet': '...',
                    'published_date': '...',  # 如果可用
                    'source': 'web'
                },
                ...
            ]
        """
        if self.has_client and self.tavily_client:
            try:
                # 使用原生 Tavily SDK
                search_params = {
                    "query": query,
                    "max_results": self.max_results
                }
                
                # 时间范围限制
                if time_range:
                    search_params["days"] = {
                        "day": 1,
                        "week": 7,
                        "month": 30,
                        "year": 365
                    }.get(time_range, None)
                
                # 主题类型
                if topic:
                    search_params["topic"] = topic
                
                # 域名过滤
                if include_domains:
                    search_params["include_domains"] = include_domains
                if exclude_domains:
                    search_params["exclude_domains"] = exclude_domains
                
                response = self.tavily_client.search(**search_params)
                
                # 格式化结果
                cleaned_results = []
                for result in response.get("results", []):
                    cleaned_results.append({
                        'title': result.get('title', 'No title'),
                        'url': result.get('url', ''),
                        'snippet': result.get('content', ''),
                        'published_date': result.get('published_date', ''),
                        'score': result.get('score', 0),
                        'source': 'web'
                    })
                
                return cleaned_results
            
            except Exception as e:
                error_msg = str(e)
                # 401 错误表示 API 密钥无效
                if "401" in error_msg or "Unauthorized" in error_msg:
                    print(f"Tavily API 密钥无效或未授权。请检查 config.yaml 中的 tavily.api_key 配置。")
                else:
                    print(f"Tavily search error: {e}")
                return self._demo_search(query)
        
        return self._demo_search(query)
    
    def search_academic(self, query: str, time_range: Optional[str] = "year") -> List[Dict]:
        """
        搜索学术信息（快捷方法）
        
        自动限制搜索范围到学术网站，并设置时间范围
        
        Args:
            query: 搜索查询
            time_range: 时间范围（默认一年内）
        
        Returns:
            搜索结果列表
        """
        academic_domains = [
            "arxiv.org",
            "scholar.google.com",
            "semanticscholar.org",
            "pubmed.ncbi.nlm.nih.gov",
            "ieee.org",
            "acm.org",
            "springer.com",
            "sciencedirect.com"
        ]
        
        return self.search(
            query=query,
            time_range=time_range,
            include_domains=academic_domains
        )
    
    def _demo_search(self, query: str) -> List[Dict]:
        """返回模拟搜索结果"""
        return [
            {
                'title': f'搜索结果 1: {query}',
                'url': 'https://example.com/1',
                'snippet': f'这是关于"{query}"的最新信息。根据最近的研究和报道...',
                'source': 'web_demo'
            },
            {
                'title': f'搜索结果 2: {query} 详解',
                'url': 'https://example.com/2',
                'snippet': f'深入分析"{query}"的背景、发展和应用...',
                'source': 'web_demo'
            },
            {
                'title': f'{query} - 维基百科',
                'url': 'https://en.wikipedia.org/wiki/' + query.replace(' ', '_'),
                'snippet': f'{query}是一个重要的概念，涉及多个领域...',
                'source': 'web_demo'
            }
        ]
    
    def as_langchain_tool(self) -> Tool:
        """转换为 LangChain Tool 格式（支持时间过滤）"""
        return Tool(
            name="web_search",
            description=(
                "搜索互联网上的最新信息、背景知识或概念定义。支持时间过滤。"
                "适用于：1) 查询论文中未提及的新概念；"
                "2) 获取最新的研究进展（推荐使用时间限制）；"
                "3) 了解某个技术或方法的背景。"
                "输入格式：可以是简单字符串，或 JSON 格式指定参数：\n"
                "  简单模式: '查询内容'\n"
                "  高级模式: '{\"query\": \"查询内容\", \"time_range\": \"month\", \"topic\": \"general\"}'\n"
                "time_range 可选值: day, week, month, year\n"
                "topic 可选值: general, news\n"
                "输出：包含标题、链接、摘要和发布日期的搜索结果列表。"
            ),
            func=lambda q: self._format_results(self._parse_and_search(q))
        )
    
    def _parse_and_search(self, query_input: str) -> List[Dict]:
        """解析查询输入并执行搜索"""
        import json
        
        # 尝试解析为 JSON
        try:
            params = json.loads(query_input)
            if isinstance(params, dict) and 'query' in params:
                return self.search(
                    query=params['query'],
                    time_range=params.get('time_range'),
                    topic=params.get('topic'),
                    include_domains=params.get('include_domains'),
                    exclude_domains=params.get('exclude_domains')
                )
        except (json.JSONDecodeError, TypeError):
            pass
        
        # 简单字符串查询
        return self.search(query_input)
    
    def _format_results(self, results: List[Dict]) -> str:
        """格式化结果为字符串"""
        if not results:
            return "未找到相关信息。"
        
        formatted = []
        for i, result in enumerate(results, 1):
            parts = [
                f"[{i}] {result['title']}",
                f"    链接: {result['url']}",
                f"    摘要: {result['snippet']}"
            ]
            
            # 发布日期
            if result.get('published_date'):
                parts.append(f"    发布日期: {result['published_date']}")
            
            formatted.append('\n'.join(parts) + '\n')
        
        return "\n".join(formatted)


# 便捷函数
def create_web_search_tool(api_key: Optional[str] = None, max_results: int = 5) -> WebSearchTool:
    """创建网络搜索工具实例"""
    return WebSearchTool(api_key=api_key, max_results=max_results)
