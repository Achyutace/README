"""
翻译服务
1. 文本翻译
2. 段落翻译并存储到数据库
3. 获取整页翻译缓存
"""

from typing import Dict, List, Optional
from pathlib import Path

from core.config import settings
from core.llm_provider import resolve_llm_profile, create_openai_client
from utils.llm_simple import translate_text
from core.database import db
from repository.sql_repo import SQLRepository
from utils.pdf_engine import make_paragraph_id
from core.logging import get_logger

logger = get_logger(__name__)

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

class TranslateService:
    """
    翻译服务
    """

    def __init__(self,
                 model: str = None,
                 temperature: float = 0.3,
                 base_url: str = None,
                 api_key: str = None):
        """
        Args:
            model: 使用的模型 (可选，默认从 config 读取)
            temperature: 温度参数
            base_url: 请求级 API Base 覆盖
            api_key: 请求级 API Key 覆盖
        """
        # 1. 解析配置 (优先级: 参数 > config.models.translate > config.openai)
        self.profile = resolve_llm_profile(
            scene="translate",
            api_key=api_key,
            api_base=base_url,
            model=model
        )
        
        self.model = self.profile.model
        self.temperature = temperature

        # 2. 初始化客户端
        if self.profile.is_available and HAS_OPENAI:
            self.client = create_openai_client(self.profile)
            self.has_client = True
        else:
            self.client = None
            self.has_client = False
            if not self.profile.is_available:
                logger.warning("Translate API key not found. Translate service will use demo mode.")

    def translate(self, text: str, context: str = None) -> str:
        """
        翻译接口
        
        Args:
            text: 待翻译文本
            context: 上下文 (可选)
            
        Returns:
            translated_text (str): 翻译后的文本
        """
        if not text or not text.strip():
            return ""

        if not self.has_client:
            return self._demo_translate(text)

        try:
            return translate_text(
                client=self.client,
                text=text,
                context=context,
                model=self.model,
                temperature=self.temperature
            )
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return self._demo_translate(text)

    def translate_paragraph(self, file_hash: str, page_number: int, paragraph_index: int, original_text: str, force: bool = False) -> Dict:
        """
        翻译段落并存储到数据库
        
        Args:
            file_hash: 文件哈希
            page_number: 页码
            paragraph_index: 段落索引
            original_text: 原文
            force: 是否强制重译
            
        Returns:
            result (dict): {translation: str, cached: bool}
        """
        repo = SQLRepository(db.session)

        # 1. 检查缓存
        if not force:
            translations = repo.get_paragraph_translations(file_hash, page_number, paragraph_index)
            if translations and translations[0]:
                return {
                    'translation': translations[0],
                    'cached': True
                }

        # 2. 调用翻译
        translated_text = self.translate(original_text)

        # 3. 存储结果
        try:
            repo.update_paragraph_translation(file_hash, page_number, paragraph_index, translated_text)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving paragraph translation: {e}")
            # 注意：此处不一定非要 raise，因为翻译已经生成，返回结果给前端展示，只是数据库没存上
            # 但为了严谨，这里还是记录错误

        return {
            'translation': translated_text,
            'cached': False
        }

    def translate_text(self, text: str, context: str = None) -> Dict:
        """
        翻译选中文本（带上下文处理）
        
        Args:
            text: 待翻译文本
            context: 上下文
            
        Returns:
            result (dict): 包含原文、译文和上下文信息的字典
        """
        translated = self.translate(text, context)
        
        return {
            'originalText': text,
            'translatedText': translated,
            'hasContext': bool(context),
            'contextLength': len(context) if context else 0
        }

    def get_page_translations(self, file_hash: str, page_number: int) -> Dict[str, str]:
        """
        获取某页的所有历史翻译

        Args:
            file_hash: 文件哈希 (即 pdf_id)
            page_number: 页码

        Returns:
            dict: { paragraphId: translationText, ... }
        """
        repo = SQLRepository(db.session)
        paragraphs = repo.get_paragraphs(file_hash, page_number=page_number)

        results = {}
        for p in paragraphs:
            if p.translation_text:
                p_id = make_paragraph_id(file_hash, p.page_number, p.paragraph_index)
                results[p_id] = p.translation_text
        return results

    def _demo_translate(self, text: str) -> str:
        """演示模式翻译 (无 API Key 时的 fallback)"""
        return f"[Demo Translation] {text}"
