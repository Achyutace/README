"""
Agent Service - 学术论文阅读助手 Agent [对话用]

使用 LangGraph 实现的多节点工作流：
1. RAG 检索 - 从本地向量数据库中检索当前论文相关段落
2. 相关性与充分性评估 - 判断检索到的信息是否足以回答问题
3. 工具规划与执行 - 如果信息不足，调用外部工具（联网搜索/笔记编辑/读取对话历史/读取完整文本）
4. 综合生成 - 整合本地和外部信息，生成最终答案
"""

import json
from typing import Dict, List, Optional, TypedDict, Annotated
from datetime import datetime

# LangChain 核心组件 (LangChain 0.3 适配: 使用 langchain_core)
from langchain_openai import ChatOpenAI  # OpenAI 的聊天模型
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage  # 消息类型
from langchain_core.tools import Tool  # 工具封装
from langgraph.graph import StateGraph, END  # 状态图和结束节点
# from langgraph.prebuilt import ToolExecutor # 移除：代码中手动执行工具，不需要此组件

# 本地服务和工具
from services.rag_service import RAGService  # RAG服务
from services.storage_service import StorageService
from tools.web_search_tool import WebSearchTool  # 网络搜索工具
from tools.paper_discovery_tool import PaperDiscoveryTool  # 论文搜索工具
class AgentState(TypedDict):
    """ Agent 状态定义 """
    user_query: str  
    retrieval_query: str  
    user_id: str
    paper_id: str
    
    is_general_chat: bool  # 标记是否为通用问题
    need_full_text: bool   # 标记是否需要全文总结
    
    chat_history: List[Dict]
    local_context: List[Dict]
    local_context_text: str
    is_sufficient: bool
    missing_info: str
    tool_calls: List[Dict]
    external_context: List[Dict]
    final_response: str
    citations: List[Dict]
    steps: List[str]
    current_step: str


