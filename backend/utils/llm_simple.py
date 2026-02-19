from typing import Optional, Any
import re

def get_lang_name(lang_code: str) -> str:
    """获取语言显示名称"""
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

def construct_translation_prompt(source_lang: str = "en", target_lang: str = "zh") -> str:
    """构建标准翻译的 System Prompt"""
    src_name = get_lang_name(source_lang)
    tgt_name = get_lang_name(target_lang)
    
    return f"""你是一个专业的学术翻译专家。请将以下{src_name}文本翻译成{tgt_name}。

翻译要求：
1. 保持学术术语的准确性
2. 保持句子结构的流畅性
3. 专业术语可以保留原文并在括号中注释
4. 只输出翻译结果，不要有其他内容"""

def construct_context_translation_prompt(text: str, context: str = None) -> tuple[str, str]:
    """
    构建带上下文翻译的 Prompt
    Returns: (system_prompt, user_prompt)
    """
    system_prompt = """你是一个专业的学术翻译专家。请根据提供的文档上下文，准确翻译用户选中的词句。

翻译要求：
1. 理解文档的整体语境和专业领域
2. 准确翻译专业术语，保持学术规范
3. 对于专有名词和缩写，保留原文并在括号中注释
4. 只输出翻译结果，不要有任何额外说明或解释"""

    user_prompt = f"""文档上下文（前几段内容，帮助理解专业术语）：
---
{context[:2000]}  
---

请翻译以下选中的文本：
{text}

翻译结果："""
    
    return system_prompt, user_prompt

def clean_translation_output(text: str) -> str:
    """
    清洗翻译输出，去除可能的 Markdown 标记等多余成分
    """
    if not text:
        return ""
    
    # 去除 Markdown 代码块标记 (```json ... ``` 或 ``` ...)
    # 匹配开头
    text = re.sub(r'^```(?:\w+)?\s*\n', '', text.strip())
    # 匹配结尾
    text = re.sub(r'\n\s*```$', '', text)
    
    # 去除首尾空白
    return text.strip()

def invoke_llm_translation(
    client: Any,
    model: str,
    system_prompt: str,
    user_content: str,
    temperature: float = 0.3
) -> Optional[str]:
    """
    调用 LLM 进行翻译的纯函数。
    
    Args:
        client: 初始化好的 OpenAI 客户端实例
        model: 模型名称
        system_prompt: 系统提示词
        user_content: 用户输入内容
        temperature: 温度参数
        
    Returns:
        translations: 翻译后的文本，失败返回 None
    """
    if not client:
        return None
        
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # 记录错误时，不要 dump 整个 client 对象，防止泄漏其中的 api_key
        print(f"LLM Translation Error: {str(e)}")
        return None

def translate_text(
    client: Any,
    text: str,
    context: str = None,
    model: str = "qwen-plus",
    temperature: float = 0.3,
    source_lang: str = "en",
    target_lang: str = "zh"
) -> str:
    """
    统一的翻译接口，自动处理上下文 prompt 构建和结果清洗
    
    Args:
        client: OpenAI client 实例
        text: 待翻译文本
        context: 上下文 (可选)
        model: 模型名称
        temperature: 温度
        source_lang: 源语言代码
        target_lang: 目标语言代码
        
    Returns:
        翻译后的文本
    """
    if not client:
        print("Translate Error: Client is None")
        return ""
    
    if not text or not text.strip():
        return ""
        
    if context and context.strip():
        # 有上下文时使用上下文 prompt
        system_prompt, user_content = construct_context_translation_prompt(text, context)
    else:
        # 无上下文使用标准翻译 prompt
        system_prompt = construct_translation_prompt(source_lang, target_lang)
        user_content = text
        
    result = invoke_llm_translation(
        client=client,
        model=model,
        system_prompt=system_prompt,
        user_content=user_content,
        temperature=temperature
    )
    
    return clean_translation_output(result) if result else ""
