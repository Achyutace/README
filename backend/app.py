"""
README AI 辅助阅读应用 - Flask 后端服务

功能：
- PDF 上传、文本提取、图片提取
- AI 路线图生成、文档摘要
- 智能对话（Agent + RAG）
- 段落翻译、笔记管理
"""

import os
from pathlib import Path
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from dotenv import load_dotenv

from services.pdf_service import PdfService
from services.ai_service import AiService
from services.rag_service import RAGService
from services.agent_service import AcademicAgentService
from services.translate_service import TranslateService
from services.image_service import ImageService
from models.database import Database

from route.chatbox import chatbox_bp, init_chatbox_routes
from route.translate import translate_bp, init_translate_routes
from route.notes import notes_bp, init_notes_routes
from route.paper import paper_bp, init_paper_routes

load_dotenv()

app = Flask(__name__)
CORS(app)

# ==================== 配置 ====================
STORAGE_ROOT = Path(os.path.dirname(__file__)) / 'storage'
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = str(STORAGE_ROOT / 'uploads')
app.config['CACHE_FOLDER'] = str(STORAGE_ROOT / 'cache')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CACHE_FOLDER'], exist_ok=True)

# ==================== 服务实例化 ====================
db = Database(str(STORAGE_ROOT / 'readme.db'))
pdf_service = PdfService(app.config['UPLOAD_FOLDER'], app.config['CACHE_FOLDER'])
ai_service = AiService()
rag_service = RAGService(str(STORAGE_ROOT / 'chroma_db'))
agent_service = AcademicAgentService(rag_service)
translate_service = TranslateService(db=db)
image_service = ImageService(db=db, cache_dir=str(STORAGE_ROOT / 'cache' / 'images'))


def get_pdf_service(user_id: str = None) -> PdfService:
    return pdf_service


# ==================== 注册蓝图 ====================
init_chatbox_routes(db, agent_service)
init_translate_routes(db, translate_service, get_pdf_service)
init_notes_routes(db, get_pdf_service)
init_paper_routes(db, get_pdf_service, rag_service, image_service)

app.register_blueprint(chatbox_bp)
app.register_blueprint(translate_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(paper_bp)


@app.before_request
def before_request():
    g.user_id = request.headers.get('X-User-Id', 'default_user')


# ==================== 基础路由 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})


# ==================== PDF 路由 ====================

@app.route('/api/pdf/upload', methods=['POST'])
def upload_pdf():
    """上传 PDF 文件"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400

    try:
        result = pdf_service.save_and_process(file)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/<pdf_id>/text', methods=['GET'])
def get_pdf_text(pdf_id):
    """提取 PDF 文本"""
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
    """获取 PDF 信息"""
    try:
        result = pdf_service.get_info(pdf_id)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/<pdf_id>/paragraphs', methods=['GET'])
def get_pdf_paragraphs(pdf_id):
    """获取 PDF 段落结构"""
    try:
        paragraphs = pdf_service.parse_paragraphs(pdf_id)
        return jsonify({'paragraphs': paragraphs})
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/<pdf_id>/images', methods=['GET'])
def get_pdf_images(pdf_id):
    """获取 PDF 图片列表"""
    try:
        images = pdf_service.get_images_list(pdf_id)
        return jsonify({'images': images})
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf/image/<image_id>', methods=['GET'])
def get_image_data(image_id):
    """获取图片 Base64 数据"""
    try:
        image_data = pdf_service.get_image_data(image_id)
        if image_data is None:
            return jsonify({'error': 'Image not found'}), 404
        return jsonify(image_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== AI 路由 ====================

@app.route('/api/ai/roadmap', methods=['POST'])
def generate_roadmap():
    """生成学习路线图"""
    data = request.get_json()
    pdf_id = data.get('pdfId')

    if not pdf_id:
        return jsonify({'error': 'pdfId is required'}), 400

    try:
        text = pdf_service.extract_text(pdf_id)['text']
        roadmap = ai_service.generate_roadmap(text)
        return jsonify({'roadmap': roadmap})
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/summary', methods=['POST'])
def generate_summary():
    """生成文档摘要"""
    data = request.get_json()
    pdf_id = data.get('pdfId')

    if not pdf_id:
        return jsonify({'error': 'pdfId is required'}), 400

    try:
        text = pdf_service.extract_text(pdf_id)['text']
        summary = ai_service.generate_summary(text)
        return jsonify(summary)
    except FileNotFoundError:
        return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== 启动 ====================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