class AcademicAgentService:
    def __init__(self,   
                 rag_service: RAGService,
                 storage_service: StorageService,
                 openai_api_key: Optional[str] = None,  
                 openai_api_base: Optional[str] = None,  
                 model: str = "qwen-plus",  
                 temperature: float = 0.7):  
        """  
        初始化 Agent 服务      
        """  
        self.rag_service = rag_service
        self.storage_service = storage_service  
  
  
        api_key = openai_api_key
        api_base = openai_api_base
        if api_key:  
            # 初始化 OpenAI 聊天模型  
            self.llm = ChatOpenAI(  
                model=model,  
                temperature=temperature,  
                api_key=api_key,  
                base_url=api_base  
            )  
            self.has_llm = True  
        else:  
            # 没有 API Key，进入 Demo 模式（返回模拟数据）  
            self.llm = None  
            self.has_llm = False  
            print("Warning: OpenAI API key not found. Agent will use demo mode.")  
          
        # 初始化工具  
        self.web_search = WebSearchTool()  
        self.paper_discovery = PaperDiscoveryTool()  
          
        self.workflow = self._build_workflow()  

    def _build_workflow(self) -> StateGraph:
        """构建 LangGraph 工作流"""
        workflow = StateGraph(AgentState)
        
        # 节点定义
        workflow.add_node("query_translation", self._query_translation_node) # 节点0: 意图识别
        workflow.add_node("general_chat", self._general_chat_node)         # 节点0b: 闲聊
        workflow.add_node("rag_retrieval", self._rag_retrieval_node)       # 节点1: 本地 RAG
        workflow.add_node("full_text_retrieval", self._full_text_retrieval_node) # 节点1b: 全文检索
        
        # 评估+规划+执行 合并为一个节点
        workflow.add_node("adaptive_retrieval", self._adaptive_retrieval_node) # 节点2: 自适应补充检索
        
        workflow.add_node("synthesize", self._synthesize_node)             # 节点3: 综合生成
        
        # 设置入口
        workflow.set_entry_point("query_translation")
        
        # 意图路由 
        workflow.add_conditional_edges(
            "query_translation",
            self._route_query,
            {
                "academic": "rag_retrieval",
                "general": "general_chat",
                "full_text": "full_text_retrieval"
            }
        )
        
        workflow.add_edge("general_chat", END)
        
        # 主流程：RAG -> 自适应检索 -> 综合 -> 结束
        workflow.add_edge("rag_retrieval", "adaptive_retrieval")
        workflow.add_edge("full_text_retrieval", "adaptive_retrieval")
        workflow.add_edge("adaptive_retrieval", "synthesize")
        workflow.add_edge("synthesize", END)
        
        return workflow.compile()

    # ====================  路由逻辑 ====================
    def _route_query(self, state: AgentState) -> str:
        """根据翻译结果决定下一步走向"""
        if state.get("is_general_chat", False):
            return "general"
        if state.get("need_full_text", False):
            return "full_text"
        return "academic"
    
    # ====================  查询翻译节点 ====================
    def _query_translation_node(self, state: AgentState) -> AgentState:
        """节点 0: 查询翻译与优化 + 意图识别"""
        steps = state.get('steps', [])
        steps.append('意图识别与查询优化')
        
        user_query = state['user_query']
        
        if not self.has_llm:
            # Demo 模式默认视为学术问题
            return {
                **state,
                'steps': steps,
                'current_step': '跳过翻译(Demo模式)...',
                'retrieval_query': user_query,
                'is_general_chat': False,
                'need_full_text': False
            }
        # Prompt 
        prompt = f"""
你是一个专业的学术查询优化专家。你的任务是识别用户的意图并将用户的输入转化为高效的英文学术检索词（Search Query）。
请严格按照以下逻辑处理：
1. **意图识别（关键分支）**：
   - **FullText**: 如果用户要求“全文总结”、“总结全文”、“这篇文章讲了什么”、“概述全文”、“主要内容”、“摘要”等需要阅读整篇文档才能回答的宏观问题，请直接输出：Reference
   - **General**: 如果输入属于闲聊、问候、无意义字符或完全非学术的话题（例如：“你好”、“你是谁”、“讲个笑话”、“今天天气”），请直接输出：N/A
   - **Academic**: 如果是具体的学术问题（如“Transformer的架构是什么”、“实验结果如何”），请进入第2步。
2. **翻译与重构（如果是学术问题）**：
   - 将用户问题翻译为专业的**英文**学术术语。
   - **去停用词**：去除 "How to", "Help me find", "What is", "about" 等无关词汇。
   - **关键词提取**：只保留核心实体、技术名词和研究方向。
   - **格式优化**：输出为适合检索的关键词字符串（空格分隔）。
3. **输出约束**：
   - 仅输出最终的英文查询字符串，或者 "N/A" (闲聊)，或者 "Reference" (全文需求)。
   - 不要包含任何解释、前缀、Markdown 格式或标点符号。
**示例：**
User: 你好
Agent: N/A
User: 帮我总结一下这篇文章
Agent: Reference
User: 帮我找一下关于Transformer在时间序列预测中的改进模型
Agent: transformer time series forecasting improved models
User: 什么是低秩适应（LoRA）？
Agent: low-rank adaptation LoRA parameter efficient fine-tuning
User: {user_query}
Agent:
"""
        translated_query = user_query
        is_general_chat = False
        need_full_text = False
        step_desc = ""
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            
            # 清洗数据，防止 LLM 输出多余标点
            content = content.replace('"', '').replace("'", "")
            
            if content == "N/A":
                # 识别为闲聊
                is_general_chat = True
                step_desc = "识别为非学术/闲聊意图，转入通用对话模式"
                translated_query = "" # 闲聊不需要检索词
            elif content == "Reference":
                # 识别为全文总结
                need_full_text = True
                step_desc = "识别为全文总结意图，准备获取全文"
                translated_query = user_query 
            else:
                # 识别为学术问题
                translated_query = content
                step_desc = f'已将问题优化为检索词: "{translated_query}"'
            
        except Exception as e:
            print(f"Translation error: {e}")
            step_desc = '翻译服务异常，使用原始查询'
        return {
            **state,
            'steps': steps,
            'current_step': step_desc,
            'retrieval_query': translated_query,
            'is_general_chat': is_general_chat,
            'need_full_text': need_full_text
        }
    # ==================== 通用闲聊节点 ====================
    def _general_chat_node(self, state: AgentState) -> AgentState:
        """节点 0b: 通用闲聊处理 (不查库)"""
        steps = state.get('steps', [])
        steps.append('通用对话生成')
        
        user_query = state['user_query']
        chat_history = state.get('chat_history', [])
        
        if not self.has_llm:
            return {
                **state,
                'steps': steps,
                'current_step': '通用对话(Demo)...',
                'final_response': f"你好！我是学术助手。(Demo回覆: {user_query})",
                'citations': []
            }
        # 简单的对话 Prompt
        system_prompt = "你是一个专业的学术论文阅读助手。虽然用户当前的问题与特定的学术检索无关，但请保持专业、友好、积极的态度进行回答。"
        
        messages = [SystemMessage(content=system_prompt)]
        
        # 加入历史记录 (最近 3 轮即可，避免上下文过长)
        for msg in chat_history[-3:]:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                messages.append(AIMessage(content=msg['content']))
        
        messages.append(HumanMessage(content=user_query))
        
        response_text = ""
        try:
            response = self.llm.invoke(messages)
            response_text = response.content
        except Exception as e:
            response_text = "抱歉，我现在无法处理您的请求。"
            print(f"General chat error: {e}")
        return {
            **state,
            'steps': steps,
            'current_step': '已生成通用回复',
            'final_response': response_text,
            'citations': [] # 闲聊没有引用
        }

    # ==================== RAG 检索节点 ====================
    def _rag_retrieval_node(self, state: AgentState) -> AgentState:
        """节点 1: RAG 检索"""
        steps = state.get('steps', [])
        steps.append('RAG 检索')
        
        # 优先使用优化后的 retrieval_query，如果没有则用 user_query
        query_to_use = state.get('retrieval_query') or state['user_query']
        
        user_id = state['user_id']
        paper_id = state['paper_id']
        
        # 执行检索
        results = self.rag_service.retrieve(query=query_to_use, file_hash=paper_id, top_k=5)
        
        # 格式化为文本
        context_parts = []
        for i, result in enumerate(results, 1):
            section = result.get('section', 'unknown')
            page = result.get('page', 'N/A')

            if section == 'unknown' and 'metadata' in result:
                section = result['metadata'].get('section', 'unknown')
            if page == 'N/A' and 'metadata' in result:
                page = result['metadata'].get('page', 'N/A')

            context_parts.append(
                f"[来源 {i}] 章节: {section}, "
                f"页码: {page}\n"
                f"{result['parent_content']}\n"
            )
        
        return {
            **state,
            'steps': steps,
            'current_step': f'正在检索本地知识库 (Query: {query_to_use})...',
            'local_context': results,
            'local_context_text': '\n'.join(context_parts) if context_parts else '未找到相关内容'
        }
    
    # ==================== 全文检索节点 ====================
    def _full_text_retrieval_node(self, state: AgentState) -> AgentState:
        """节点 1b: 全文检索 (针对摘要/总结类问题)"""
        steps = state.get('steps', [])
        steps.append('全文获取')
        
        file_hash = state['paper_id']
        local_context = []
        local_context_text = ""
        current_step_desc = ""

        if not file_hash:
             current_step_desc = "未指定文件，无法获取全文"
             local_context_text = "用户未指定具体文档，无法进行全文总结。"
        else:
             try:
                 # 获取全文，include_translation=False 以节约上下文
                 full_text = self.storage_service.get_full_text(file_hash, include_translation=False)
                 if full_text:
                     # 限制长度，防止 LLM 上下文爆 (保留前50000字符，对大多数论文足够)
                     limited_text = full_text[:50000] 
                     
                     # 构造上下文对象
                     local_context = [{
                         'parent_content': limited_text,
                         'metadata': {'page': 'All', 'section': 'Full Document'}
                     }]
                     
                     # 构造上下文文本（用于 adaptive_retrieval 判断）
                     if len(full_text) > 3000:
                         local_context_text = f"【文档全文】\n{full_text[:3000]}...\n(由于长度限制展示前 3000 字符，但完整内容已传入下文)"
                     else:
                         local_context_text = f"【文档全文】\n{full_text}"
                         
                     current_step_desc = "已获取文档全文内容"
                 else:
                     current_step_desc = "文档内容为空"
                     local_context_text = "文档内容为空。"
             except Exception as e:
                 print(f"Full text retrieval error: {e}")
                 current_step_desc = f"获取全文失败: {str(e)}"
                 local_context_text = f"获取全文失败: {str(e)}"
                 
        return {
            **state,
            'steps': steps,
            'current_step': current_step_desc,
            'local_context': local_context,  # 传递给 synthesize 节点
            'local_context_text': local_context_text # 传递给 adaptive_retrieval 节点
        }
    
    # ==================== 补充检索节点 ====================
    def _adaptive_retrieval_node(self, state: AgentState) -> AgentState:
        """节点 2: 自适应补充检索 (评估 + 工具规划 + 执行)"""
        steps = state.get('steps', [])
        
        if not self.has_llm:
            # Demo 模式
            steps.append('自适应检索(Demo)')
            return {
                **state,
                'steps': steps,
                'current_step': '跳过外部检索(Demo)...',
                'external_context': [],
                'is_sufficient': True
            }

        user_query = state['user_query']
        local_context = state['local_context_text']
        
        # 构建 Prompt：要求 LLM 同时输出“是否充足”和“如果不足需要的工具调用”
        prompt = f"""
你是一个专业的学术研究助手。你的任务是根据用户的提问和已经检索到的本地文档内容，决定是否需要进行额外的外部搜索。

用户问题：
{user_query}

本地文档内容（RAG结果）：
{local_context[:3000]}

请仔细分析：
1. 本地文档是否足以全面、准确地回答用户问题？
2. 如果不足，需要补充哪些信息？通过什么工具获取？

可用工具：
- web_search: 搜索互联网 (通用概念、最新新闻、代码文档)
- search_papers: 搜索学术数据库 (ArXiv/Semantic Scholar 查找相关论文)

请输出 JSON 格式：
{{
    "status": "sufficient" 或 "insufficient",
    "reason": "判断的理由",
    "tool_calls": [  // 如果 status 为 sufficient，此项为空列表
        {{"tool": "web_search" 或 "search_papers", "query": "具体的查询关键词"}},
        ...
    ]
}}
"""
        steps.append('评估与补充检索')
        external_context = []
        is_sufficient = True
        current_step_desc = "信息充足，无需外部检索"

        try:
            # 1. 调用 LLM 做决策
            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            # 解析 JSON
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```json")[1].split("```")[0].strip() if "json" in content else content.split("```")[1].strip()
            
            decision = json.loads(content)
            
            # 2. 根据决策行动
            if decision.get("status") == "insufficient":
                is_sufficient = False
                tool_calls = decision.get("tool_calls", [])
                
                tool_logs = []
                
                # 3. 如果不足，执行工具
                for call in tool_calls:
                    tool_name = call.get("tool")
                    query = call.get("query")
                    
                    if not tool_name or not query: 
                        continue
                        
                    try:
                        if tool_name == 'web_search':
                            results = self.web_search.search(query)
                            external_context.extend(results)
                            tool_logs.append(f"Web: {query}")
                            
                        elif tool_name == 'search_papers':
                            results = self.paper_discovery.search_papers(query)
                            external_context.extend(results)
                            tool_logs.append(f"Paper: {query}")
                            
                    except Exception as t_err:
                        print(f"Tool execution failed: {t_err}")
                
                if tool_logs:
                    current_step_desc = f"补充检索执行中: {', '.join(tool_logs)}"
                else:
                    current_step_desc = "需要补充检索，但工具规划为空"
            
            else:
                # 信息充足
                current_step_desc = "本地信息充足，跳过外部检索"

        except Exception as e:
            print(f"Adaptive retrieval error: {e}")
            current_step_desc = "自适应检索模块出错，使用现有信息"

        return {
            **state,
            'steps': steps,
            'current_step': current_step_desc,
            'is_sufficient': is_sufficient,
            'external_context': external_context,
            'tool_calls': decision.get("tool_calls", []) if 'decision' in locals() else []
        }
    
    def _synthesize_node(self, state: AgentState) -> AgentState:
        """节点 3: 综合生成 (支持 JSON 格式引用)"""
        steps = state.get('steps', [])
        steps.append('综合生成答案')
        
        # --- 1. 准备上下文 (关键：必须包含元数据供 LLM 提取) ---
        # 格式化本地上下文，带上 ID 方便 LLM 引用
        local_context_str = ""
        for i, item in enumerate(state.get('local_context', []), 1):
            # 确保 page 和 section 存在
            page = item.get('page', item.get('metadata', {}).get('page', 'N/A'))
            section = item.get('section', item.get('metadata', {}).get('section', '未知章节'))
            local_context_str += f"【本地文档-{i}】(页码: {page}, 章节: {section}):\n{item.get('parent_content', '')}\n\n"

        # 格式化外部上下文
        external_context_str = ""
        if state.get('external_context'):
            # 复用之前的格式化逻辑，或者稍微简化，确保带上 URL
            for i, item in enumerate(state.get('external_context', [])[:5], 1): # 限制前5条
                title = item.get('title', '未命名')
                url = item.get('url', '')
                snippet = item.get('snippet', item.get('abstract', ''))
                external_context_str += f"【外部来源-{i}】(标题: {title}, 链接: {url}):\n{snippet}\n\n"

        # --- 2. 构建 Prompt ---
        synthesis_prompt = f"""
你是一个专业的学术论文阅读助手。请根据提供的资料回答用户问题。

用户问题：
{state['user_query']}

=== 资料区域 ===
{local_context_str}
{external_context_str}
==============

**任务要求**：
1. **综合回答**：使用 Markdown 格式回答问题。回答中提到的每一个观点，**必须**在句子末尾标注引用来源，格式为 `[n]` (例如 `[1]`, `[2]`)。
2. **结构化引用**：将所有对应的引用来源整理为 JSON 数据。
3. **严格格式**：**只输出一个纯 JSON 对象**，不要包含 markdown 代码块标记（如 ```json），不要包含其他废话。

