"""
聊天框相关路由：接收信息，agent处理问题，输出回答
"""

import json
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app

# 定义 Blueprint
chatbox_bp = Blueprint('chatbox', __name__, url_prefix='/api/chatbox')

def get_agent_service():
    """
    获取 Agent Service 实例
    """
    if hasattr(current_app, 'agent_service'):
        return current_app.agent_service
    else:
        raise RuntimeError("Agent Service is not initialized in the application context.")

@chatbox_bp.route('/message', methods=['POST'])
def send_message():
    """
    发送消息（非流式）
    
    前端需在 Body 中提供完整的对话历史，因为后端不存储记录。
    
    Request Body:
    {
        "message": "用户当前的问题",
        "history": [
            {"role": "user", "content": "之前的问"},
            {"role": "assistant", "content": "之前的答"}
        ],
        "pdfId": "必选，当前关联的 PDF ID",
        "userId": "可选，用户ID"
    }
    
    Response:
    {
        "response": "AI 的完整回答",
        "citations": [...],
        "steps": [...]
    }
    """
    data = request.get_json()
    
    user_query = data.get('message')
    history = data.get('history', [])
    pdf_id = data.get('pdfId')
    user_id = data.get('userId', 'default')

    if not user_query:
        return jsonify({'error': 'Message is required'}), 400

    try:
        agent_service = get_agent_service()
        
        # 调用 Agent 进行对话
        # 注意：我们将前端传来的 history 直接传给 agent，实现无状态对话
        result = agent_service.chat(
            user_query=user_query,
            user_id=user_id,
            paper_id=pdf_id,
            chat_history=history
        )
        
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Chatbox error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@chatbox_bp.route('/stream', methods=['POST'])
def stream_message():
    """
    发送消息（流式 SSE）
    
    用于前端实现打字机效果。
    
    Request Body: 同 /message
    
    Response: Server-Sent Events (text/event-stream)
    Events:
        - step: 中间思考步骤/工具调用
        - final: 最终回答片段或完整结果
        - error: 错误信息
    """
    data = request.get_json()
    
    user_query = data.get('message')
    history = data.get('history', [])
    pdf_id = data.get('pdfId')
    user_id = data.get('userId', 'default')

    if not user_query:
        return jsonify({'error': 'Message is required'}), 400

    def generate():
        try:
            agent_service = get_agent_service()
            
            # 使用 stream_chat 生成器
            for event in agent_service.stream_chat(
                user_query=user_query,
                user_id=user_id,
                paper_id=pdf_id,
                chat_history=history
            ):
                # 将字典转换为 JSON 字符串并符合 SSE 格式
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            current_app.logger.error(f"Stream error: {str(e)}")
            error_event = {'type': 'error', 'error': str(e)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    # 返回流式响应
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no', # 禁用 Nginx 缓冲
            'Connection': 'keep-alive'
        }
    )