import re
from typing import List, Dict, Any

def is_section_header(text: str) -> bool:
    """检测是否为章节标题"""
    headers = [
        'abstract', 'introduction', 'related work', 'background',
        'method', 'methodology', 'approach', 'experiment', 'results',
        'discussion', 'conclusion', 'references', 'acknowledgment'
    ]
    text_lower = text.lower().strip()
    for header in headers:
        if re.match(rf'^(\d+\.?\s*)?{header}s?$', text_lower):
            return True
    return False

def create_chunks_from_paragraphs(paragraphs: List[Any], chunk_size: int = 500) -> List[Dict]:
    """
    将数据库段落对象合并为文本块
    
    Args:
        paragraphs: PdfParagraph 对象列表 (需包含 original_text, page_number)
        chunk_size: 目标块大小
    """
    chunks = []
    current_chunk_text = ""
    current_section = "content"
    # 记录当前正在构建的chunk的起始页码
    chunk_start_page = paragraphs[0].page_number if paragraphs else 1
    
    for p in paragraphs:
        text = p.original_text.strip()
        if not text:
            continue
        
        page_num = p.page_number
        
        # 检测是否为新的章节标题
        if is_section_header(text):
            # 遇到标题，先保存之前的累积内容（如果有）
            if current_chunk_text:
                chunks.append({
                    'content': current_chunk_text.strip(),
                    'page': chunk_start_page, 
                    'section': current_section
                })
                current_chunk_text = ""
            
            # 更新当前章节名 (移除序号，保留核心标题)
            # 且标题本身不再作为chunk内容重复添加，因为它已作为元数据存在
            current_section = re.sub(r'^[\d\.\s]+', '', text).strip().lower()
            chunk_start_page = page_num
            continue
        
        # 如果当前块已经够大，则保存当前块并开始新块
        if len(current_chunk_text) >= chunk_size:
            chunks.append({
                'content': current_chunk_text.strip(),
                'page': chunk_start_page, 
                'section': current_section
            })
            current_chunk_text = ""
            chunk_start_page = page_num

        # 追加当前段落文本
        if current_chunk_text:
            current_chunk_text += "\n\n" + text
        else:
            current_chunk_text = text
    
    # 处理剩余内容
    if current_chunk_text.strip():
        chunks.append({
            'content': current_chunk_text.strip(),
            'page': chunk_start_page,
            'section': current_section
        })
        
    return chunks
