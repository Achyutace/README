"""
Agent Service - 学术论文阅读助手 Agent [对话用]

使用 LangGraph 实现的多节点工作流：
1. RAG 检索 - 从本地向量数据库中检索当前论文相关段落
2. 相关性与充分性评估 - 判断检索到的信息是否足以回答问题
3. 工具规划与执行 - 如果信息不足，调用外部工具（联网搜索/笔记编辑/读取对话历史/读取完整文本）
4. 综合生成 - 整合本地和外部信息，生成最终答案
"""

import os
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
from services.storage_service import StorageService  # PDF 处理服务
from tools.web_search_tool import WebSearchTool  # 网络搜索工具
from tools.paper_discovery_tool import PaperDiscoveryTool  # 论文搜索工具

class AgentState(TypedDict):
    """ Agent 状态定义 """
    user_query: str  # 用户的问题
    user_id: str  # 用户标识符
    paper_id: str  # 当前正在阅读的论文ID
    
    chat_history: List[Dict]  # 历史对话记录 （MVP）
    
    local_context: List[Dict]  # 从本地知识库检索到的相关段落列表
    local_context_text: str  # 格式化后的本地上下文文本
    
    is_sufficient: bool  # 本地信息是否足够回答问题
    missing_info: str  # 如果信息不足，描述缺少什么信息
    
    tool_calls: List[Dict]  # 调用的工具列表
    external_context: List[Dict]  # 从外部工具获取的信息
    
    final_response: str  # 生成的最终答案
    citations: List[Dict]  # 引用来源列表（本地文档页码、章节等）
    
    steps: List[str]  # 记录执行的步骤名称（用于调试和展示）
    current_step: str  # 当前正在执行的步骤描述

class AcademicAgentService:
    """ 学术论文阅读助手 Agent """
    
    def __init__(self, 
                 rag_service: RAGService,
                 openai_api_key: Optional[str] = None,
                 openai_api_base: Optional[str] = None,
                 model: str = "gpt-3.5-turbo",
                 temperature: float = 0.7):
        """
        初始化 Agent 服务    
        """
        self.rag_service = rag_service

        api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        api_base = openai_api_base or os.getenv('OPENAI_API_BASE') 
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
        
        # 添加节点
        workflow.add_node("rag_retrieval", self._rag_retrieval_node)  # 节点1: RAG检索
        workflow.add_node("sufficiency_judge", self._sufficiency_judge_node)  # 节点2: 评估
        workflow.add_node("tool_planning", self._tool_planning_node)  # 节点3: 工具调用
        workflow.add_node("synthesize", self._synthesize_node)  # 节点4: 综合生成
        
        # 设置入口点
        workflow.set_entry_point("rag_retrieval")
        
        # 添加边
        workflow.add_edge("rag_retrieval", "sufficiency_judge")
        
        # 条件边：判断是否需要工具
        workflow.add_conditional_edges(
            "sufficiency_judge",
            self._should_use_tools,
            {
                "use_tools": "tool_planning",
                "sufficient": "synthesize"
            }
        )
        
        workflow.add_edge("tool_planning", "synthesize")
        workflow.add_edge("synthesize", END)
        
        return workflow.compile()
    
    def _rag_retrieval_node(self, state: AgentState) -> AgentState:
        """节点 1: RAG 检索"""
        # 确保 steps 列表已初始化
        steps = state.get('steps', [])
        steps.append('RAG 检索')
        
        user_query = state['user_query']
        user_id = state['user_id']
        paper_id = state['paper_id']
        
        # 执行检索
        results = self.rag_service.retrieve(query=user_query, user_id=user_id, paper_id=paper_id, top_k=5)
        
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
            'current_step': '正在检索本地知识库...',
            'local_context': results,
            'local_context_text': '\n'.join(context_parts) if context_parts else '未找到相关内容'
        }
    
    def _sufficiency_judge_node(self, state: AgentState) -> AgentState:
        """节点 2: 相关性与充分性评估"""
        steps = state.get('steps', [])
        steps.append('信息充分性评估')
        
        if not self.has_llm:
            # Demo 模式：简单判断
            is_sufficient = len(state['local_context']) >= 1
            return {
                **state,
                'steps': steps,
                'current_step': '正在评估信息是否充足...',
                'is_sufficient': is_sufficient,
                'missing_info': '' if is_sufficient else '需要更多外部信息'
            }
        
        # 使用 LLM 判断
        judge_prompt = f"""
你是一个信息充分性评估专家。请根据用户的问题和检索到的本地上下文，判断信息是否足够回答问题。

用户问题：
{state['user_query']}

本地上下文：
{state['local_context_text'][:3000]} 

请判断：
1. 如果本地上下文包含足够的信息可以完整、准确地回答用户问题，输出 JSON：{{"sufficient": true, "missing": ""}}
2. 如果本地上下文不足以回答问题，输出 JSON：{{"sufficient": false, "missing": "缺少的具体信息描述"}}

只输出 JSON，不要有其他内容，输出的缺少的信息尽量简洁。
"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=judge_prompt)])
            # 清理可能的 markdown 标记
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
                
            result = json.loads(content)
            
            return {
                **state,
                'steps': steps,
                'current_step': '正在评估信息是否充足...',
                'is_sufficient': result.get('sufficient', False),
                'missing_info': result.get('missing', '')
            }
        
        except Exception as e:
            print(f"Judge error: {e}")
            return {
                **state,
                'steps': steps,
                'current_step': '评估出错，默认继续...',
                'is_sufficient': True,  # 出错时默认认为足够
                'missing_info': ''
            }
    
    def _should_use_tools(self, state: AgentState) -> str:
        """条件判断：是否需要使用工具"""
        return "sufficient" if state['is_sufficient'] else "use_tools"
    
    def _tool_planning_node(self, state: AgentState) -> AgentState:
        """节点 3: 工具规划与执行"""
        steps = state.get('steps', [])
        steps.append('工具调用')
        
        if not self.has_llm:
            # Demo 模式
            return {
                **state,
                'steps': steps,
                'current_step': '信息不足，正在使用外部工具(Demo)...',
                'external_context': self._demo_tool_execution(state)
            }
        
        # 使用 LLM 规划工具调用
        tool_prompt = f"""
