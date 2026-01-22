"""
翻译服务 - 提供段落级别的翻译功能

功能：
1. 文本翻译（英文 -> 中文）
2. 段落翻译并存储到数据库
3. 翻译缓存优化
"""

import os
from typing import Dict, List, Optional
from pathlib import Path

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

class TranslateService:
    """
    翻译服务

    - translate: 翻译单段文本
    - translate_paragraph: 翻译段落并存储到数据库
    - translate_page: 翻译整页内容
    - batch_translate: 批量翻译
    """

    def __init__(self,
                 db=None,
                 model: str = "qwen-plus",
                 temperature: float = 0.3,
                 base_url: str = None):
        """
        Args:
            db: 数据库实例（用于存储翻译结果）
            model: 使用的模型
            temperature: 温度参数（翻译任务建议较低）
            base_url: OpenAI API 基础 URL（可选，用于代理或其他兼容服务）
        """
        self.db = db
        self.model = model
        self.temperature = temperature

        # 初始化 OpenAI 客户端
        api_key = os.getenv('TRANSLATE_API_KEY')
        if api_key and HAS_OPENAI:
            client_kwargs = {"api_key": api_key}
            
            # 支持 base_url 参数或环境变量
            if base_url or os.getenv('TRANSLATE_API_BASE'):
                client_kwargs["base_url"] = base_url or os.getenv('TRANSLATE_API_BASE')
            
            self.client = OpenAI(**client_kwargs)
            self.has_client = True
        else:
            self.client = None
            self.has_client = False
            print("Warning: OpenAI API key not found. Translate service will use demo mode.")

    def translate(self, text: str, source_lang: str = "en", target_lang: str = "zh") -> Dict:
        """
        翻译单段文本

        Args:
            text: 待翻译文本
            source_lang: 源语言（默认英文）
            target_lang: 目标语言（默认中文）

        Returns:
            {
                'originalText': str,
                'translatedText': str,
                'sourceLanguage': str,
                'targetLanguage': str,
                'sentences': [
                    {'index': int, 'original': str, 'translated': str},
                    ...
                ]
            }
        """
        if not text or not text.strip():
            return {
                'originalText': text,
                'translatedText': '',
                'sourceLanguage': source_lang,
                'targetLanguage': target_lang,
                'sentences': []
            }

        if not self.has_client:
            return self._demo_translate(text, source_lang, target_lang)

        try:
            # 构建翻译 prompt
            system_prompt = f"""你是一个专业的学术翻译专家。请将以下{self._get_lang_name(source_lang)}文本翻译成{self._get_lang_name(target_lang)}。

翻译要求：
1. 保持学术术语的准确性
2. 保持句子结构的流畅性
3. 专业术语可以保留原文并在括号中注释
4. 只输出翻译结果，不要有其他内容"""

            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ]
            )

            translated_text = response.choices[0].message.content.strip()

            # 分句对齐（简单实现）
            sentences = self._align_sentences(text, translated_text)

            return {
                'originalText': text,
                'translatedText': translated_text,
                'sourceLanguage': source_lang,
                'targetLanguage': target_lang,
                'sentences': sentences
            }

        except Exception as e:
            print(f"Translation error: {e}")
            return self._demo_translate(text, source_lang, target_lang)

    def translate_paragraph(self,
                           file_hash: str,
                           page_number: int,
                           paragraph_index: int,
                           original_text: str,
                           force: bool = False) -> Dict:
        """
        翻译段落并存储到数据库

        Args:
            file_hash: 文件哈希
            page_number: 页码
            paragraph_index: 段落索引
            original_text: 原文
            force: 是否强制重新翻译（忽略缓存）

        Returns:
            {
                'success': bool,
                'translation': str,
                'cached': bool
            }
        """
        # 检查缓存
        if not force and self.db:
            cached = self.db.get_paragraph_translation(file_hash, page_number, paragraph_index)
            if cached:
                return {
                    'success': True,
                    'translation': cached,
                    'cached': True
                }

        # 执行翻译
        result = self.translate(original_text)

        # 存储到数据库
        if self.db and result.get('translatedText'):
            self.db.update_paragraph_translation(
                file_hash, page_number, paragraph_index,
                result['translatedText']
            )

        return {
            'success': True,
            'translation': result.get('translatedText', ''),
            'cached': False
        }

    def translate_page(self,
                      file_hash: str,
                      page_number: int,
                      paragraphs: List[Dict],
                      force: bool = False) -> Dict:
        """
        翻译整页内容

        Args:
            file_hash: 文件哈希
            page_number: 页码
            paragraphs: 段落列表 [{'index': int, 'text': str}, ...]
            force: 是否强制重新翻译

        Returns:
            {
                'success': bool,
                'page_number': int,
                'translations': [
                    {'index': int, 'original': str, 'translation': str, 'cached': bool},
                    ...
                ],
                'total': int,
                'translated': int,
                'cached': int
            }
        """
        translations = []
        cached_count = 0

        for para in paragraphs:
            idx = para.get('index', 0)
            text = para.get('text', '')

            result = self.translate_paragraph(
                file_hash, page_number, idx, text, force
            )

            translations.append({
                'index': idx,
                'original': text,
                'translation': result.get('translation', ''),
                'cached': result.get('cached', False)
            })

            if result.get('cached'):
                cached_count += 1

        return {
            'success': True,
            'page_number': page_number,
            'translations': translations,
            'total': len(paragraphs),
            'translated': len(translations),
            'cached': cached_count
        }

    def batch_translate(self, texts: List[str]) -> List[Dict]:
        """
        批量翻译

        Args:
            texts: 文本列表

        Returns:
            翻译结果列表
        """
        results = []
        for text in texts:
            result = self.translate(text)
            results.append(result)
        return results

    def _demo_translate(self, text: str, source_lang: str, target_lang: str) -> Dict:
        """Demo 模式的翻译"""
        # 简单的模拟翻译
        demo_translation = f"[翻译] {text[:100]}..." if len(text) > 100 else f"[翻译] {text}"

        return {
            'originalText': text,
            'translatedText': demo_translation,
            'sourceLanguage': source_lang,
            'targetLanguage': target_lang,
            'sentences': [
                {'index': 1, 'original': text, 'translated': demo_translation}
            ]
        }

    def _get_lang_name(self, lang_code: str) -> str:
        """获取语言名称"""
        lang_map = {
            'en': '英文',
            'zh': '中文',
            'ja': '日文',
            'ko': '韩文',
            'fr': '法文',
            'de': '德文',
            'es': '西班牙文'
        }
        return lang_map.get(lang_code, lang_code)

    def _align_sentences(self, original: str, translated: str) -> List[Dict]:
        """
        简单的分句对齐

        Args:
            original: 原文
            translated: 译文

        Returns:
            对齐的句子列表
        """
        import re

        # 简单的分句
        original_sentences = re.split(r'(?<=[.!?])\s+', original)
        translated_sentences = re.split(r'(?<=[。！？])\s*', translated)

        sentences = []
        for i, (orig, trans) in enumerate(zip(original_sentences, translated_sentences), 1):
            sentences.append({
                'index': i,
                'original': orig.strip(),
                'translated': trans.strip()
            })

        # 处理长度不匹配的情况
        if len(original_sentences) > len(translated_sentences):
            for i in range(len(translated_sentences), len(original_sentences)):
                sentences.append({
                    'index': i + 1,
                    'original': original_sentences[i].strip(),
                    'translated': ''
                })

        return sentences