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
    if not hasattr(current_app, 'agent_service') or \
       not hasattr(current_app, 'chat_service') or \
       not hasattr(current_app, 'storage_service'):
        raise RuntimeError("Services are not initialized in the application context.")
    return current_app.agent_service, current_app.chat_service, current_app.storage_service

def async_generate_and_update_title(app, agent_service, storage_service, session_id, user_query):
    """
    后台线程任务：调用 Agent 生成标题并更新数据库
    """
    with app.app_context():
        try:
            new_title = agent_service.generate_session_title(user_query) or user_query[:20]
            #  更新
            storage_service.update_chat_session_title(session_id, new_title)
            current_app.logger.info(f"Auto-generated title for session {session_id}: {new_title}")
        except Exception as e:
            current_app.logger.error(f"Title generation failed: {e}")

def handle_lazy_session_creation(storage_service, agent_service, session_id, pdf_id, user_query):
    """
    处理会话的懒创建：
    如果数据库中不存在该 session_id，则创建会话并启动标题生成线程
    """
    # 查询
    session = storage_service.get_chat_session(session_id)
    
    if not session:
        current_app.logger.info(f"Lazy creating session: {session_id}")
        
        # 2. 创建会话 (使用默认标题)
        storage_service.create_chat_session(
            session_id=session_id,
            file_hash=pdf_id,
            title="新对话"
        )
        
        # 3. 启动异步线程生成标题 
        real_app = current_app._get_current_object()
        thread = threading.Thread(
            target=async_generate_and_update_title,
            args=(real_app, agent_service, storage_service, session_id, user_query)
        )
        thread.start()

# ==================== 路由接口 ====================

@chatbox_bp.route('/new', methods=['POST'])
def new_session():
    """
    接口 A: 处理【新对话】
    """
    new_id = str(uuid.uuid4())
    
    return jsonify({
        'sessionId': new_id,
        'title': '新对话',
        'isNew': True,
        'messageCount': 0
    })

