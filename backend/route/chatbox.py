"""
聊天框相关路由：接收信息，agent处理问题，输出回答
"""

import json
import uuid
import threading
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app

# 定义 Blueprint
chatbox_bp = Blueprint('chatbox', __name__, url_prefix='/api/chatbox')

# ==================== 辅助函数 ====================

def get_services():
    """获取服务实例的辅助函数"""
    if not hasattr(current_app, 'agent_service') or not hasattr(current_app, 'chat_service'):
        raise RuntimeError("Services are not initialized in the application context.")
    return current_app.agent_service, current_app.chat_service

def async_generate_and_update_title(app, agent_service, chat_service, session_id, user_query):
    """
    后台线程任务：调用 Agent 生成标题并更新数据库
    """
    with app.app_context():
        try:
            new_title = agent_service.generate_session_title(user_query) or user_query[:20]
            chat_service.update_session_title(session_id, new_title)
            current_app.logger.info(f"Auto-generated title for session {session_id}: {new_title}")
        except Exception as e:
            current_app.logger.error(f"Title generation failed: {e}")

def handle_lazy_session_creation(chat_service, agent_service, session_id, pdf_id, user_query):
    """
    处理会话的懒创建：
    如果数据库中不存在该 session_id，则创建会话并启动标题生成线程
    """
    session = chat_service.storage.get_chat_session(session_id)
    
    if not session:
        current_app.logger.info(f"Lazy creating session: {session_id}")
        
        # 2. 创建会话 (使用默认标题)
        chat_service.storage.create_chat_session(
            session_id=session_id,
            file_hash=pdf_id,
            title="新对话"
        )
        
        # 3. 启动异步线程生成标题 
        real_app = current_app._get_current_object()
        thread = threading.Thread(
            target=async_generate_and_update_title,
            args=(real_app, agent_service, chat_service, session_id, user_query)
        )
        thread.start()

# ==================== 路由接口 ====================

@chatbox_bp.route('/new', methods=['POST'])
def new_session():
    """
    接口 A: 处理【新对话】
    策略：纯内存生成 UUID，不操作数据库，实现“零垃圾数据”。
    """
    new_id = str(uuid.uuid4())
    
    return jsonify({
        'sessionId': new_id,
        'title': '新对话',
        'isNew': True, # 标记为新会话，前端可据此清空界面
        'messageCount': 0
    })

@chatbox_bp.route('/message', methods=['POST'])
def send_message():
    """
    接口 B: 发送消息（非流式）
    策略：懒创建会话 -> 存用户消息 -> 查DB历史 -> Agent推理 -> 存AI消息
    """
    data = request.get_json()
    
    user_query = data.get('message')
    session_id = data.get('sessionId') 
    pdf_id = data.get('pdfId')
    user_id = data.get('userId', 'default')

    if not session_id or not user_query:
        return jsonify({'error': 'Message and sessionId are required'}), 400

    try:
        agent_service, chat_service = get_services()

        # 1. 处理懒创建逻辑 (如果是第一条消息)
        handle_lazy_session_creation(chat_service, agent_service, session_id, pdf_id, user_query)

        # 2. 存储用户消息
        chat_service.add_message(session_id, "user", user_query)

        # 3. 从数据库获取历史记录 (不再依赖前端传来的 history)
        history = chat_service.get_chat_history_for_agent(session_id, limit=10)

        # 4. 调用 Agent
        result = agent_service.chat(
            user_query=user_query,
            user_id=user_id,
            paper_id=pdf_id,
            chat_history=history
        )
        
        # 5. 存储 AI 回答
        chat_service.add_message(
            session_id, 
            "assistant", 
            result['response'], 
            citations=result.get('citations'),
            steps=result.get('steps')
        )
        
        # 返回结果带上 sessionId
        result['sessionId'] = session_id
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Chatbox error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@chatbox_bp.route('/stream', methods=['POST'])
def stream_message():
    """
    接口 C: 发送消息（流式 SSE）
    策略：同上，但在流结束时存储 AI 完整回答
    """
    data = request.get_json()
    
    user_query = data.get('message')
    session_id = data.get('sessionId')
    pdf_id = data.get('pdfId')
    user_id = data.get('userId', 'default')

    if not session_id or not user_query:
        return jsonify({'error': 'Message and sessionId are required'}), 400

    def generate():
        # 在生成器内部获取服务和上下文
        agent_service, chat_service = get_services()
        
        try:
            # 1. 处理懒创建逻辑
            handle_lazy_session_creation(chat_service, agent_service, session_id, pdf_id, user_query)
            
            # 2. 存储用户消息
            chat_service.add_message(session_id, "user", user_query)
            
            # 3. 获取历史
            history = chat_service.get_chat_history_for_agent(session_id, limit=10)
            
            # 4. 流式调用 Agent
            # 我们需要捕获最终的完整回答以便存储
            final_response_data = None
            
            for event in agent_service.stream_chat(
                user_query=user_query,
                user_id=user_id,
                paper_id=pdf_id,
                chat_history=history
            ):
                # 如果是 final 事件，记录下来用于存储
                if event.get('type') == 'final':
                    final_response_data = event
                
                # 发送给前端
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            # 5. 流结束后，存储 AI 完整回答
            if final_response_data:
                chat_service.add_message(
                    session_id,
                    "assistant",
                    final_response_data['response'],
                    citations=final_response_data.get('citations'),
                    steps=final_response_data.get('steps')
                )
                
        except Exception as e:
            current_app.logger.error(f"Stream error: {str(e)}")
            error_event = {'type': 'error', 'error': str(e)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )