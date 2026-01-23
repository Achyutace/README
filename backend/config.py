"""
配置管理模块

从 config.yaml 加载配置，提供全局配置访问
"""

import os
import yaml
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class OpenAIConfig:
    api_key: str = ""
    api_base: str = ""
    model: str = "qwen-plus"


@dataclass
class TranslateConfig:
    api_key: str = ""
    api_base: str = ""


@dataclass
class TavilyConfig:
    api_key: str = ""


@dataclass
class Config:
    openai: OpenAIConfig
    translate: TranslateConfig
    tavily: TavilyConfig

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai.api_key)

    @property
    def has_translate_key(self) -> bool:
        return bool(self.translate.api_key)

    @property
    def has_tavily_key(self) -> bool:
        return bool(self.tavily.api_key)


def load_config(config_path: Optional[str] = None) -> Config:
    """
    从 config.yaml 加载配置

    Args:
        config_path: 配置文件路径，默认为项目根目录的 config.yaml

    Returns:
        Config 实例
    """
    if config_path is None:
        # 默认查找项目根目录的 config.yaml
        # backend/config.py -> backend -> project_root
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.yaml"
    else:
        config_path = Path(config_path)

    # 默认配置
    openai_config = OpenAIConfig()
    translate_config = TranslateConfig()
    tavily_config = TavilyConfig()

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # 解析 OpenAI 配置
            if 'openai' in data:
                openai_data = data['openai']
                openai_config = OpenAIConfig(
                    api_key=openai_data.get('api_key', ''),
                    api_base=openai_data.get('api_base', ''),
                    model=openai_data.get('model', 'qwen-plus')
                )

            # 解析翻译配置
            if 'translate' in data:
                translate_data = data['translate']
                translate_config = TranslateConfig(
                    api_key=translate_data.get('api_key', ''),
                    api_base=translate_data.get('api_base', '')
                )

            # 解析 Tavily 配置
            if 'tavily' in data:
                tavily_data = data['tavily']
                tavily_config = TavilyConfig(
                    api_key=tavily_data.get('api_key', '')
                )

        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
    else:
        print(f"Warning: Config file not found at {config_path}")

    return Config(
        openai=openai_config,
        translate=translate_config,
        tavily=tavily_config
    )


# 全局配置实例（延迟加载）
_settings: Optional[Config] = None


def get_settings() -> Config:
    """获取全局配置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = load_config()
    return _settings


# 便捷访问
settings = get_settings()
