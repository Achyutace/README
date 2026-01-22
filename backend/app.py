import os
from pathlib import Path
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from dotenv import load_dotenv

# ==================== 1. 导入服务类 ====================
from services.pdf_service import PdfService
from services.storage_service import StorageService
from services.rag_service import RAGService
from services.translate_service import TranslateService
from services.agent_service import AcademicAgentService
from services.chat_service import ChatService  

# ==================== 2. 导入路由蓝图 ====================
from route.upload import upload_bp
from route.chatbox import chatbox_bp
from route.highlight import highlight_bp
from route.translate import translate_bp

# 加载环境变量 (.env)
load_dotenv()

# 初始化 Flask 应用
app = Flask(__name__)
# 允许跨域，支持前端从不同端口访问
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ==================== 3. 基础配置与路径 ====================
# 获取当前文件所在目录的父级作为项目根目录
BASE_DIR = Path(__file__).resolve().parent
STORAGE_ROOT = BASE_DIR / 'storage'
USERS_DIR = STORAGE_ROOT / 'users'
CHROMA_DIR = STORAGE_ROOT / 'chroma_db'

# 确保基础目录存在
STORAGE_ROOT.mkdir(exist_ok=True)
USERS_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

# 将配置存入 app.config 以便在其他地方调用
app.config['STORAGE_ROOT'] = str(STORAGE_ROOT)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 限制上传大小为 100MB

# ==================== 4. 初始化全局服务 (单例) ====================

# (1) 存储服务：负责数据库交互和文件持久化
# 路由中通过 current_app.storage_service 访问
storage_service = StorageService(storage_root=str(STORAGE_ROOT))
app.storage_service = storage_service

# (2) RAG 服务：负责向量检索
# 路由中通过 current_app.rag_service 访问
rag_service = RAGService(chroma_dir=str(CHROMA_DIR))
app.rag_service = rag_service

# (3) 翻译服务：负责调用 LLM 进行翻译
# 依赖 storage_service.db 进行缓存
# 路由中通过 current_app.translate_service 访问
translate_service = TranslateService(
    db=storage_service.db,
    model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
    temperature=0.3
)
app.translate_service = translate_service

# (4) Agent 服务：负责聊天和智能问答
# 依赖 rag_service 进行上下文检索
# 路由中通过 current_app.agent_service 访问
agent_service = AcademicAgentService(rag_service=rag_service)
app.agent_service = agent_service

# (5) Chat 服务：负责会话管理业务逻辑 [新增]
# 依赖 storage_service 进行持久化
# 路由中通过 current_app.chat_service 访问
chat_service = ChatService(storage_service=storage_service)
app.chat_service = chat_service

# ==================== 5. 请求上下文钩子 ====================

@app.before_request
def before_request():
    """
    在每个请求处理之前执行：
    1. 解析用户 ID
    2. 初始化该用户的 PdfService (因为上传路径依赖用户 ID)
    """
    # 跳过 OPTIONS 请求 (CORS 预检)
    if request.method == 'OPTIONS':
        return

    # 1. 获取用户 ID
    # 优先从 Header 获取，其次从 URL 参数获取，默认为 'default_user'
    user_id = request.headers.get('X-User-Id') or request.args.get('userId') or 'default_user'
    g.user_id = user_id

    # 2. 准备用户目录
    user_path = USERS_DIR / user_id
    upload_folder = user_path / 'uploads'
    cache_folder = user_path / 'cache'
    
    # 确保目录存在
    upload_folder.mkdir(parents=True, exist_ok=True)
    cache_folder.mkdir(parents=True, exist_ok=True)

    # 3. 初始化 PdfService 并挂载到 g
    # 路由中通过 g.pdf_service 访问
    g.pdf_service = PdfService(
        upload_folder=str(upload_folder),
        cache_folder=str(cache_folder)
    )

# ==================== 6. 注册蓝图 ====================

app.register_blueprint(upload_bp)      # URL 前缀: /api/pdf
app.register_blueprint(chatbox_bp)     # URL 前缀: /api/chatbox
app.register_blueprint(highlight_bp)   # URL 前缀: /api/highlight
app.register_blueprint(translate_bp)   # URL 前缀: /api/translate

# ==================== 7. 健康检查接口 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """用于前端检测后端是否存活"""
    return jsonify({
        'status': 'ok',
        'user_id': g.user_id,
        'services': {
            'storage': True,
            'rag': hasattr(app, 'rag_service'),
            'translate': hasattr(app, 'translate_service'),
            'agent': hasattr(app, 'agent_service'),
            'chat': hasattr(app, 'chat_service') # [新增] 检查 ChatService
        }
    })

# ==================== 8. 启动入口 ====================

if __name__ == '__main__':
    # 开发模式启动
    print(f" Server running at http://localhost:5000")
    print(f" Storage Root: {STORAGE_ROOT}")
    app.run(debug=True, host='0.0.0.0', port=5000)