@chatbox_bp.route('/message', methods=['POST'])
def send_message():
    """
    接口 B: 发送消息（非流式）
    """
    data = request.get_json()
    
    user_query = data.get('message')
    session_id = data.get('sessionId') 
    pdf_id = data.get('pdfId')
    user_id = data.get('userId', 'default')

    if not session_id or not user_query:
        return jsonify({'error': 'Message and sessionId are required'}), 400

    try:
        # 获取三个服务
        agent_service, chat_service, storage_service = get_services()

        # 1. 处理懒创建逻辑 
        handle_lazy_session_creation(storage_service, agent_service, session_id, pdf_id, user_query)

        # 2. 存储用户消息
        storage_service.add_chat_message(
            session_id=session_id, 
            role="user", 
            content=user_query
        )

        # 3. 获取并处理历史记录
        # 从 DB 拿原始数据
        raw_messages = storage_service.get_chat_messages(session_id)
        # 用 ChatService 处理成 Agent 需要的格式
        history = chat_service.process_history_for_agent(raw_messages, limit=10)

        # 4. 调用 Agent
        result = agent_service.chat(
            user_query=user_query,
            user_id=user_id,
            paper_id=pdf_id,
            chat_history=history
        )
        
        # 5. 存储 AI 回答 
        msg_id = storage_service.add_chat_message(
            session_id=session_id, 
            role="assistant", 
            content=result['response'], 
            citations=result.get('citations')
        )
        
        # 6. 构造返回结果
        result['sessionId'] = session_id
      
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Chatbox error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@chatbox_bp.route('/stream', methods=['POST'])
def stream_message():
    """
    接口 C: 发送消息（流式 SSE）
    """
    data = request.get_json()
    
    user_query = data.get('message')
    session_id = data.get('sessionId')
    pdf_id = data.get('pdfId')
    user_id = data.get('userId', 'default')

    if not session_id or not user_query:
        return jsonify({'error': 'Message and sessionId are required'}), 400

    def generate():
        # 在生成器内部获取服务
        agent_service, chat_service, storage_service = get_services()
        
        try:
            # 1. 处理懒创建逻辑
            handle_lazy_session_creation(storage_service, agent_service, session_id, pdf_id, user_query)
            
            # 2. 存储用户消息
            storage_service.add_chat_message(session_id, "user", user_query)
            
            # 3. 获取并处理历史
            raw_messages = storage_service.get_chat_messages(session_id)
            history = chat_service.process_history_for_agent(raw_messages, limit=10)
            
            # 4. 流式调用 Agent
            final_response_data = None
            
            for event in agent_service.stream_chat(
                user_query=user_query,
                user_id=user_id,
                paper_id=pdf_id,
                chat_history=history
            ):
                if event.get('type') == 'final':
                    final_response_data = event
                
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            
            # 5. 流结束后，存储 AI 完整回答
            if final_response_data:
                storage_service.add_chat_message(
                    session_id=session_id,
                    role="assistant",
                    content=final_response_data['response'],
                    citations=final_response_data.get('citations')
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

@chatbox_bp.route('/session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """
    接口 D: 删除会话
    删除会话及其所有消息
    """
    try:
        # 获取服务
        _, _, storage_service = get_services()
        
        # 检查会话是否存在
        session = storage_service.get_chat_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # 删除会话及其所有消息
        deleted_count = storage_service.delete_chat_session(session_id)
        
        return jsonify({
            'success': True,
            'sessionId': session_id,
            'deletedMessages': deleted_count,
            'message': f'Session deleted with {deleted_count} messages'
        })
        
    except Exception as e:
        current_app.logger.error(f"Delete session error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@chatbox_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    接口 E: 获取会话列表
    可选参数：
    - pdfId: 筛选特定PDF的会话
    - limit: 返回数量限制（默认50）
    """
    try:
        # 获取服务
        _, chat_service, storage_service = get_services()
        
        # 获取查询参数
        pdf_id = request.args.get('pdfId')
        limit = request.args.get('limit', type=int, default=50)
        
        # 从 storage_service 获取原始数据，再用 chat_service 格式化
        raw_sessions = storage_service.list_chat_sessions(file_hash=pdf_id, limit=limit)
        sessions = chat_service.format_session_list(raw_sessions)

        return jsonify({
            'success': True,
            'sessions': sessions,
            'total': len(sessions)
        })
        
    except Exception as e:
        current_app.logger.error(f"List sessions error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@chatbox_bp.route('/session/<session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """
    接口 F: 获取会话的所有消息
    """
    try:
        # 获取服务
        _, chat_service, storage_service = get_services()
        
        # 检查会话是否存在
        session = storage_service.get_chat_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        # 从 storage_service 获取原始消息，再用 chat_service 格式化
        raw_messages = storage_service.get_chat_messages(session_id)
        messages = chat_service.format_messages(raw_messages)

        return jsonify({
            'success': True,
            'sessionId': session_id,
            'messages': messages,
            'total': len(messages)
        })
        
    except Exception as e:
        current_app.logger.error(f"Get messages error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@chatbox_bp.route('/session/<session_id>/title', methods=['PUT'])
def update_session_title(session_id):
    """
    接口 G: 更新会话标题
    """
    try:
        data = request.get_json()
        new_title = data.get('title')
        
        if not new_title or not new_title.strip():
            return jsonify({'error': 'Title is required'}), 400

        # 获取服务
        _, _, storage_service = get_services()

        # 调用 storage_service 更新标题
        success = storage_service.update_chat_session_title(session_id, new_title.strip())

        if not success:
            return jsonify({'error': 'Session not found or update failed'}), 404
        
        return jsonify({
            'success': True,
            'sessionId': session_id,
            'title': new_title.strip()
        })
        
    except Exception as e:
        current_app.logger.error(f"Update title error: {str(e)}")
        return jsonify({'error': str(e)}), 500