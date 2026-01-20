"""
工具 A: 广义信息搜索（Web Search）

目标：回答"最新进展"、"背景知识"或"某个概念的定义"
实现：对接 Tavily API
"""

import os
from typing import List, Dict, Optional
from langchain.tools import Tool
from langchain_community.tools.tavily_search import TavilySearchResults


class WebSearchTool:
    """网络搜索工具 - 使用 Tavily API"""
    
    def __init__(self, api_key: Optional[str] = None, max_results: int = 5):
        """
        Args:
            api_key: Tavily API Key（如果为 None，从环境变量读取）
            max_results: 最大返回结果数
        """
        self.api_key = api_key or os.getenv('TAVILY_API_KEY')
        self.max_results = max_results
        
        # 初始化 Tavily 搜索
        if self.api_key:
            self.search_tool = TavilySearchResults(
                api_key=self.api_key,
                max_results=max_results
            )
        else:
            self.search_tool = None
            print("Warning: Tavily API key not found. Web search will use demo mode.")
    
    def search(self, query: str) -> List[Dict]:
        """
        执行网络搜索
        
        Args:
            query: 搜索查询
        
        Returns:
            [
                {
                    'title': '...',
                    'url': '...',
                    'snippet': '...',
                    'source': 'web'
                },
                ...
            ]
        """
        if self.search_tool:
            try:
                results = self.search_tool.invoke({"query": query})
                
                # 清洗结果
                cleaned_results = []
                for result in results:
                    if isinstance(result, dict):
                        cleaned_results.append({
                            'title': result.get('title', 'No title'),
                            'url': result.get('url', ''),
                            'snippet': result.get('content', result.get('snippet', '')),
                            'source': 'web'
                        })
                
                return cleaned_results[:self.max_results]
            
            except Exception as e:
                print(f"Tavily search error: {e}")
                return self._demo_search(query)
        
        return self._demo_search(query)
    
    def _demo_search(self, query: str) -> List[Dict]:
        """演示模式：返回模拟搜索结果"""
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
        """转换为 LangChain Tool 格式"""
        return Tool(
            name="web_search",
            description=(
                "搜索互联网上的最新信息、背景知识或概念定义。"
                "适用于：1) 查询论文中未提及的新概念；"
                "2) 获取最新的研究进展；"
                "3) 了解某个技术或方法的背景。"
                "输入：搜索查询字符串。"
                "输出：包含标题、链接和摘要的搜索结果列表。"
            ),
            func=lambda q: self._format_results(self.search(q))
        )
    
    def _format_results(self, results: List[Dict]) -> str:
        """格式化结果为字符串"""
        if not results:
            return "未找到相关信息。"
        
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(
                f"[{i}] {result['title']}\n"
                f"    链接: {result['url']}\n"
                f"    摘要: {result['snippet']}\n"
            )
        
        return "\n".join(formatted)


# 便捷函数
def create_web_search_tool(api_key: Optional[str] = None, max_results: int = 5) -> WebSearchTool:
    """创建网络搜索工具实例"""
    return WebSearchTool(api_key=api_key, max_results=max_results)
