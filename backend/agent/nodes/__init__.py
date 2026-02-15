"""
Agent Nodes — LangGraph 工作流节点

Router + Expert 架构：
- router: 路由层，持有上下文，闲聊直接回复，学术问题分发给专家
- paper_expert: 当前论文专家，严格基于 RAG 结果回答
- search_expert: 外部搜索专家，基于联网/文献库搜索结果回答
"""

from agent.nodes.router import router_node
from agent.nodes.paper_expert import paper_expert_node
from agent.nodes.search_expert import search_expert_node

__all__ = [
    "router_node",
    "paper_expert_node",
    "search_expert_node",
]
