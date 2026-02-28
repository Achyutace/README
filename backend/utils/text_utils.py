def build_context_string(paragraphs: list, max_paragraphs: int = 3) -> str | None:
    """
    将原文段落列表拼接为上下文字符串
    """
    if not paragraphs:
        return None
        
    context_parts = [p.get('original_text', '') for p in paragraphs[:max_paragraphs]]
    return '\n\n'.join(context_parts)
