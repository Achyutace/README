from pathlib import Path
from flask import Flask, request, jsonify, g
from flask_cors import CORS

from core.config import settings

# ==================== 1. 导入服务类 ====================
from services.paper_service import PdfService
from services.rag_service import RAGService
from services.translate_service import TranslateService
from services.agent_service import AcademicAgentService
from services.chat_service import ChatService

# ==================== 2. 导入路由蓝图 ====================
from route.upload import upload_bp
from route.chatbox import chatbox_bp
from route.highlight import highlight_bp
from route.translate import translate_bp
from route.notes import notes_bp

# ==================== 2.1 Celery ====================
from celery_app import celery  # noqa: F401  (确保 Worker 能发现任务)

# 初始化 Flask 应用
app = Flask(__name__)
# 允许跨域，支持前端从不同端口访问
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ==================== 3. 基础配置与路径 ====================
# 获取项目根目录（README 目录）
BASE_DIR = Path(__file__).resolve().parent.parent  
STORAGE_ROOT = BASE_DIR / 'storage'  # README/storage
USERS_DIR = STORAGE_ROOT / 'users'
CHROMA_DIR = STORAGE_ROOT / 'chroma_db'

# 初始化磁盘目录结构
def init_storage_directories():
    """初始化存储目录结构"""
    directories = [
        STORAGE_ROOT,
        STORAGE_ROOT / 'images',      # 图片存储目录
        STORAGE_ROOT / 'uploads',     # PDF上传目录
        USERS_DIR,                     # 用户数据目录
        CHROMA_DIR,                    # 向量数据库目录
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
# 路由中通过 current_app.rag_service 访问
rag_service = RAGService(chroma_dir=str(CHROMA_DIR))
app.rag_service = rag_service

# (2) 翻译服务：负责调用 LLM 进行翻译
# 路由中通过 current_app.translate_service 访问
translate_service = TranslateService(
    model=settings.openai.model,
    temperature=0.3
)
app.translate_service = translate_service

# (3) Agent 服务：负责聊天和智能问答
# 依赖 rag_service 进行上下文检索
agent_service = AcademicAgentService(
    rag_service=rag_service,
    openai_api_key=settings.openai.api_key,
    openai_api_base=settings.openai.api_base,
    model=settings.openai.model
)
app.agent_service = agent_service

# (4) Chat 服务：负责会话数据格式化
chat_service = ChatService()
app.chat_service = chat_service

# ==================== 5. 请求上下文钩子 ====================

@app.before_request
def before_request():
    """
    在每个请求处理之前执行：
    1. 解析用户标识 → 确保数据库中有对应 User 记录 → 得到 UUID
    2. 初始化该用户的 PdfService (因为上传路径依赖用户 ID)
    """
    import uuid as _uuid
    from core.database import SessionLocal
    from repository.sql_repo import SQLRepository

    # 跳过 OPTIONS 请求 (CORS 预检)
    if request.method == 'OPTIONS':
        return

    # 1. 获取用户标识
    # 支持两种形式:
    #   a) UUID 字符串 → 直接当 user.id 使用
    #   b) 普通用户名   → 通过 get_or_create_user 获得 UUID
    raw_user_id = (
        request.headers.get('X-User-Id')
        or request.form.get('userId')
        or request.args.get('userId')
        or 'default_user'
    )

    # 尝试解析为 UUID
    try:
        user_uuid = _uuid.UUID(raw_user_id)
        # 是合法 UUID, 用作磁盘目录名时取前 16 位
        user_dir_name = str(user_uuid)
    except ValueError:
        # 不是 UUID → 当作 username, 在数据库中 get_or_create
        user_dir_name = raw_user_id
        user_uuid = None

    # 确保 DB 中有用户记录
    if user_uuid is None:
        db = SessionLocal()
        try:
            repo = SQLRepository(db)
            user_obj = repo.get_or_create_user(raw_user_id)
            user_uuid = user_obj.id
        finally:
            db.close()
    else:
        # UUID 形式: 验证用户存在 (不存在就自动创建)
        db = SessionLocal()
        try:
            repo = SQLRepository(db)
            user_obj = repo.get_user_by_id(user_uuid)
            if not user_obj:
                # UUID 不存在 → 用 raw_user_id 作 username 创建
                user_obj = repo.get_or_create_user(raw_user_id)
                user_uuid = user_obj.id
        finally:
            db.close()

    # 挂载到 g (统一为 UUID 类型)
    g.user_id = user_uuid  # uuid.UUID
    g.user_id_str = str(user_uuid)  # 字符串形式，方便日志/路径

    # 2. 准备用户目录 (用 UUID 字符串作目录名)
    user_path = USERS_DIR / g.user_id_str
    upload_folder = user_path / 'uploads'

    # 确保目录存在
    upload_folder.mkdir(parents=True, exist_ok=True)

    # 3. 初始化 PdfService 并挂载到 g
    g.pdf_service = PdfService(
        upload_folder=str(upload_folder),
    )

# ==================== 6. 注册蓝图 ====================

app.register_blueprint(upload_bp)      # URL 前缀: /api/pdf
app.register_blueprint(chatbox_bp)     # URL 前缀: /api/chatbox
app.register_blueprint(highlight_bp)   # URL 前缀: /api/highlight
app.register_blueprint(translate_bp)   # URL 前缀: /api/translate
app.register_blueprint(notes_bp)       # URL 前缀: /api/notes

# ==================== 7. 健康检查接口 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """用于前端检测后端是否存活"""
    return jsonify({
        'status': 'ok',
        'user_id': g.user_id,
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
    # 开发模式启动
    print(f" Server running at http://localhost:5000")
    print(f" Storage Root: {STORAGE_ROOT}")
    app.run(debug=True, host='0.0.0.0', port=5000)