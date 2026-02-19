"""
Agent State
—— LangGraph 工作流各节点间共享的状态结构。
"""

import operator
import uuid
from typing import Annotated, Dict, List, TypedDict


class AgentState(TypedDict):
    # ---- 输入（调用方填充，节点不修改）----
    user_query: str
    user_id: uuid.UUID
    paper_id: str
    chat_history: List[Dict]

    # ---- Router 输出 ----
    intent: str              # "chat" | "paper" | "search"
    task_description: str    # Router 给专家节点的任务描述 / 改写后的检索词

    # ---- Paper Expert ----
    local_context: List[Dict]

    # ---- Search Expert ----
    external_context: List[Dict]
    library_context: List[Dict]   # 文献库跨库 RAG 检索结果

    # ---- 最终输出 ----
    final_response: str
    citations: List[Dict]

    # ---- 追踪 ----
    steps: Annotated[List[str], operator.add]
    current_step: str
