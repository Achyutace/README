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
import json
from pathlib import Path
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from services.pdf_service import PdfService
from services.chat_service import ChatService 
from services.rag_service import RAGService
from services.roadmap_service import AiService
from services.agent_service import AcademicAgentService

# 加载环境变量（如 OpenAI API Key）
load_dotenv()

# 初始化 Flask 应用
app = Flask(__name__)
# 启用 CORS，允许前端跨域访问（前端在不同端口运行）
CORS(app)

# ==================== 应用配置 ====================
# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
STORAGE_ROOT = PROJECT_ROOT / 'storage'

# 创建存储目录结构
(STORAGE_ROOT / 'users').mkdir(parents=True, exist_ok=True)
(STORAGE_ROOT / 'shared').mkdir(parents=True, exist_ok=True)
(STORAGE_ROOT / 'temp').mkdir(parents=True, exist_ok=True)

# 配置路径
app.config['STORAGE_ROOT'] = str(STORAGE_ROOT)
app.config['USERS_FOLDER'] = str(STORAGE_ROOT / 'users')
app.config['SHARED_FOLDER'] = str(STORAGE_ROOT / 'shared')
app.config['TEMP_FOLDER'] = str(STORAGE_ROOT / 'temp')
# 限制上传文件最大为 50MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024


def get_user_id():
    """
    从请求中获取用户ID
    优先级：Header > Query Parameter > Default
    """
    # 从 Header
    user_id = request.headers.get('X-User-Id')
    if user_id:
        return user_id
    
    # 从查询参数获取
    user_id = request.args.get('userId')
    if user_id:
        return user_id
    
    # 默认用户（开发环境）
    return 'default_user'


def get_user_storage_path(user_id: str) -> Path:
    """
    获取用户的存储根目录
    自动创建必要的子目录
    """
    user_path = Path(app.config['USERS_FOLDER']) / user_id
    
    # 创建用户目录结构
    (user_path / 'uploads').mkdir(parents=True, exist_ok=True)
    (user_path / 'cache' / 'paragraphs').mkdir(parents=True, exist_ok=True)
    (user_path / 'cache' / 'translations').mkdir(parents=True, exist_ok=True)
    (user_path / 'cache' / 'images').mkdir(parents=True, exist_ok=True)
    (user_path / 'uploads' / 'vectors').mkdir(parents=True, exist_ok=True)
    (user_path / 'metadata').mkdir(parents=True, exist_ok=True)
    
    return user_path


def get_pdf_service_for_user(user_id: str) -> PdfService:
    """
    为指定用户创建 PdfService 实例
    """
    user_path = get_user_storage_path(user_id)
    upload_folder = str(user_path / 'uploads')
    cache_folder = str(user_path / 'cache')
    return PdfService(upload_folder, cache_folder)


@app.before_request
def before_request():
    """
    在每个请求前执行，设置用户上下文
    """
    g.user_id = get_user_id()
    g.user_path = get_user_storage_path(g.user_id)


