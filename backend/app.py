"""
README AI 辅助阅读应用 - Flask 后端服务

功能概述：
1. PDF 文件上传、存储和文本提取
2. AI 功能：学习路线图生成、文档摘要、翻译、智能对话
3. RESTful API 接口，支持跨域请求

技术栈：
- Flask: Web 框架
- Flask-CORS: 跨域资源共享支持
- PyPDF2/pdfplumber: PDF 文本提取
- OpenAI API: AI 功能实现
"""

import os
import shutil
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from services.pdf_service import PdfService
from services.ai_service import AiService
from services.chat_service import ChatService

# 加载环境变量（如 OpenAI API Key）
load_dotenv()

# 初始化 Flask 应用
app = Flask(__name__)
# 启用 CORS，允许前端跨域访问（前端在不同端口运行）
CORS(app)

# ==================== 应用配置 ====================
# 设置 PDF 上传目录为 backend/uploads/
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
# 限制上传文件最大为 50MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# 确保上传目录存在，不存在则创建
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== 服务实例化 ====================
# PDF 服务：负责文件存储、文本提取等
pdf_service = PdfService(app.config['UPLOAD_FOLDER'])
# AI 服务：负责调用 OpenAI API 实现各种 AI 功能
ai_service = AiService()
# 聊天服务：负责管理聊天会话和消息历史
chat_service = ChatService()


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    健康检查接口
    用于确认服务是否正常运行
    """
    return jsonify({'status': 'ok'})


# ==================== PDF 相关路由 ====================

@app.route('/api/pdf/upload', methods=['POST'])
def upload_pdf():
    """
    上传 PDF 文件接口
    
    请求：multipart/form-data，包含 'file' 字段
    
    返回：
    {
        "id": "唯一标识符",
        "filename": "文件名",
        "pageCount": 总页数
    }
    
    错误码：
    400 - 文件缺失或格式错误
    500 - 服务器处理错误
    """
    # 检查请求中是否包含文件
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    # 检查文件名是否为空
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # 验证文件类型，只允许 PDF
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    try:
        # 调用 PDF 服务保存并处理文件
        # 返回包含 id, filename, pageCount 的字典
        result = pdf_service.save_and_process(file)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/<pdf_id>/text', methods=['GET'])
def get_pdf_text(pdf_id):
    """
    提取 PDF 文本内容接口
    
    路径参数：
    - pdf_id: PDF 的唯一标识符
    
    查询参数（可选）：
    - page: 指定页码（从 1 开始），不传则提取全部页面
    
    返回：
    {
        "text": "提取的文本内容",
        "blocks": [
            {
                "text": "文本块内容",
                "pageNumber": 页码,
                "bbox": [x0, y0, x1, y1]  # 坐标信息，用于高亮定位
            }
        ]
    }
    
    错误码：
    404 - PDF 文件不存在
    500 - 文本提取失败
    """
    # 获取可选的页码参数
    page = request.args.get('page', type=int)
    try:
        result = pdf_service.extract_text(pdf_id, page)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/<pdf_id>/info', methods=['GET'])
def get_pdf_info(pdf_id):
    """
    获取 PDF 基本信息接口
    
    路径参数：
    - pdf_id: PDF 的唯一标识符
    
    返回：
    {
        "filename": "文件名",
        "pageCount": 总页数,
        "fileSize": 文件大小（字节）
    }
    """
    try:
        result = pdf_service.get_info(pdf_id)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== AI 功能相关路由 ====================

@app.route('/api/ai/roadmap', methods=['POST'])
def generate_roadmap():
    """
    生成学习路线图接口
    
    基于 PDF 内容，使用 AI 分析并生成结构化的学习路线图
    包含知识点节点和它们之间的依赖关系
    
    请求体：
    {
        "pdfId": "PDF 标识符"
    }
    
    返回：
    {
        "roadmap": {
            "nodes": [
                {
                    "id": "节点ID",
                    "type": "节点类型",
                    "data": { "label": "知识点名称" },
                    "position": { "x": 0, "y": 0 }
                }
            ],
            "edges": [
                {
                    "id": "边ID",
                    "source": "起始节点ID",
                    "target": "目标节点ID"
                }
            ]
        }
    }
    
    错误码：
    400 - 缺少必需参数
    404 - PDF 不存在
    500 - AI 服务调用失败
    """
    data = request.get_json()
    pdf_id = data.get('pdfId')

    if not pdf_id:
        return jsonify({'error': 'pdfId is required'}), 400

    try:
        # 提取 PDF 的全文本内容
        text = pdf_service.extract_text(pdf_id)['text']
        # 调用 AI 服务生成路线图
        roadmap = ai_service.generate_roadmap(text)
        return jsonify({'roadmap': roadmap})
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/summary', methods=['POST'])
def generate_summary():
    """
    生成文档摘要接口
    
    使用 AI 分析 PDF 内容，生成结构化的摘要
    包含核心主题、关键要点、学习建议等
    
    请求体：
    {
        "pdfId": "PDF 标识符"
    }
    
    返回：
    {
        "mainTopic": "核心主题",
        "keyPoints": ["要点1", "要点2", ...],
        "difficulty": "难度级别",
        "estimatedTime": "预计阅读时间",
        "recommendations": ["建议1", "建议2", ...]
    }
    
    错误码：
    400 - 缺少必需参数
    404 - PDF 不存在
    500 - AI 服务调用失败
    """
    data = request.get_json()
    pdf_id = data.get('pdfId')

    if not pdf_id:
        return jsonify({'error': 'pdfId is required'}), 400

    try:
        # 提取 PDF 的全文本内容
        text = pdf_service.extract_text(pdf_id)['text']
        # 调用 AI 服务生成摘要
        summary = ai_service.generate_summary(text)
        return jsonify(summary)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/translate', methods=['POST'])
def translate_text():
    """
    文本翻译接口
    
    使用 AI 将选中的文本翻译成目标语言
    支持智能语言检测和上下文理解
    
    请求体：
    {
        "text": "待翻译的文本"
    }
    
    返回：
    {
        "originalText": "原文",
        "translatedText": "译文",
        "sourceLanguage": "源语言",
        "targetLanguage": "目标语言"
    }
    
    错误码：
    400 - 缺少必需参数
    500 - AI 服务调用失败
    """
    data = request.get_json()
    text = data.get('text')

    if not text:
        return jsonify({'error': 'text is required'}), 400

    try:
        # 调用 AI 服务进行翻译
        translation = ai_service.translate(text)
        return jsonify(translation)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/chat', methods=['POST'])
def chat():
    """
    智能对话接口（RAG - Retrieval Augmented Generation）
    
    基于 PDF 内容进行上下文感知的问答对话
    AI 会参考文档内容回答用户问题，并提供引用来源
    
    请求体：
    {
        "pdfId": "PDF 标识符",
        "sessionId": "会话ID（可选，不提供则创建新会话）",
        "message": "用户问题"
    }
    
    返回：
    {
        "sessionId": "会话ID",
        "response": "AI 的回答内容",
        "citations": [  // 引用的原文位置
            {
                "text": "引用文本",
                "pageNumber": 页码,
                "bbox": [x0, y0, x1, y1]
            }
        ]
    }
    
    错误码：
    400 - 缺少必需参数
    404 - PDF 不存在
    500 - AI 服务调用失败
    """
    data = request.get_json()
    pdf_id = data.get('pdfId')
    message = data.get('message')
    session_id = data.get('sessionId')

    if not pdf_id or not message:
        return jsonify({'error': 'pdfId and message are required'}), 400

    try:
        # 如果没有提供sessionId，创建新会话
        if not session_id:
            session = chat_service.create_session(pdf_id)
            session_id = session['id']
        
        # 添加用户消息
        chat_service.add_message(session_id, 'user', message)
        
        # 获取历史消息作为上下文
        history = chat_service.get_messages(session_id)
        history_for_ai = [{'role': m['role'], 'content': m['content']} for m in history[:-1]]  # 排除刚添加的消息
        
        # 提取 PDF 的全文本作为上下文
        text = pdf_service.extract_text(pdf_id)['text']
        # 调用 AI 服务进行对话
        ai_response = ai_service.chat(text, message, history_for_ai)
        
        # 添加AI回复到会话
        chat_service.add_message(session_id, 'assistant', ai_response['response'], ai_response.get('citations', []))
        
        return jsonify({
            'sessionId': session_id,
            'response': ai_response['response'],
            'citations': ai_response.get('citations', [])
        })
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 聊天会话管理路由 ====================

@app.route('/api/chat/sessions', methods=['GET'])
def list_chat_sessions():
    """
    获取聊天会话列表
    
    查询参数：
    - pdfId: 可选，筛选特定PDF的会话
    
    返回：
    {
        "sessions": [
            {
                "id": "会话ID",
                "pdfId": "PDF ID",
                "title": "会话标题",
                "createdAt": "创建时间",
                "updatedAt": "更新时间",
                "messageCount": 消息数量
            }
        ]
    }
    """
    pdf_id = request.args.get('pdfId')
    sessions = chat_service.list_sessions(pdf_id)
    return jsonify({'sessions': sessions})


@app.route('/api/chat/sessions', methods=['POST'])
def create_chat_session():
    """
    创建新的聊天会话
    
    请求体：
    {
        "pdfId": "PDF 标识符",
        "title": "会话标题（可选）"
    }
    
    返回：
    {
        "session": {
            "id": "会话ID",
            "pdfId": "PDF ID",
            "title": "会话标题",
            "createdAt": "创建时间",
            "updatedAt": "更新时间",
            "messageCount": 0
        }
    }
    """
    data = request.get_json()
    pdf_id = data.get('pdfId')
    title = data.get('title')
    
    if not pdf_id:
        return jsonify({'error': 'pdfId is required'}), 400
    
    session = chat_service.create_session(pdf_id, title)
    return jsonify({'session': session})


@app.route('/api/chat/sessions/<session_id>', methods=['GET'])
def get_chat_session(session_id):
    """
    获取特定会话的详细信息和消息历史
    
    返回：
    {
        "session": {会话信息},
        "messages": [消息列表]
    }
    """
    session = chat_service.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    messages = chat_service.get_messages(session_id)
    return jsonify({
        'session': session,
        'messages': messages
    })


@app.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
def delete_chat_session(session_id):
    """
    删除聊天会话
    
    返回：
    {
        "success": true
    }
    """
    success = chat_service.delete_session(session_id)
    if not success:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({'success': True})


# ==================== 工具函数 ====================

def clear_uploads():
    """
    清空上传目录中的所有内容，但保留目录本身
    
    用途：
    - 开发调试时清理测试文件
    - 定期清理过期文件（可配合定时任务）
    
    注意：会跳过 .gitkeep 文件（用于 Git 追踪空目录）
    """
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            # 保留 .gitkeep 文件
            if filename == '.gitkeep':
                continue
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                # 删除文件或符号链接
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                # 递归删除目录
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')


# 取消注释以在启动时清空上传目录（谨慎使用！）
clear_uploads()


# ==================== 应用启动 ====================

if __name__ == '__main__':
    # debug=True: 开启调试模式，代码修改后自动重启，显示详细错误信息
    # host='0.0.0.0': 允许外部访问（不仅限于 localhost）
    # port=5000: 监听 5000 端口
    app.run(debug=True, host='0.0.0.0', port=5000)
