import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, HttpUrl

# Load config.yaml
CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"

def load_yaml_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_raw_config = load_yaml_config(CONFIG_PATH)

class OpenAIConfig(BaseModel):
    api_key: str
    api_base: str
    model: str = "gpt-4o"

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

class TranslateConfig(BaseModel):
    api_key: Optional[str] = None
    api_base: Optional[str] = None

class JWTConfig(BaseModel):
    secret: str = "change-me-in-config-yaml"
    access_expire_minutes: int = 30
    refresh_expire_days: int = 7

class AppConfig:
    def __init__(self, raw: Dict[str, Any]):
        # Database
        db_conf = raw.get("database", {})
        self.database = DatabaseConfig(
            url=db_conf.get("url", "postgresql://user:password@localhost:5432/paper_agent_db")
        )
        self.DATABASE_URL = self.database.url

        # Proxy
        proxy_conf = raw.get("proxy", {})
        self.proxy = ProxyConfig(
            http=proxy_conf.get("http"),
            https=proxy_conf.get("https")
        )

        # Tavily
        tavily_conf = raw.get("tavily", {})
        self.tavily = TavilyConfig(
            api_key=tavily_conf.get("api_key")
        )

        # Scientific
        scientific_conf = raw.get("scientific", {})
        self.scientific = ScientificConfig(
            semantic_scholar_api_key=scientific_conf.get("semantic_scholar_api_key")
        )

        # Translate
        trans_conf = raw.get("translate", {})
        self.translate = TranslateConfig(
            api_key=trans_conf.get("api_key"),
            api_base=trans_conf.get("api_base")
        )

        # OpenAI
        oa_conf = raw.get("openai", {})
        self.openai = OpenAIConfig(**oa_conf) if oa_conf else None
        
        # Vector Store
        vs_conf = raw.get("vector_store", {})
        self.vector_store = VectorStoreConfig(
            enable_qdrant=vs_conf.get("enable_qdrant", True),
            qdrant_url=vs_conf.get("qdrant", {}).get("url", "http://localhost:6333"),
            qdrant_api_key=vs_conf.get("qdrant", {}).get("api_key"),
            qdrant_prefer_grpc=vs_conf.get("qdrant", {}).get("prefer_grpc", True),
        )

        # COS
        cos_conf = raw.get("cos", {})
        self.cos = COSConfig(
            enabled=cos_conf.get("enabled", False),
            secret_id=cos_conf.get("secret_id", ""),
            secret_key=cos_conf.get("secret_key", ""),
            region=cos_conf.get("region", ""),
            bucket=cos_conf.get("bucket", ""),
            scheme=cos_conf.get("scheme", "https"),
        )

        # Celery
        celery_conf = raw.get("celery", {})
        self.celery = CeleryConfig(
            broker_url=celery_conf.get("broker_url", "redis://localhost:6379/0"),
            result_backend=celery_conf.get("result_backend", "redis://localhost:6379/1"),
        )

        # JWT
        jwt_conf = raw.get("jwt", {})
        self.jwt = JWTConfig(
            secret=jwt_conf.get("secret", "change-me-in-config-yaml"),
            access_expire_minutes=jwt_conf.get("access_expire_minutes", 30),
            refresh_expire_days=jwt_conf.get("refresh_expire_days", 7),
        )
        # 便捷属性
        self.jwt_secret = self.jwt.secret

    @property
    def has_openai_key(self) -> bool:
        return self.openai is not None and bool(self.openai.api_key)

    @property
    def has_translate_key(self) -> bool:
        return self.translate is not None and bool(self.translate.api_key)

# Global Instance
settings = AppConfig(_raw_config)
