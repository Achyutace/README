"""
Paper Expert — 当前论文专家

1. 根据 Router 传来的 task_description 执行 RAG 检索
2. 严格基于当前论文的检索结果生成回答
3. 如果检索结果不足以回答，如实告知用户而非捏造
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState

_SYSTEM = (
    "你是一位严谨的论文阅读专家。你只能基于下方提供的论文原文片段来回答问题。"
    "如果提供的片段无法回答问题，请明确告诉用户'当前论文中未找到相关信息'，"
    "不要编造任何论文中不存在的内容。"
)

_ANSWER_PROMPT = """## 任务
{task}

## 论文原文片段
{context_block}

## 输出要求
- 使用 Markdown 格式回答，对引用的内容在句末标注 `[n]`
- 输出纯 JSON（不要代码块包裹）:

{{
  "answer": "你的回答 ...",
  "citations": [
    {{
      "id": 1,
      "source_type": "local",
      "title": "章节名",
      "snippet": "引用的关键原文",
      "page": "页码或 null"
    }}
  ]
}}"""


def paper_expert_node(state: AgentState, llm, rag_service) -> dict:
    """论文专家节点 — RAG 检索 + 基于论文回答。"""

    task = state.get("task_description") or state["user_query"]
    paper_id = state["paper_id"]
    user_id = state["user_id"]

    # 1. RAG 检索
    results = rag_service.retrieve(
        query=task, file_hash=paper_id, user_id=user_id, top_k=5
    )

    # 2. 构建上下文
    context_block = _format_context(results)

    # 3. 生成回答
    prompt = _ANSWER_PROMPT.format(task=task, context_block=context_block)

    try:
        resp = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ])
        data = json.loads(_strip_fence(resp.content))
        answer = data.get("answer", "")
        citations = data.get("citations", [])
    except json.JSONDecodeError:
        answer = resp.content if "resp" in dir() else "生成失败"
        citations = []
    except Exception as e:
        print(f"[paper_expert] error: {e}")
        answer = "抱歉，论文专家生成回答时出错。"
        citations = []

    return {
        "steps": ["论文专家"],
        "current_step": f"基于 {len(results)} 条检索结果生成回答",
        "local_context": results,
        "final_response": answer,
        "citations": citations,
    }


# ==================== 工具函数 ====================

def _format_context(results: list) -> str:
    if not results:
        return "（未检索到相关内容）"
    parts = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        section = r.get("section", meta.get("section", "unknown"))
        page = r.get("page", meta.get("page", "N/A"))
        parts.append(f"[片段 {i}] 章节: {section} | 页码: {page}\n{r['parent_content']}")
    return "\n\n".join(parts)


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()