**JSON 输出结构定义**：
{{
    "answer": "你的回答文本，包含 [1] 这样的标记...",
    "citations": [
        {{
            "id": 1,                   // 对应文中的 [1]
            "source_type": "local",    // 必须是 "local" 或 "external"
            "title": "章节标题或网页标题",
            "snippet": "引用的原文片段(简短)",
            "page": "12",              // 如果是 local，填页码；如果是 external，填 null
            "url": "http://..."        // 如果是 external，填链接；如果是 local，填 null
        }}
    ]
}}
"""
        
        if not self.has_llm:
            return self._demo_synthesize(state)

        final_response_text = ""
        citations_json = []

        try:
            # --- 3. 调用 LLM ---
            response = self.llm.invoke([HumanMessage(content=synthesis_prompt)])
            content = response.content.strip()

            # --- 4. 解析 JSON (增强健壮性) ---
            # 去除可能的 Markdown 标记
            if content.startswith("```json"):
                content = content.split("```json")[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()

            data = json.loads(content)
            
            final_response_text = data.get("answer", "")
            citations_json = data.get("citations", [])

        except json.JSONDecodeError:
            print("JSON Parsing failed, falling back to raw text.")
            # 降级处理：如果在回答中包含了 JSON 但解析失败，尝试提取文本部分
            final_response_text = content 
            citations_json = [] 
        except Exception as e:
            print(f"Synthesize error: {e}")
            final_response_text = "抱歉，生成答案时发生错误。"

        return {
            **state,
            'steps': steps,
            'current_step': '回答生成完毕',
            'final_response': final_response_text,
            'citations': citations_json # 现在这里是结构化的 JSON 数据
        }

    def _demo_synthesize(self, state):
        """Demo 模式的模拟返回"""
        return {
            **state,
            'steps': state.get('steps', []) + ['综合生成(Demo)'],
            'current_step': '完成',
            'final_response': f"这是一个关于 '{state['user_query']}' 的演示回答。我们发现了一些有趣的点 [1]。并且外部搜索也证实了这一点 [2]。",
            'citations': [
                {
                    "id": 1,
                    "source_type": "local",
                    "title": "Introduction",
                    "snippet": "Transformers are powerful...",
                    "page": "1",
                    "url": None
                },
                {
                    "id": 2,
                    "source_type": "external",
                    "title": "Attention is all you need",
                    "snippet": "Abstract of the paper...",
                    "page": None,
                    "url": "https://arxiv.org/abs/1706.03762"
                }
            ]
        }

    
    def _format_external_context(self, external_context: List[Dict]) -> str:
        """格式化外部上下文"""

        if not external_context:
            return ""
        
        parts = []
        # 最多使用前3个结果（避免 prompt 过长）
        for i, item in enumerate(external_context[:3], 1):
            source_type = item.get('source', 'unknown')
            
            if source_type in ['arxiv', 'semantic_scholar'] or 'paper_id' in item:
                # 构建论文信息
                paper_info = [
                    f"[论文 {i}] {item.get('title', 'N/A')}",
                    f"发表日期: {item.get('published', 'N/A')}",
                    f"引用数: {item.get('citations', 0)}",
                ]
                
                # 过滤空字符串
                paper_info = [info for info in paper_info if info]
                
                # 添加评分信息（如果有）
                if 'relevance_score' in item:
                    paper_info.append(
                        f"评分 - 相关性: {item.get('relevance_score', 0):.2f}, "
                        f"时效性: {item.get('recency_score', 0):.2f}, "
                        f"引用影响: {item.get('citation_impact', 0):.2f}"
                    )
                
                # 添加摘要（截断到300字符）
                abstract = item.get('abstract', '')
                if abstract:
                    # 移除可能的省略号后缀
                    abstract = abstract.rstrip('.')
                    if len(abstract) > 300:
                        abstract = abstract[:300] + '...'
                    paper_info.append(f"摘要: {abstract}")
                
                parts.append('\n'.join(paper_info))
            
            elif 'snippet' in item:
                web_info = [
                    f"[网页 {i}] {item.get('title', 'N/A')}",
                    f"内容: {item['snippet']}"
                ]
                
                if item.get('url'):
                    web_info.append(f"来源: {item['url']}")
                
                parts.append('\n'.join(web_info))
            
            # ========== 通用格式（其他数据源） ==========
            else:
                # 尝试提取标题和内容
                title = item.get('title', item.get('name', 'N/A'))
                content = item.get('content', item.get('description', item.get('abstract', '')))
                
                if content:
                    if len(content) > 400:
                        content = content[:400] + '...'
                    parts.append(f"[来源 {i}] {title}\n{content}")
                else:
                    parts.append(f"[来源 {i}] {title}")
        
        return '\n\n'.join(parts)
    
    def _extract_citations(self, state: AgentState) -> List[Dict]:
        """提取引用信息"""
        citations = []
        
        # 从本地上下文提取
        for result in state.get('local_context', []):
            page = result.get('page', result.get('metadata', {}).get('page', 0))
            section = result.get('section', result.get('metadata', {}).get('section', 'unknown'))
            
            citations.append({
                'source_type': 'local',  # 来源类型：本地文档
                'page': page,  # 页码
                'section': section,  # 章节
            })
        
        # ========== 从外部上下文提取引用 ==========
        for item in state.get('external_context', []):
            source_type = item.get('source', 'external')
            
            # 论文类型的引用
            if source_type in ['arxiv', 'semantic_scholar'] or 'paper_id' in item:
                authors = item.get('authors', [])
                authors_str = ', '.join(authors[:3]) if isinstance(authors, list) else str(authors)
                if isinstance(authors, list) and len(authors) > 3:
                    authors_str += ' et al.'
                
                citations.append({
                    'source_type': 'paper',
                    'paper_id': item.get('paper_id', ''),
                    'title': item.get('title', ''),
                    'authors': authors_str,
                    'published': item.get('published', ''),
                    'citations': item.get('citations', 0),
                    'url': item.get('url', ''),
                    'pdf_url': item.get('pdf_url', '')
                })
            
            # 网络搜索的引用
            elif 'snippet' in item:
                citations.append({
                    'source_type': 'web',
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', '')[:200],
                    'url': item.get('url', '')
                })
            
            # 通用外部来源
            else:
                citations.append({
                    'source_type': 'external',
                    'title': item.get('title', item.get('name', '')),
                    'content': str(item.get('content', item.get('description', '')))[:200],
                    'url': item.get('url', '')
                })
        
        return citations
    
    def _demo_response(self, state: AgentState) -> str:
        """Demo 模式的响应"""
        return f'根据本地文档和外部信息，关于"{state["user_query"]}"的回答是：这是一个演示回答。在实际使用中，系统会综合本地知识库和外部工具的信息来提供详细的回答。'
    
    # ==================== 公共接口 ====================
    
    def generate_session_title(self, user_query: str) -> str:
        """
        使用 LLM 根据用户的第一句提问生成简短的会话标题
        """
        if not self.has_llm:
            # Demo 模式或无 LLM，回退到简单截断
            return user_query[:20] + "..." if len(user_query) > 20 else user_query

        prompt = f"""