你是一个工具调用规划专家。用户的问题缺少某些信息，需要使用工具获取。

用户问题：
{state['user_query']}

缺少的信息：
{state['missing_info']}

可用工具：
1. web_search: 搜索互联网获取最新信息、背景知识、概念定义或实时数据
   - 适用场景：查找基础概念、最新新闻、技术文档、通用知识
   - 返回：网页标题、内容摘要、来源链接

2. search_papers: 在学术数据库（ArXiv、Semantic Scholar）中搜索论文
   - 适用场景：查找相关研究、了解学术进展、获取论文详情
   - 返回：论文标题、作者、摘要、发表日期、引用数、相关性评分、PDF链接
   - 支持：自然语言查询、ArXiv分类（如 'cat:cs.CL'）、标题搜索（如 'ti:"transformer"'）

请根据缺失的信息类型选择最合适的工具，并提供精确的查询参数。

输出 JSON 格式：
{{
    "tool": "工具名称",
    "query": "查询字符串"
}}

只输出 JSON，不要有其他内容。
"""
        
        external_context = []
        current_step_desc = '信息不足，正在使用外部工具...'
        
        try:
            # LLM 决定使用哪个工具以及如何调用
            response = self.llm.invoke([HumanMessage(content=tool_prompt)])
            
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
                
            tool_plan = json.loads(content)
            
            tool_name = tool_plan.get('tool')
            query = tool_plan.get('query')
            
            # 执行工具
            if tool_name == 'web_search':
                # 网络搜索
                results = self.web_search.search(query)
                external_context = results
                current_step_desc = f'已完成网络搜索: {query}'
            
            elif tool_name == 'search_papers':
                # ArXiv 论文搜索
                results = self.paper_discovery.search_papers(query)
                external_context = results
                current_step_desc = f'已完成论文搜索: {query}'
            
        except Exception as e:
            # 工具执行出错，降级到 demo 模式
            print(f"Tool execution error: {e}")
            external_context = self._demo_tool_execution(state)
            current_step_desc = '工具执行出错，使用模拟数据'
        
        return {
            **state,
            'steps': steps,
            'current_step': current_step_desc,
            'external_context': external_context
        }
    
    def _demo_tool_execution(self, state: AgentState) -> List[Dict]:
        """Demo 模式的工具执行"""
        return [
            {
                'title': '外部搜索结果',
                'snippet': f'根据"{state["user_query"]}"的外部搜索，找到了相关信息...',
                'source': 'demo'
            }
        ]
    
    def _synthesize_node(self, state: AgentState) -> AgentState:
        """节点 4: 综合生成"""
        steps = state.get('steps', [])
        steps.append('综合生成答案')
        
        if not self.has_llm:
            # Demo 模式
            return {
                **state,
                'steps': steps,
                'current_step': '正在生成最终回答(Demo)...',
                'final_response': self._demo_response(state),
                'citations': self._extract_citations(state)
            }
        
        # 构建综合 prompt
        synthesis_prompt = f"""
你是一个学术论文阅读助手。请根据本地文档和（如果有的话）外部信息，回答用户的问题。

用户问题：
{state['user_query']}

本地文档内容：
{state['local_context_text'][:4000]}
"""
        
        if state.get('external_context'):
            external_text = self._format_external_context(state['external_context'])
            synthesis_prompt += f"""

外部搜索结果：
{external_text}
"""
        
        synthesis_prompt += """

请提供详细、准确的回答，并在引用信息时明确标注来源：
- 对于本地文档的引用，使用 [本地文档: 页X, 章节Y]
- 对于外部信息的引用，使用 [外部来源: 标题]

回答：
"""
        
        final_response = ""
        try:
            # 添加对话历史
            messages = []
            for msg in state.get('chat_history', [])[-5:]:  # 最近5轮
                if msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                else:
                    messages.append(AIMessage(content=msg['content']))
            
            # 添加当前问题和上下文
            messages.append(HumanMessage(content=synthesis_prompt))
            
            response = self.llm.invoke(messages)
            final_response = response.content
        
        except Exception as e:
            # 生成出错，降级到 demo 模式
            print(f"Synthesis error: {e}")
            final_response = self._demo_response(state)
            
        return {
            **state,
            'steps': steps,
            'current_step': '正在生成最终回答...',
            'final_response': final_response,
            'citations': self._extract_citations(state)
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
            'user_id': user_id,
            'paper_id': paper_id,
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
            'user_id': user_id,
            'paper_id': paper_id,
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