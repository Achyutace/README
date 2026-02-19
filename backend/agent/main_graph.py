"""
Agent 主图 — Router + Expert 架构

公共接口:
- chat(): 非流式对话
- stream_chat(): 流式对话 (SSE)
- simple_chat(): 简单对话（不走工作流，直接 LLM）
- generate_session_title(): 生成会话标题
"""

from typing import Dict, List, Optional
from functools import partial

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes.router import router_node
from agent.nodes.paper_expert import paper_expert_node
from agent.nodes.search_expert import search_expert_node

from services.rag_service import RAGService


class AcademicAgentService:
    """学术论文阅读助手 — Router + Expert 多节点工作流"""

    def __init__(
        self,
        rag_service: RAGService,
        openai_api_key: str,
        openai_api_base: Optional[str] = None,
        model: str = "qwen-plus",
        temperature: float = 0.7,
    ):
        if not openai_api_key:
            raise ValueError("需要有效的 openai_api_key，请在 config.yaml 中配置。")

        self.rag_service = rag_service
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=openai_api_key,
            base_url=openai_api_base,
        )
        self.workflow = self._build_workflow()

    # ==================== 工作流 ====================

    def _build_workflow(self):
        g = StateGraph(AgentState)

        g.add_node("router", partial(router_node, llm=self.llm))
        g.add_node("paper_expert", partial(paper_expert_node, llm=self.llm, rag_service=self.rag_service))
        g.add_node("search_expert", partial(search_expert_node, llm=self.llm, rag_service=self.rag_service))

        g.set_entry_point("router")

        g.add_conditional_edges("router", _route, {
            "chat": END,
            "paper": "paper_expert",
            "search": "search_expert",
        })

        g.add_edge("paper_expert", END)
        g.add_edge("search_expert", END)

        return g.compile()

    # ==================== 公共接口 ====================

    def generate_session_title(self, user_query: str) -> str:
        prompt = (
            "请为以下提问生成一个极简会话标题（不超过15字），直接输出标题，不要引号。\n\n"
            f"提问：{user_query}\n标题："
        )
        try:
            resp = self.llm.invoke([HumanMessage(content=prompt)])
            return resp.content.strip().strip('"《》')
        except Exception as e:
            print(f"[title] error: {e}")
            return user_query[:20]

    def chat(self, user_query: str, user_id=None, paper_id=None, chat_history=None) -> Dict:
        """与 Agent 对话（非流式）"""
        state = _init_state(user_query, user_id, paper_id, chat_history)
        try:
            final = self.workflow.invoke(state)
            return {
                "response": final["final_response"],
                "citations": final.get("citations", []),
                "steps": final.get("steps", []),
                "context_used": {
                    "local_chunks": len(final.get("local_context", [])),
                    "external_sources": len(final.get("external_context", [])),
                    "library_chunks": len(final.get("library_context", [])),
                },
            }
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"response": f"抱歉，出现错误：{e}", "citations": [], "steps": ["错误"], "context_used": {}}

    def stream_chat(self, user_query: str, user_id=None, paper_id=None, chat_history=None):
        """流式对话（生成器，每个节点完成时 yield 一次）"""
        state = _init_state(user_query, user_id, paper_id, chat_history)
        try:
            for chunk in self.workflow.stream(state):
                for node_name, node_state in chunk.items():
                    yield {"type": "step", "step": node_state.get("current_step", node_name), "data": node_state}
                    if node_state.get("final_response"):
                        yield {
                            "type": "final",
                            "response": node_state["final_response"],
                            "citations": node_state.get("citations", []),
                            "steps": node_state.get("steps", []),
                        }
        except Exception as e:
            print(f"[stream] error: {e}")
            yield {"type": "error", "error": str(e)}

    def simple_chat(self, user_query: str, context_text=None, chat_history=None, system_prompt=None) -> Dict:
        """简单对话 — 不走工作流，直接 LLM 回答。"""
        default = "你是一个学术论文阅读助手。请根据提供的文档内容和对话历史，回答问题。"
        messages = [SystemMessage(content=system_prompt or default)]

        if context_text:
            messages.append(HumanMessage(content=f"文档内容：\n\n{context_text}\n\n---\n"))

        for msg in (chat_history or [])[-5:]:
            cls = HumanMessage if msg["role"] == "user" else AIMessage
            messages.append(cls(content=msg["content"]))

        messages.append(HumanMessage(content=user_query))

        try:
            resp = self.llm.invoke(messages)
            return {"response": resp.content, "citations": [], "context_used": {"has_context": bool(context_text)}}
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"response": f"抱歉，出现错误：{e}", "citations": [], "context_used": {}}


# ==================== 模块级工具 ====================

def _route(state: AgentState) -> str:
    """路由函数 — 读取 Router 写入的 intent 字段决定分支"""
    return state.get("intent", "paper")


def _init_state(user_query, user_id, paper_id, chat_history) -> AgentState:
    """构建工作流初始状态"""
    return {
        "user_query": user_query,
        "user_id": user_id,
        "paper_id": paper_id,
        "chat_history": chat_history or [],
        "intent": "",
        "task_description": "",
        "local_context": [],
        "external_context": [],
        "library_context": [],
        "final_response": "",
        "citations": [],
        "steps": [],
        "current_step": "",
    }
