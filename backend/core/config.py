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
    enable_chroma: bool = True
    enable_qdrant: bool = False
    
    chroma_path: str = "./storage/chroma_db"
    
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_prefer_grpc: bool = True

class AppConfig:
    def __init__(self, raw: Dict[str, Any]):
        self.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/paper_agent_db")
        
        # OpenAI
        oa_conf = raw.get("openai", {})
        self.openai = OpenAIConfig(**oa_conf) if oa_conf else None
        
        # Vector Store
        vs_conf = raw.get("vector_store", {})
        self.vector_store = VectorStoreConfig(
            enable_chroma=vs_conf.get("enable_chroma", True),
            enable_qdrant=vs_conf.get("enable_qdrant", False),
            chroma_path=vs_conf.get("chroma", {}).get("path", "./storage/chroma_db"),
            qdrant_url=vs_conf.get("qdrant", {}).get("url", "http://localhost:6333"),
            qdrant_api_key=vs_conf.get("qdrant", {}).get("api_key"),
            qdrant_prefer_grpc=vs_conf.get("qdrant", {}).get("prefer_grpc", True),
        )

# Global Instance
settings = AppConfig(_raw_config)
