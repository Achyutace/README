import fitz  # PyMuPDF
import base64

def get_page_count(filepath: str) -> int:
    """获取PDF页数"""
    doc = fitz.open(filepath)
    try:
        return len(doc)
    finally:
        doc.close()

def get_pdf_info(pdf_id: str, filepath: str) -> dict:
    """获取PDF基本信息"""
    doc = fitz.open(filepath)
    try:
        info = {
            'id': pdf_id,
            'pageCount': len(doc),
            'metadata': doc.metadata
        }
        return info
    finally:
        doc.close()

def get_page_dimensions(filepath: str, page_number: int) -> dict:
    """获取特定页面的尺寸，用于坐标转换"""
    doc = fitz.open(filepath)
    try:
        if page_number < 1 or page_number > len(doc):
            raise ValueError(f"Invalid page number: {page_number}")
        
        page = doc[page_number - 1]
        rect = page.rect
        return {
            "width": rect.width,
            "height": rect.height
        }
    finally:
        doc.close()

def _extract_page_blocks(page, page_number: int) -> list:
    """Extract text blocks with bounding boxes from a page."""
    blocks = []
    dict_blocks = page.get_text("dict")["blocks"]

    for block in dict_blocks:
        if block.get("type") == 0:  # Text block
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
                text += "\n"

            text = text.strip()
            if text:
                blocks.append({
                    'text': text,
                    'pageNumber': page_number,
                    'bbox': list(block['bbox'])  # [x0, y0, x1, y1]
                })

    return blocks

def extract_text(filepath: str, page_number: int = None) -> dict:
    """Extract text from PDF, optionally from specific page."""
    doc = fitz.open(filepath)
    blocks = []
    full_text = []

    try:
        if page_number is not None:
            # Extract from specific page (1-indexed)
            if page_number < 1 or page_number > len(doc):
                raise ValueError(f"Invalid page number: {page_number}")

            page = doc[page_number - 1]
            page_blocks = _extract_page_blocks(page, page_number)
            blocks.extend(page_blocks)
            full_text.append(page.get_text())
        else:
            # Extract from all pages
            for i, page in enumerate(doc):
                page_blocks = _extract_page_blocks(page, i + 1)
                blocks.extend(page_blocks)
                full_text.append(page.get_text())
    finally:
        doc.close()

    return {
        'text': '\n\n'.join(full_text),
        'blocks': blocks
    }

def parse_paragraphs(filepath: str, pdf_id: str) -> list[dict]:
    """
    解析PDF段落结构：识别PDF段落
    返回：包含段落ID、文本内容、页面信息和坐标范围的列表。
    """
    doc = fitz.open(filepath)
    paragraphs = []
    
    try:
        for page_num, page in enumerate(doc):
            # 获取页面尺寸，用于简单的页眉页脚过滤判断
            page_height = page.rect.height
            header_threshold = 50
            footer_threshold = page_height - 50

            # 尝试按照阅读顺序排序文本块
            blocks = page.get_text("blocks", sort=True)
            
            for block in blocks:
                # block 结构: (x0, y0, x1, y1, text, block_no, block_type)
                x0, y0, x1, y1, text, block_no, block_type = block
                
                # 只处理文本。
                if block_type != 0:
                    continue

                # 如果文本块完全位于顶部或底部区域，视为噪音
                if y1 < header_threshold or y0 > footer_threshold:
                    continue
                
                # 文本清洗
                clean_text = text.replace('-\n', '').replace('\n', ' ').strip()
                
                # 忽略过短的非实质性文本碎片
                if len(clean_text.split()) < 10:
                    continue

                # 生成确定性的段落ID，方便前端定位
                # 格式: pdf_chk_{pdf_id前8位}_{页码}_{块号}
                para_id = f"pdf_chk_{pdf_id[:8]}_{page_num + 1}_{block_no}"

                paragraphs.append({
                    "id": para_id,
                    "page": page_num + 1,
                    "bbox": {
                        "x0": x0,
                        "y0": y0,
                        "x1": x1,
                        "y1": y1,
                        "width": x1 - x0,
                        "height": y1 - y0
                    },
                    "content": clean_text,
                    "wordCount": len(clean_text.split())
                })
    finally:
        doc.close()
    
    return paragraphs

def get_images_list(filepath: str, pdf_id: str) -> list[dict]:
    """
    获取PDF所有图片的元数据列表（ID、页码、坐标），不包含Base64内容。
    """
    doc = fitz.open(filepath)
    images_meta = []
    
    try:
        for page_num, page in enumerate(doc):
            # get_image_info(xrefs=True) 返回页面图片信息
            page_images = page.get_image_info(xrefs=True)
            
            for img in page_images:
                xref = img['xref']
                bbox = img['bbox']
                
                # 构造唯一图片ID，方便直接提取
                # 格式: {pdf_id}__xref__{xref} (使用复杂的连接符避免混淆)
                image_id = f"{pdf_id}__xref__{xref}"
                
                images_meta.append({
                    "id": image_id,
                    "page": page_num + 1,
                    "bbox": {
                        "x0": bbox[0],
                        "y0": bbox[1],
                        "x1": bbox[2],
                        "y1": bbox[3],
                        "width": bbox[2] - bbox[0],
                        "height": bbox[3] - bbox[1]
                    }
                })
    finally:
        doc.close()
    return images_meta

def get_image_data(filepath: str, xref: int) -> dict:
    """
    根据图片xref获取Base64编码数据。
    """
    doc = fitz.open(filepath)
    try:
        # 使用 xref 直接提取图片
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]
        
        # 转为 Base64
        base64_str = base64.b64encode(image_bytes).decode('utf-8')
        mime_type = f"image/{image_ext}"
        
        return {
            "mimeType": mime_type,
            "base64": f"data:{mime_type};base64,{base64_str}"
        }
    finally:
        doc.close()
