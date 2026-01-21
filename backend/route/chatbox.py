"""
AI聊天框相关路由

功能：
1. 聊天会话管理
2. 消息发送和接收
3. 聊天记录存储
"""

from flask import Blueprint, request, jsonify, g
import json
import uuid

chatbox_bp = Blueprint('chatbox', __name__, url_prefix='/api/chat')


def init_chatbox_routes(db, agent_service):
    """
    初始化聊天路由

    Args:
        db: 数据库实例
        agent_service: Agent服务实例
    """

    @chatbox_bp.route('/sessions', methods=['GET'])
    def list_sessions():
        """
        获取用户的聊天会话列表

        返回：
        {
            "sessions": [
                {
                    "id": "会话ID",
                    "title": "会话标题",
                    "file_hash": "关联的PDF哈希",
                    "created_time": "创建时间",
                    "updated_time": "更新时间"
                },
                ...
            ]
        }
        """
        user_id = g.user_id
        limit = request.args.get('limit', 50, type=int)

        try:
            sessions = db.list_chat_sessions(user_id, limit)
            return jsonify({'sessions': sessions})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @chatbox_bp.route('/sessions', methods=['POST'])
    def create_session():
        """
        创建新的聊天会话

        请求体：
        {
            "file_hash": "关联的PDF文件哈希（可选）",
            "title": "会话标题（可选）"
        }

        返回：
        {
            "id": "新会话ID",
            "title": "会话标题"
        }
        """
        data = request.get_json() or {}
        user_id = g.user_id
        file_hash = data.get('file_hash')
        title = data.get('title', '新对话')

        try:
            session_id = str(uuid.uuid4())
            db.create_chat_session(session_id, user_id, file_hash, title)

            return jsonify({
                'id': session_id,
                'title': title
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @chatbox_bp.route('/sessions/<session_id>', methods=['GET'])
    def get_session(session_id):
        """获取会话详情和消息历史"""
        try:
            session = db.get_chat_session(session_id)
            if not session:
                return jsonify({'error': 'Session not found'}), 404

            messages = db.get_chat_messages(session_id)

            return jsonify({
                'session': session,
                'messages': messages
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @chatbox_bp.route('/sessions/<session_id>', methods=['DELETE'])
    def delete_session(session_id):
        """删除聊天会话"""
        try:
            db.delete_chat_session(session_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @chatbox_bp.route('/sessions/<session_id>/messages', methods=['GET'])
    def get_messages(session_id):
        """获取会话的消息列表"""
        limit = request.args.get('limit', 100, type=int)

        try:
            messages = db.get_chat_messages(session_id, limit)
            return jsonify({'messages': messages})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @chatbox_bp.route('/sessions/<session_id>/messages', methods=['POST'])
    def send_message(session_id):
        """
        发送消息并获取AI回复

        请求体：
        {
            "message": "用户消息",
            "pdfId": "当前PDF ID（可选）"
        }

        返回：
        {
            "userMessage": {...},
            "assistantMessage": {...},
            "citations": [...]
        }
        """
        data = request.get_json()
        message = data.get('message')
        pdf_id = data.get('pdfId')

        if not message:
            return jsonify({'error': 'message is required'}), 400

        try:
            # 保存用户消息
            user_msg_id = db.add_chat_message(session_id, 'user', message)

            # 获取历史消息作为上下文
            history = db.get_recent_messages(session_id, 10)
            chat_history = [{'role': m['role'], 'content': m['content']} for m in history[:-1]]

            # 调用Agent获取回复
            result = agent_service.chat(
                user_query=message,
                user_id=g.user_id,
                paper_id=pdf_id,
                chat_history=chat_history
            )

            # 保存AI回复
            assistant_msg_id = db.add_chat_message(
                session_id, 'assistant',
                result['response'],
                result.get('citations', [])
            )

            # 如果是首条消息，更新会话标题
            if len(history) <= 1:
                title = message[:50] + ('...' if len(message) > 50 else '')
                db.update_chat_session(session_id, title)

            return jsonify({
                'userMessage': {
                    'id': user_msg_id,
                    'role': 'user',
                    'content': message
                },
                'assistantMessage': {
                    'id': assistant_msg_id,
                    'role': 'assistant',
                    'content': result['response'],
                    'citations': result.get('citations', [])
                },
                'steps': result.get('steps', [])
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @chatbox_bp.route('/sessions/<session_id>/messages/stream', methods=['POST'])
    def send_message_stream(session_id):
        """
        发送消息并流式获取AI回复（SSE）

        请求体同 send_message
        """
        data = request.get_json()
        message = data.get('message')
        pdf_id = data.get('pdfId')

        if not message:
            return jsonify({'error': 'message is required'}), 400

        # 保存用户消息
        db.add_chat_message(session_id, 'user', message)

        # 获取历史
        history = db.get_recent_messages(session_id, 10)
        chat_history = [{'role': m['role'], 'content': m['content']} for m in history[:-1]]

        def generate():
            try:
                final_response = ""
                final_citations = []

                for event in agent_service.stream_chat(
                    user_query=message,
                    user_id=g.user_id,
                    paper_id=pdf_id,
                    chat_history=chat_history
                ):
                    if event.get('type') == 'final':
                        final_response = event.get('response', '')
                        final_citations = event.get('citations', [])

                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                # 保存AI回复
                if final_response:
                    db.add_chat_message(session_id, 'assistant', final_response, final_citations)

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

        from flask import current_app
        return current_app.response_class(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    return chatbox_bp
