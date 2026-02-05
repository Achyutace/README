"""
工具包 - 学术 Agent 专用工具
"""

from .web_search_tool import WebSearchTool
from .paper_discovery_tool import PaperDiscoveryTool

__all__ = [
    'WebSearchTool',
    'PaperDiscoveryTool',
    'PaperFetcherTool'
]