请为下面的用户提问生成一个极简短的会话标题（不超过 15 个字）。
不要使用“关于”、“询问”等废话，直接提取核心主题。
不要使用引号。

用户提问：{user_query}
标题：
"""
        try:
            # 直接调用 LLM，不走复杂工作流
            response = self.llm.invoke([HumanMessage(content=prompt)])
            title = response.content.strip()
            
            # 清理可能的多余符号
            title = title.replace('"', '').replace('《', '').replace('》', '')
            return title
        except Exception as e:
            print(f"Title generation error: {e}")
            return user_query[:20] # 降级处理
        
    def chat(self, 
             user_query: str,
             user_id: str = "default",
             paper_id: str = None,
             chat_history: Optional[List[Dict]] = None) -> Dict:
        """
        与 Agent 对话
        """
        # 初始化状态
        initial_state: AgentState = {
            'user_query': user_query,
            'retrieval_query': '',
            'user_id': user_id,
            'paper_id': paper_id,
            'is_general_chat': False,
            'need_full_text': False,
            'chat_history': chat_history or [],
            'local_context': [],
            'local_context_text': '',
            'is_sufficient': False,
            'missing_info': '',
            'tool_calls': [],
            'external_context': [],
            'final_response': '',
            'citations': [],
            'steps': [],
            'current_step': ''
        }
        
        # 执行工作流
        try:
            final_state = self.workflow.invoke(initial_state)
            
            return {
                'response': final_state['final_response'],  # 最终答案
                'citations': final_state['citations'],  # 引用来源
                'steps': final_state['steps'],  # 执行步骤记录
                'context_used': {
                    'local_chunks': len(final_state['local_context']),
                    'external_sources': len(final_state['external_context'])
                }
            }
        
        except Exception as e:
            print(f"Workflow error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'response': f'抱歉，处理您的问题时出现了错误：{str(e)}',
                'citations': [],
                'steps': ['错误'],
                'context_used': {}
            }
    
    def stream_chat(self, 
                    user_query: str,
                    user_id: str = "default",
                    paper_id: Optional[str] = None,
                    chat_history: Optional[List[Dict]] = None):
        """
        流式对话（生成器）
        """
        # 初始化状态
        initial_state: AgentState = {
            'user_query': user_query,
            'retrieval_query': '',
            'user_id': user_id,
            'paper_id': paper_id,
            'is_general_chat': False,
            'need_full_text': False,
            'chat_history': chat_history or [],
            'local_context': [],
            'local_context_text': '',
            'is_sufficient': False,
            'missing_info': '',
            'tool_calls': [],
            'external_context': [],
            'final_response': '',
            'citations': [],
            'steps': [],
            'current_step': ''
        }
        
        # 执行工作流并yield中间状态
        try:
            # workflow.stream() 返回一个生成器
            for chunk in self.workflow.stream(initial_state):
                # chunk 是一个字典，key 是节点名，value 是该节点返回的状态更新
                for node_name, node_state in chunk.items():
                    # Yield 当前步骤的信息
                    yield {
                        'type': 'step',
                        'step': node_state.get('current_step', node_name),
                        'data': node_state
                    }
                    
                    # 如果到了最后一步，提取最终结果
                    if 'final_response' in node_state and node_state['final_response']:
                        yield {
                            'type': 'final',
                            'response': node_state['final_response'],
                            'citations': node_state['citations'],
                            'steps': node_state['steps']
                        }
        
        except Exception as e:
            # ========== 错误处理 ==========
            print(f"Stream error: {e}")
            yield {
                'type': 'error',
                'error': str(e)
            }
    
    def simple_chat(self,
                    user_query: str,
                    context_text: Optional[str] = None,
                    chat_history: Optional[List[Dict]] = None,
                    system_prompt: Optional[str] = None) -> Dict:
        """
        简单对话模式 - 基于提供的上下文文本进行对话
        
        适用场景：
        - 用户需要快速回答
        - 问题相对简单，不需要外部工具
        - 希望基于整篇文档内容进行对话

        Args:
            user_query: 用户问题
            context_text: 上下文文本（如文档全文，由路由层提供）
            chat_history: 对话历史（可选）
            system_prompt: 自定义系统提示词（可选）
        
        Returns:
            包含 response 的字典
        """
        if not self.has_llm:
            return {
                'response': f'Demo 模式：关于"{user_query}"的简单回答。实际使用时会基于提供的上下文生成回答。',
                'citations': [],
                'context_used': {
                    'has_context': bool(context_text),
                    'chat_history_turns': len(chat_history or [])
                }
            }
        
        try:
            # 使用自定义系统提示词或默认提示词
            default_system_prompt = "你是一个学术论文阅读助手。请根据提供的文档内容和对话历史，简洁、准确地回答用户的问题。"
            messages = [SystemMessage(content=system_prompt or default_system_prompt)]
            
            # 如果提供了上下文文本，添加为上下文消息
            if context_text:
                context_message = f"文档内容：\n\n{context_text}\n\n---\n\n请基于以上文档内容回答用户的问题。"
                messages.append(HumanMessage(content=context_message))
            
            # 添加对话历史（最近 5 轮）
            for msg in (chat_history or [])[-5:]:
                if msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    messages.append(AIMessage(content=msg['content']))
            
            # 添加当前用户问题
            messages.append(HumanMessage(content=user_query))
            
            # 调用 LLM 生成回答
            response = self.llm.invoke(messages)
            
            return {
                'response': response.content,
                'citations': [],  # 简单模式不提供详细引用
                'context_used': {
                    'has_context': bool(context_text),
                    'context_length': len(context_text) if context_text else 0,
                    'chat_history_turns': len(chat_history or [])
                }
            }
        
        except Exception as e:
            print(f"Simple chat error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'response': f'抱歉，处理您的问题时出现了错误：{str(e)}',
                'citations': [],
                'context_used': {}
            }