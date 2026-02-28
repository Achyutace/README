import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

# Load config.yaml
# Use CONFIG_PATH from environment if available, otherwise fallback to local dev path
_default_path = Path(__file__).parent.parent.parent / "config.yaml"
CONFIG_PATH = Path(os.getenv("CONFIG_PATH", _default_path))

def load_yaml_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path} (Resolved from CONFIG_PATH env var or default)")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_raw_config = load_yaml_config(CONFIG_PATH)


# ==================== 配置模型 ====================

class OpenAIConfig(BaseModel):
    api_key: str
    api_base: str

class AppInfoConfig(BaseModel):
    """应用总体配置"""
    env: str = "development"
    host: str = "0.0.0.0"
    port: int = 5000

class SceneModelConfig(BaseModel):
    """单个场景的模型配置（支持可选的独立 API 凭证）"""
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None

class ModelsConfig(BaseModel):
    """按场景分配模型"""
    chat: SceneModelConfig = SceneModelConfig(model="qwen-plus")
    translate: SceneModelConfig = SceneModelConfig(model="qwen-plus")
    vision: SceneModelConfig = SceneModelConfig(model="gpt-4o-mini")
    embedding: SceneModelConfig = SceneModelConfig(model="text-embedding-3-small")
    roadmap: SceneModelConfig = SceneModelConfig(model="qwen-plus")


class VectorStoreConfig(BaseModel):
    enable_qdrant: bool = True
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_prefer_grpc: bool = True

class COSConfig(BaseModel):
    enabled: bool = False
    secret_id: str
    secret_key: str
    region: str
    bucket: str
    scheme: str = "https"

class CeleryConfig(BaseModel):
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"


class DatabaseConfig(BaseModel):
    url: str


class ProxyConfig(BaseModel):
    http: Optional[str] = None
    https: Optional[str] = None


class TavilyConfig(BaseModel):
    api_key: Optional[str] = None


class ScientificConfig(BaseModel):
    semantic_scholar_api_key: Optional[str] = None
    semantic_scholar_api_url: str = "https://api.semanticscholar.org/graph/v1"


class JWTConfig(BaseModel):
    secret: str = "change-me-in-config-yaml"
    access_expire_minutes: int = 30
    refresh_expire_days: int = 7


# ==================== 解析辅助 ====================

def _parse_scene_model(value) -> SceneModelConfig:
    """解析场景模型配置，支持简写和详写两种格式"""
    if isinstance(value, str):
        # 简写: "qwen-plus"
        return SceneModelConfig(model=value)
    elif isinstance(value, dict):
        # 详写: { model: "xxx", api_key: "...", api_base: "..." }
        return SceneModelConfig(
            model=value.get("model", "qwen-plus"),
            api_key=value.get("api_key"),
            api_base=value.get("api_base"),
        )
    return SceneModelConfig(model="qwen-plus")


def _parse_models_config(raw: Dict[str, Any]) -> ModelsConfig:
    """从 raw config 解析 models 块"""
    models_raw = raw.get("models", {})
    if not models_raw:
        return ModelsConfig()

    return ModelsConfig(
        chat=_parse_scene_model(models_raw.get("chat", "qwen-plus")),
        translate=_parse_scene_model(models_raw.get("translate", "qwen-plus")),
        vision=_parse_scene_model(models_raw.get("vision", "gpt-4o-mini")),
        embedding=_parse_scene_model(models_raw.get("embedding", "text-embedding-3-small")),
        roadmap=_parse_scene_model(models_raw.get("roadmap", "qwen-plus")),
    )


# ==================== 主配置类 ====================

class AppConfig:
    def __init__(self, raw: Dict[str, Any]):
        # 1. 应用基本信息
        app_conf = raw.get("app", {})
        self.env = app_conf.get("env", "development")
        self.app = AppInfoConfig(
            env=self.env,
            host=app_conf.get("host", "0.0.0.0"),
            port=app_conf.get("port", 5000),
        )

        def get_sec(key: str) -> Dict[str, Any]:
            """辅助获取配置节，支持环境特定的覆盖"""
            base = raw.get(key, {})
            # 尝试从当前环境节中获取覆盖配置 (例如: production.database)
            overrides = raw.get(self.env, {}).get(key, {})
            if isinstance(base, dict) and isinstance(overrides, dict):
                return {**base, **overrides}
            return overrides if overrides is not None else (base if base is not None else {})

        # 2. 从合并后的配置中解析各部分
        
        # OpenAI (全局默认凭证)
        oa_conf = get_sec("openai")
        self.openai = OpenAIConfig(**oa_conf) if oa_conf else OpenAIConfig(api_key="", api_base="")

        # Models (按场景分配)
        models_raw = get_sec("models")
        self.models = _parse_models_config({"models": models_raw})

        # Database
        db_conf = get_sec("database")
        self.database = DatabaseConfig(
            url=db_conf.get("url", "postgresql://user:password@localhost:5432/paper_agent_db")
        )
        self.DATABASE_URL = self.database.url

        # Proxy
        proxy_conf = get_sec("proxy")
        self.proxy = ProxyConfig(
            http=proxy_conf.get("http"),
            https=proxy_conf.get("https")
        )

        # Tavily
        tavily_conf = get_sec("tavily")
        self.tavily = TavilyConfig(
            api_key=tavily_conf.get("api_key")
        )

        # Scientific
        scientific_conf = get_sec("scientific")
        self.scientific = ScientificConfig(
            semantic_scholar_api_key=scientific_conf.get("semantic_scholar_api_key"),
            semantic_scholar_api_url=scientific_conf.get("semantic_scholar_api_url", "https://api.semanticscholar.org/graph/v1")
        )

        # Vector Store
        vs_conf = get_sec("vector_store")
        qdrant_conf = vs_conf.get("qdrant", {})
        self.vector_store = VectorStoreConfig(
            enable_qdrant=vs_conf.get("enable_qdrant", True),
            qdrant_url=qdrant_conf.get("url", "http://localhost:6333"),
            qdrant_api_key=qdrant_conf.get("api_key"),
            qdrant_prefer_grpc=qdrant_conf.get("prefer_grpc", True),
        )

        # COS
        cos_conf = get_sec("cos")
        self.cos = COSConfig(
            enabled=cos_conf.get("enabled", False),
            secret_id=cos_conf.get("secret_id", ""),
            secret_key=cos_conf.get("secret_key", ""),
            region=cos_conf.get("region", ""),
            bucket=cos_conf.get("bucket", ""),
            scheme=cos_conf.get("scheme", "https"),
        )

        # Celery
        celery_conf = get_sec("celery")
        self.celery = CeleryConfig(
            broker_url=celery_conf.get("broker_url", "redis://localhost:6379/0"),
            result_backend=celery_conf.get("result_backend", "redis://localhost:6379/1"),
        )

        # JWT
        jwt_conf = get_sec("jwt")
        self.jwt = JWTConfig(
            secret=jwt_conf.get("secret", "change-me-in-config-yaml"),
            access_expire_minutes=jwt_conf.get("access_expire_minutes", 3000),
            refresh_expire_days=jwt_conf.get("refresh_expire_days", 7),
        )
        self.jwt_secret = self.jwt.secret

    @property
    def has_openai_key(self) -> bool:
        return self.openai is not None and bool(self.openai.api_key)

    @property
    def debug(self) -> bool:
        """根据环境自动推导是否开启调试模式"""
        return self.env == "development"


# Global Instance
settings = AppConfig(_raw_config)