# ==================== 服务实例化 ====================
# 聊天服务：负责管理聊天会话和消息历史
chat_service = ChatService()
ai_service = AiService()
# RAG 服务：负责文档索引和检索
rag_service = RAGService()
# Agent 服务：负责智能对话和工具调用
agent_service = AcademicAgentService(rag_service)


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    健康检查接口
    用于确认服务是否正常运行
    """
    return jsonify({
        'status': 'ok',
        'userId': g.user_id,
        'userPath': str(g.user_path)
    })


# ==================== PDF 相关路由 ====================

@app.route('/api/pdf/upload', methods=['POST'])
def upload_pdf():
    """
    上传 PDF 文件接口
    
    请求：multipart/form-data，包含 'file' 字段
    请求头（可选）：X-User-Id（用户标识）
    查询参数（可选）：userId（用户标识）
    
    返回：
    {
        "id": "唯一标识符",
        "filename": "文件名",
        "pageCount": 总页数,
        "userId": "用户ID"
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
        # 获取当前用户的 PDF 服务实例
        pdf_service = get_pdf_service_for_user(g.user_id)
        
        # 调用 PDF 服务保存并处理文件
        # 返回包含 id, filename, pageCount 的字典
        result = pdf_service.save_and_process(file)
        
        # 索引到 RAG 系统
        pdf_id = result['id']
        filepath = pdf_service.get_filepath(pdf_id)
        
        try:
            index_result = rag_service.index_paper(
                pdf_path=filepath,
                paper_id=pdf_id,
                user_id=g.user_id
            )
            result['indexed'] = True
            result['chunks'] = index_result.get('chunks_created', 0)
        except Exception as e:
            print(f"RAG indexing warning: {e}")
            result['indexed'] = False
        
        result['userId'] = g.user_id
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
    # 获取当前用户的 PDF 服务实例
    pdf_service = get_pdf_service_for_user(g.user_id)
    
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
    # 获取当前用户的 PDF 服务实例
    pdf_service = get_pdf_service_for_user(g.user_id)
    
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
        # 获取当前用户的 PDF 服务实例
        pdf_service = get_pdf_service_for_user(g.user_id)
        
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
        # 获取当前用户的 PDF 服务实例
        pdf_service = get_pdf_service_for_user(g.user_id)
        
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
    智能对话接口（RAG - Retrieval Augmented Generation）【已废弃】
    
    请使用 /api/agent/chat 或 /api/agent/chat/stream 代替
    这是旧版本的简单 RAG 实现，新版本使用 Agent 框架，支持工具调用
    
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
        # 获取当前用户的 PDF 服务实例
        pdf_service = get_pdf_service_for_user(g.user_id)
        
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


# ==================== Agent 智能对话接口 ====================

@app.route('/api/agent/chat', methods=['POST'])
def agent_chat():
    """
    Agent 智能对话接口（新版）
    
    使用 Agent 框架实现的高级对话系统：
    - 自动检索本地知识库
    - 智能判断是否需要外部工具
    - 支持联网搜索、论文查找、论文抓取等工具
    - 提供详细的引用来源
    
    请求体：
    {
        "message": "用户问题",
        "userId": "用户ID（可选，默认 'default'）",
        "pdfId": "当前阅读的 PDF ID（可选）",
        "history": [  // 可选，历史对话记录
            {
                "role": "user" | "assistant",
                "content": "对话内容"
            }
        ]
    }
    
    返回：
    {
        "response": "AI 的回答内容",
        "citations": [  // 引用来源
            {
                "source": "local" | "external",
                "page": 页码,
                "section": "章节",
                "text": "引用文本"
            }
        ],
        "steps": ["执行步骤1", "执行步骤2", ...],
        "context_used": {
            "local_chunks": 3,
            "external_sources": 1
        }
    }
    
    错误码：
    400 - 缺少必需参数
    500 - 服务调用失败
    """
    data = request.get_json()
    message = data.get('message')
    user_id = data.get('userId', 'default')
    pdf_id = data.get('pdfId')
    history = data.get('history', [])

    if not message:
        return jsonify({'error': 'message is required'}), 400

    try:
        result = agent_service.chat(
            user_query=message,
            user_id=user_id,
            paper_id=pdf_id,
            chat_history=history
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agent/chat/stream', methods=['POST'])
def agent_chat_stream():
    """
    Agent 流式对话接口
    
    与 /api/agent/chat 功能相同，但使用 Server-Sent Events (SSE) 流式返回
    可以实时看到 Agent 的执行过程（检索、工具调用、生成等）
    
    请求体：与 /api/agent/chat 相同
    
    返回：SSE 流
    
    事件类型：
    - step: 中间步骤更新
      data: {"type": "step", "step": "正在检索...", "data": {...}}
    
    - final: 最终结果
      data: {"type": "final", "response": "...", "citations": [...], "steps": [...]}
    
    - error: 错误
      data: {"type": "error", "error": "错误信息"}
    """
    data = request.get_json()
    message = data.get('message')
    user_id = data.get('userId', 'default')
    pdf_id = data.get('pdfId')
    history = data.get('history', [])

    if not message:
        return jsonify({'error': 'message is required'}), 400

    def generate():
        """SSE 生成器"""
        try:
            for event in agent_service.stream_chat(
                user_query=message,
                user_id=user_id,
                paper_id=pdf_id,
                chat_history=history
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return app.response_class(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


# ==================== RAG 管理接口 ====================

@app.route('/api/rag/stats', methods=['GET'])
def rag_stats():
    """
    获取 RAG 知识库统计信息
    
    查询参数：
    - userId: 用户ID（可选，默认 'default'）
    
    返回：
    {
        "collection_name": "user_default",
        "total_chunks": 150,
        "papers_indexed": 5
    }
    """
    user_id = request.args.get('userId', 'default')
    
    try:
        stats = rag_service.get_collection_stats(user_id)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rag/delete/<pdf_id>', methods=['DELETE'])
def delete_from_rag(pdf_id):
    """
    从 RAG 知识库删除论文
    
    路径参数：
    - pdf_id: PDF 标识符
    
    查询参数：
    - userId: 用户ID（可选，默认 'default'）
    
    返回：
    {
        "success": true,
        "message": "Paper deleted from knowledge base"
    }
    """
    user_id = request.args.get('userId', 'default')
    
    try:
        success = rag_service.delete_paper(pdf_id, user_id)
        if success:
            return jsonify({'success': True, 'message': 'Paper deleted from knowledge base'})
        else:
            return jsonify({'success': False, 'message': 'Failed to delete paper'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
# clear_uploads()


# ==================== 应用启动 ====================

if __name__ == '__main__':
    # debug=True: 开启调试模式，代码修改后自动重启，显示详细错误信息
    # host='0.0.0.0': 允许外部访问（不仅限于 localhost）
    # port=5000: 监听 5000 端口
    app.run(debug=True, host='0.0.0.0', port=5000)
