"""
chatbox.py
聊天框相关路由：聊天记录管理；会话发送，获取回答
"""

import json
import uuid
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app, g
from route.utils import require_auth
from tasks.chat_tasks import generate_session_title_task

# 定义 Blueprint
chatbox_bp = Blueprint('chatbox', __name__, url_prefix='/api/chatbox')

# ==================== 辅助函数 ====================

def handle_lazy_session_creation(chat_service, session_id, pdf_id, user_query, user_id):
    """
    处理会话的懒创建：
    如果数据库中不存在该 session_id，则同步创建会话，再通过 Celery 异步生成标题
    """
    existing_session = chat_service.get_session(session_id, user_id)

    if not existing_session:
        current_app.logger.info(f"Lazy creating session: {session_id}")

        chat_service.create_session(
            user_id=user_id,
            file_hash=pdf_id,
            title="新对话"
        )

        # 丢给 Celery 异步生成标题（独立 DB 连接，不阻塞请求）
        generate_session_title_task.delay(session_id, user_id, user_query)


# ==================== 路由接口 ====================

@chatbox_bp.route('/new', methods=['POST'])
@require_auth
def new_session():
    """
    接口 A: 处理【新对话】— 仅生成前端 ID，不写库 (懒创建)
    """
    new_id = str(uuid.uuid4())

    return jsonify({
        'sessionId': new_id,
        'title': '新对话',
        'isNew': True,
        'messageCount': 0
    })


@chatbox_bp.route('/message', methods=['POST'])
@require_auth
def send_message():
    """
    接口 B: 发送消息（非流式）
    """
    data = request.get_json()

    user_query = data.get('message')
    session_id = data.get('sessionId')
    pdf_id = data.get('pdfId')
    user_id = g.user_id

    if not session_id or not user_query:
        return jsonify({'error': 'Message and sessionId are required'}), 400

    try:
        agent_service = current_app.agent_service
        chat_service = current_app.chat_service

        # 1. 懒创建会话
        handle_lazy_session_creation(chat_service, session_id, pdf_id, user_query, user_id)

        # 2. 存储用户消息
        chat_service.add_user_message(session_id, user_id, user_query)

        # 3. 获取历史记录
        history = chat_service.get_formatted_history(session_id, user_id, limit=10)

        # 4. 调用 Agent
        '''
            return {
                'response': final_state['final_response'],  # 最终答案
                'citations': final_state['citations'],  # 引用来源
                'steps': final_state['steps'],  # 执行步骤记录
                'context_used': {
                    'local_chunks': len(final_state['local_context']),
                    'external_sources': len(final_state['external_context'])
                }
            }
        '''
        result = agent_service.chat(
            user_query=user_query,
            user_id=user_id,
            paper_id=pdf_id,
            chat_history=history
        )

        # 5. 存储 AI 回答
        chat_service.add_ai_message(
            session_id=session_id,
            user_id=user_id,
            content=result['response'],
            citations=result.get('citations')
        )

        result['sessionId'] = session_id
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Chatbox error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@chatbox_bp.route('/simple-chat', methods=['POST'])
@require_auth
def simple_chat():
    """
    接口 B2: 简单对话模式（基于 PDF 全文，非流式）
    """
    data = request.get_json()

    user_query = data.get('message')
    session_id = data.get('sessionId')
    pdf_id = data.get('pdfId')
    user_id = g.user_id

    if not session_id or not user_query:
        return jsonify({'error': 'Message and sessionId are required'}), 400

    try:
        agent_service = current_app.agent_service
        pdf_service = g.pdf_service
        chat_service = current_app.chat_service

        # 1. 懒创建
        handle_lazy_session_creation(chat_service, session_id, pdf_id, user_query, user_id)

        # 2. 存储用户消息
        chat_service.add_user_message(session_id, user_id, user_query)

        # 3. 历史记录
        history = chat_service.get_formatted_history(session_id, user_id, limit=10)

        # 4. 获取 PDF 全文
        paragraphs = pdf_service.get_paragraph(pdf_id) if pdf_id else []
        context_text = "\n\n".join([p.get('original_text', '') for p in paragraphs]) if paragraphs else ''

        # 5. 调用 Agent simple_chat
        result = agent_service.simple_chat(
            user_query=user_query,
            context_text=context_text,
            chat_history=history
        )

        # 6. 存储 AI 回答
        chat_service.add_ai_message(
            session_id=session_id,
            user_id=user_id,
            content=result['response'],
            citations=result.get('citations')
        )

        result['sessionId'] = session_id
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Simple chat error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@chatbox_bp.route('/stream', methods=['POST'])
@require_auth
def stream_message():
    """
    接口 C: 发送消息（流式 SSE）
    """
    data = request.get_json()

    user_query = data.get('message')
    session_id = data.get('sessionId')
    pdf_id = data.get('pdfId')
    user_id = g.user_id

    if not session_id or not user_query:
        return jsonify({'error': 'Message and sessionId are required'}), 400

    def generate():
        agent_service = current_app.agent_service
        chat_service = current_app.chat_service

        try:
            # 1. 懒创建
            handle_lazy_session_creation(chat_service, session_id, pdf_id, user_query, user_id)

            # 2. 存储用户消息
            chat_service.add_user_message(session_id, user_id, user_query)

            # 3. 历史
            history = chat_service.get_formatted_history(session_id, user_id, limit=10)

            # 4. 流式调用
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

            # 5. 存储 AI 完整回答
            if final_response_data:
                chat_service.add_ai_message(
                    session_id=session_id,
                    user_id=user_id,
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
@require_auth
def delete_session(session_id):
    """
    接口 D: 删除会话
    """
    try:
        chat_service = current_app.chat_service
        user_id = g.user_id

        chat_service.delete_session(session_id, user_id)

        return jsonify({
            'success': True,
            'sessionId': session_id,
            'message': 'Session deleted'
        })

    except Exception as e:
        current_app.logger.error(f"Delete session error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@chatbox_bp.route('/sessions', methods=['GET'])
@require_auth
def list_sessions():
    """
    接口 E: 获取会话列表
    """
    try:
        chat_service = current_app.chat_service
        user_id = g.user_id

        pdf_id = request.args.get('pdfId')
        limit = request.args.get('limit', type=int, default=50)

        sessions = chat_service.list_user_sessions(user_id, file_hash=pdf_id, limit=limit)

        return jsonify({
            'success': True,
            'sessions': sessions,
            'total': len(sessions)
        })

    except Exception as e:
        current_app.logger.error(f"List sessions error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@chatbox_bp.route('/session/<session_id>/messages', methods=['GET'])
@require_auth
def get_session_messages(session_id):
    """
    接口 F: 获取会话的所有消息
    """
    try:
        chat_service = current_app.chat_service
        user_id = g.user_id

        messages = chat_service.get_session_messages_for_ui(session_id, user_id)

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
@require_auth
def update_session_title(session_id):
    """
    接口 G: 更新会话标题
    """
    try:
        data = request.get_json()
        new_title = data.get('title')
        user_id = g.user_id

        if not new_title or not new_title.strip():
            return jsonify({'error': 'Title is required'}), 400

        chat_service = current_app.chat_service
        success = chat_service.update_title(session_id, user_id, new_title.strip())

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