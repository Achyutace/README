"""
LLM Provider 抽象层

提供统一的 API 配置解析：
- 默认从 config.yaml 读取（开发模式）
- 可由请求数据覆盖（开发模式 + 生产环境）
- 支持 per-service 独立 API 凭证
"""

from dataclasses import dataclass
from typing import Optional

from core.config import settings


@dataclass
class LLMProfile:
    api_key: str
    api_base: str
    model: str

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)


def resolve_llm_profile(
    scene: str = "chat",
    *,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProfile:
    """
    解析 LLM 调用配置。

    优先级：
        1. 函数参数（来自请求数据覆盖）
        2. config.yaml 中 models.<scene> 的 per-service 覆盖
        3. config.yaml 中 openai 全局配置

    Args:
        scene:    场景名称（chat / translate / vision / embedding / roadmap）
        api_key:  请求覆盖
        api_base: 请求覆盖
        model:    请求覆盖
    """
    # 从 models.<scene> 获取场景配置
    scene_config = getattr(settings.models, scene, None)

    # 场景级别的默认值
    scene_model = scene_config.model if scene_config else "qwen-plus"
    scene_api_key = (scene_config.api_key if scene_config else None) or None
    scene_api_base = (scene_config.api_base if scene_config else None) or None

    return LLMProfile(
        api_key=api_key or scene_api_key or settings.openai.api_key,
        api_base=api_base or scene_api_base or settings.openai.api_base,
        model=model or scene_model,
    )


def create_openai_client(profile: LLMProfile):
    """根据 LLMProfile 创建 OpenAI 客户端"""
    from openai import OpenAI
    import httpx

    kwargs = {"api_key": profile.api_key}
    if profile.api_base:
        kwargs["base_url"] = profile.api_base

    # 全局代理配置
    proxy_url = settings.proxy.http or settings.proxy.https
    if proxy_url:
        kwargs["http_client"] = httpx.Client(proxies=proxy_url)

    return OpenAI(**kwargs)


def get_langchain_llm(profile: LLMProfile, temperature: float = 0.7):
    """
    创建 LangChain ChatOpenAI 实例，自动注入全局代理配置
    """
    from langchain_openai import ChatOpenAI
    import httpx

    if not profile.is_available:
        return None

    kwargs = {
        "model": profile.model,
        "temperature": temperature,
        "api_key": profile.api_key,
    }
    
    if profile.api_base:
        kwargs["base_url"] = profile.api_base

    # 注入全局代理
    proxy_url = settings.proxy.http or settings.proxy.https
    if proxy_url:
        kwargs["http_client"] = httpx.Client(proxies=proxy_url)

    return ChatOpenAI(**kwargs)


def get_langchain_embeddings(profile: LLMProfile):
    """
    创建 LangChain OpenAIEmbeddings 实例，自动注入全局代理配置
    """
    from langchain_openai import OpenAIEmbeddings
    import httpx

    if not profile.is_available:
        return None

    kwargs = {
        "model": profile.model,
        "api_key": profile.api_key,
    }

    if profile.api_base:
        kwargs["base_url"] = profile.api_base

    # 注入全局代理
    proxy_url = settings.proxy.http or settings.proxy.https
    if proxy_url:
        kwargs["http_client"] = httpx.Client(proxies=proxy_url)

    return OpenAIEmbeddings(**kwargs)
