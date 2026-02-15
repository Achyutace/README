"""
Router — 路由层

唯一持有对话历史上下文的节点。职责：
1. 闲聊 → 直接回复，写入 final_response
2. 学术问题 → 理解意图，结合上下文改写 query，生成自包含的
   task_description 分发给专家（下游专家不持有对话历史）
   - 当前论文相关 → intent="paper"
   - 需要外部知识 → intent="search"
"""

import json

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent.state import AgentState

_SYSTEM = (
    "你是一个学术论文阅读助手的路由调度器。\n"
    "你需要理解用户意图，并在必要时根据对话历史补全用户提问中的指代和省略并且添加上下文支持，"
    "使下游处理器无需上下文也能完整理解任务。"
)

_ROUTE_PROMPT = """请分析用户的最新提问，判断其意图并按要求输出 JSON（不要代码块包裹）。

## 对话历史（最近几轮）
{history_block}

## 用户最新提问
{user_query}

## 你的工作
1. **理解意图** — 判断用户提问属于 chat / paper / search 中的哪一类。
2. **改写查询** — 如果意图不是 chat，请结合对话历史将用户的提问改写成一段
   **自包含、无指代**的任务描述。  
   - 将"它""这个方法""上面提到的"等指代词替换为对话中实际提及的具体概念或术语。  
   - 保留用户的核心提问方向，不要扩展也不要缩减问题范围。  
   - 使用和用户相同的语言（中文提问就用中文改写，英文提问就用英文改写）。  
   - 如果用户提问已经足够清晰完整，直接保留原文即可，无需强行改写。

## 意图类型
- **chat**: 闲聊、问候、与论文/学术无关的话题。你需要直接给出友好的回复。
- **paper**: 关于当前正在阅读的这篇论文的具体问题（内容理解、方法细节、实验结果、公式推导等）。需要从论文原文中检索信息来回答。
- **search**: 需要论文之外的外部知识才能回答的问题（对比其他方法、领域综述、最新进展、背景知识科普等）。需要联网搜索或查阅学术数据库。

## 输出格式
{{
  "intent": "chat 或 paper 或 search",
  "response": "如果 intent 是 chat，在这里直接写你的回复；否则留空字符串",
  "task": "如果 intent 不是 chat，在这里用简洁的英文描述检索/回答任务，方便下游专家节点理解；否则留空字符串"
}}"""


def router_node(state: AgentState, llm) -> dict:
    """路由节点 — 意图识别 + 闲聊处理 + 任务分发。"""

    history_block = _format_history(state.get("chat_history", []))
    user_query = state["user_query"]

    prompt = _ROUTE_PROMPT.format(
        history_block=history_block or "（无历史记录）",
        user_query=user_query,
    )

    try:
        resp = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ])
        data = json.loads(_strip_fence(resp.content))
    except Exception as e:
        # 解析失败，降级为 paper
        print(f"[router] parse error, fallback to paper: {e}")
        return {
            "steps": ["路由"],
            "current_step": "意图解析失败，默认走论文专家",
            "intent": "paper",
            "task_description": user_query,
        }

    intent = data.get("intent", "paper")

    if intent == "chat":
        return {
            "steps": ["路由"],
            "current_step": "闲聊，直接回复",
            "intent": "chat",
            "task_description": "",
            "final_response": data.get("response", ""),
            "citations": [],
        }

    # 改写后的 task；若 LLM 返回空则回退到原始 query
    rewritten = (data.get("task") or "").strip() or user_query

    return {
        "steps": ["路由"],
        "current_step": f"分发至 {'论文专家' if intent == 'paper' else '搜索专家'}",
        "intent": intent,
        "task_description": rewritten,
    }


# ==================== 工具函数 ====================

def _format_history(history: list, max_turns: int = 4) -> str:
    lines = []
    for msg in history[-max_turns:]:
        role = "用户" if msg["role"] == "user" else "助手"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()
