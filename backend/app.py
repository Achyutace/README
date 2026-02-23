import os
from datetime import timedelta
from pathlib import Path
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_swagger_ui import get_swaggerui_blueprint

from core.config import settings
from core.exceptions import APIError
from core.logging import setup_logging, get_logger
from core.security import try_get_current_user_id

# ==================== 0. 全局日志配置 ====================
setup_logging()
logger = get_logger(__name__)

# ==================== 1. 导入服务类 ====================
from services.paper_service import PdfService
from services.rag_service import RAGService
from services.translate_service import TranslateService
from agent import AcademicAgentService
from services.chat_service import ChatService
from services.library_service import LibraryService
from services.note_service import NoteService

# ==================== 2. 导入路由蓝图 ====================
from route.upload import upload_bp
from route.chatbox import chatbox_bp
from route.highlight import highlight_bp
from route.translate import translate_bp
from route.notes import notes_bp
from route.auth import auth_bp
from route.link import link_bp
from route.roadmap import roadmap_bp

# ==================== 2.1 Celery ====================
from celery_app import celery  # noqa: F401  (确保 Worker 能发现任务)

# 初始化 Flask 应用
app = Flask(__name__)
# 允许跨域，支持前端从不同端口访问
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ==================== 2.5 JWT 配置 ====================
app.config['JWT_SECRET_KEY'] = settings.jwt.secret
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=settings.jwt.access_expire_minutes)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=settings.jwt.refresh_expire_days)
jwt_manager = JWTManager(app)

# ==================== 2.6 Flask-SQLAlchemy ====================
from core.database import db, init_db
init_db(app)

# ==================== 3. 基础配置与路径 ====================
# 获取项目根目录（README 目录）
BASE_DIR = Path(__file__).resolve().parent.parent  
STORAGE_ROOT = BASE_DIR / 'storage'  # README/storage
USERS_DIR = STORAGE_ROOT / 'users'

# 初始化磁盘目录结构
def init_storage_directories():
    """初始化存储目录结构"""
    directories = [
        STORAGE_ROOT,
        STORAGE_ROOT / 'images',      # 图片存储目录
        STORAGE_ROOT / 'uploads',     # PDF上传目录
        USERS_DIR,                     # 用户数据目录
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    
    print(f" Storage directories initialized at: {STORAGE_ROOT}")

# 执行目录初始化
init_storage_directories()

# 将配置存入 app.config 以便在其他地方调用
app.config['STORAGE_ROOT'] = str(STORAGE_ROOT)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 限制上传大小为 100MB

# ==================== 4. 初始化全局服务 (单例) ====================

# (1) RAG 服务：负责向量检索
rag_service = RAGService()
app.rag_service = rag_service

# (2) 翻译服务：负责调用 LLM 进行翻译
translate_service = TranslateService(
    temperature=0.3
)
app.translate_service = translate_service

# (3) Agent 服务：负责聊天和智能问答
agent_service = AcademicAgentService(
    rag_service=rag_service,
)
app.agent_service = agent_service

# (4) Chat 服务：负责会话管理
#     ChatService 需要 SQLRepository, 在 before_request 中按请求创建
#     这里先挂载一个工厂, 实际实例在钩子中赋值
app.chat_service = None   # 占位, 由 before_request 初始化

# (5) Library 服务：文献管理 (自管理 DB Session)
library_service = LibraryService()
app.library_service = library_service

# (6) Note 服务：笔记管理
#     NoteService 需要 SQLRepository, 与 ChatService 同理
app.note_service = None   # 占位, 由 before_request 初始化

# ==================== 5. 请求上下文钩子 ====================

@app.before_request
def before_request():
    """
    每个请求前：
    1. 若 Authorization 头存在且为 Bearer Token，尝试解析 user_id
    2. 初始化该用户的 PdfService、per-request DB 服务
    3. 公开接口不携带 JWT 时不设置 g.user_id，由各路由自行判断
    4. 受保护接口由 @jwt_required() 装饰器确保 g.user_id 存在
    """
    from repository.sql_repo import SQLRepository

    if request.method == 'OPTIONS':
        return

    # ---------- 1. 从 JWT 提取用户身份 ----------
    user_uuid = try_get_current_user_id()

    # 挂载到 g（如果解析成功）
    if user_uuid:
        g.user_id = user_uuid
        g.user_id_str = str(user_uuid)

        # 2. 准备用户目录
        user_path = USERS_DIR / g.user_id_str
        upload_folder = user_path / 'uploads'
        upload_folder.mkdir(parents=True, exist_ok=True)

        # 3. 初始化 PdfService
        g.pdf_service = PdfService(upload_folder=str(upload_folder))

        # 4. 初始化 per-request 服务 (Flask-SQLAlchemy 自动管理 session 生命周期)
        repo = SQLRepository(db.session)
        app.chat_service = ChatService(db_repo=repo)
        app.note_service = NoteService(db_repo=repo)
    # 未认证请求 — 不初始化用户相关服务
    # 公开接口不需要这些，受保护接口会被 @jwt_required() 拦截

# ==================== 5.5 Swagger UI ====================
# 只有在开发模式下才注册 Swagger
if settings.env == "development" or settings.debug:
    SWAGGER_URL = '/api/docs'
    API_URL = '/api/openapi.yaml'
    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={'app_name': "Paper Agent API"}
    )
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    @app.route('/api/openapi.yaml')
    def send_openapi():
        openapi_dir = BASE_DIR / "docs" / "openapi"
        return send_from_directory(str(openapi_dir), 'openapi.yaml')

# ==================== 5.5 全局错误处理 ====================

@app.errorhandler(APIError)
def handle_api_error(error):
    """处理所有自定义 API 异常 → 统一 JSON 格式"""
    return jsonify(error.to_dict()), error.status_code

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """未预期的异常 → 500 + 日志"""
    logger.error(f"Unexpected error: {error}", exc_info=True)
    return jsonify({"code": "SERVER_ERROR", "error": "Internal server error"}), 500

# ==================== 6. 注册蓝图 ====================

app.register_blueprint(upload_bp)      # URL 前缀: /api/pdf
app.register_blueprint(chatbox_bp)     # URL 前缀: /api/chatbox
app.register_blueprint(highlight_bp)   # URL 前缀: /api/highlight
app.register_blueprint(translate_bp)   # URL 前缀: /api/translate
app.register_blueprint(notes_bp)       # URL 前缀: /api/notes
app.register_blueprint(auth_bp)        # URL 前缀: /api/auth
app.register_blueprint(roadmap_bp)     # URL 前缀: /api/roadmap
app.register_blueprint(link_bp)        # URL 前缀: /api/link

# ==================== 7. 健康检查接口 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """用于前端检测后端是否存活（公开接口，不需要认证）"""
    return jsonify({
        'status': 'ok',
        'services': {
            'celery': True,
            'rag': hasattr(app, 'rag_service'),
            'translate': hasattr(app, 'translate_service'),
            'agent': hasattr(app, 'agent_service'),
            'chat': hasattr(app, 'chat_service')
        }
    })

# ==================== 8. 启动入口 ====================

if __name__ == '__main__':
    # 获取配置中的主机和端口
    host = settings.app.host
    port = settings.app.port
    print(f" Server running at http://{host}:{port}")
    print(f" Storage Root: {STORAGE_ROOT}")
    app.run(debug=settings.debug, host=host, port=port)