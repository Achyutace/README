"""
Search Expert — 外部搜索专家

职责：
1. 根据 Router 传来的 task_description 执行联网搜索 / 学术论文搜索
2. 检索用户文献库中的相关内容（跨库 RAG）
3. 基于搜索结果 + 文献库结果归纳回答
4. 标注所有来源的引用信息（标题、URL、论文来源等）
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from agent.state import AgentState
from services.websearch_service import web_search_service

_SYSTEM = (
    "你是一位学术搜索专家。你的任务是综合外部搜索结果与用户文献库中的相关内容，"
    "为用户提供准确、有来源的回答。回答中的每个关键观点都必须标注引用来源。"
)

_ANSWER_PROMPT = """## 任务
{task}

## 外部搜索结果
{web_block}

## 用户文献库中的相关内容
{library_block}

## 输出要求
- 使用 Markdown 格式回答，对引用的内容在句末标注 `[n]`
- 优先使用有明确来源的信息，文献库内容和外部搜索结果都可以引用
- 输出纯 JSON（不要代码块包裹）:

{{
  "answer": "你的回答 ...",
  "citations": [
    {{
      "id": 1,
      "source_type": "external 或 library",
      "title": "来源标题",
      "snippet": "引用的关键内容",
      "url": "来源链接或 null",
      "file_hash": "文献库来源的 file_hash 或 null"
    }}
  ]
}}"""


def search_expert_node(state: AgentState, llm, rag_service=None) -> dict:
    """搜索专家节点 — 外部搜索 + 文献库 RAG + 归纳回答"""

    task = state.get("task_description") or state["user_query"]
    user_id = state.get("user_id")
    current_paper = state.get("paper_id")

    # 1. 外部搜索（网页 + 学术论文）
    search_results = _do_search(task)

    # 2. 文献库 RAG（基于 abstract 跨库检索，排除当前论文）
    library_results = []
    if rag_service and user_id:
        try:
            library_results = rag_service.retrieve_related_papers(
                query=task,
                user_id=user_id,
                exclude_file_hash=current_paper,
                top_k=6,
            )
        except Exception as e:
            print(f"[search_expert] library RAG failed: {e}")

    # 3. 构建上下文
    web_block = _format_web_results(search_results)
    library_block = _format_library_results(library_results)

    # 4. 生成回答
    prompt = _ANSWER_PROMPT.format(
        task=task,
        web_block=web_block,
        library_block=library_block,
    )

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
        print(f"[search_expert] error: {e}")
        answer = "抱歉，搜索专家生成回答时出错。"
        citations = []

    return {
        "steps": ["搜索专家"],
        "current_step": (
            f"基于 {len(search_results)} 条搜索结果"
            f"和 {len(library_results)} 条文献库结果生成回答"
        ),
        "external_context": search_results,
        "library_context": library_results,
        "final_response": answer,
        "citations": citations,
    }


# ==================== 工具函数 ====================

def _do_search(query: str) -> list:
    """同时执行网页搜索和学术论文搜索，合并结果。"""
    results = []
    try:
        results.extend(web_search_service.search_web(query))
    except Exception as e:
        print(f"[search_expert] web_search failed: {e}")
    try:
        results.extend(web_search_service.search_papers(query))
    except Exception as e:
        print(f"[search_expert] search_papers failed: {e}")
    return results


def _format_web_results(results: list) -> str:
    if not results:
        return "（未搜索到相关结果）"
    parts = []
    for i, item in enumerate(results[:8], 1):
        title = item.get("title", "未命名")
        url = item.get("url", "")
        snippet = item.get("snippet", item.get("abstract", ""))
        parts.append(f"[结果 {i}] {title}\n链接: {url}\n{snippet}")
    return "\n\n".join(parts)


def _format_library_results(results: list) -> str:
    if not results:
        return "（用户文献库中未找到相关论文）"
    parts = []
    for i, r in enumerate(results, 1):
        file_hash = r.get("file_hash", "unknown")
        snippet = r.get("abstract_snippet", "")
        score = r.get("score", 0)
        parts.append(
            f"[文献 {i}] file_hash: {file_hash} | 相似度: {score:.2f}\n"
            f"摘要片段: {snippet}"
        )
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
