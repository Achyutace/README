import fitz  # PyMuPDF
import base64

# =============== ID 生成/解析 =============
def make_paragraph_id(pdf_id: str, page_number: int, index: int) -> str:
    """生成确定的段落ID"""
    return f"pdf_chk_{pdf_id[:8]}_{page_number}_{index}"

def parse_paragraph_id(para_id: str) -> dict:
     """解析段落ID"""
     # "pdf_chk_{pdf_id[:8]}_{page_number}_{index}"
     parts = para_id.split('_')
     if len(parts) >= 5 and parts[0] == 'pdf' and parts[1] == 'chk':
         return {
             'short_pdf_id': parts[2],
             'page_number': int(parts[3]),
             'index': int(parts[4])
         }
     return None

def make_image_id(pdf_id: str, image_index: int) -> str:
    """生成唯一的图片ID """
    return f"pdf_img_{pdf_id}_{image_index}"

def parse_image_id(image_id: str) -> tuple[str, int]:
    """解析图片ID以获取 pdf_id 和 image_index"""
    if not image_id.startswith("pdf_img_"):
        raise ValueError("Invalid image ID format")

    content = image_id[len("pdf_img_"):]
    parts = content.rsplit('_', 1) 
    if len(parts) != 2:
        raise ValueError("Invalid image ID format")
        
    pdf_id, index_str = parts
    return pdf_id, int(index_str)

# =============== PDF解析 =============

def get_pdf_info(pdf_id: str, filepath: str) -> dict:
    """获取PDF基本信息"""
    doc = fitz.open(filepath)
    try:
        # 获取每一页的尺寸
        dimensions = []
        for page in doc:
            rect = page.rect
            dimensions.append({
                "width": rect.width,
                "height": rect.height
            })
            
        info = {
            'id': pdf_id,
            'pageCount': len(doc),
            'metadata': doc.metadata,
            'dimensions': dimensions
        }
        return info
    finally:
        doc.close()

def get_page_count(filepath: str) -> int:
    """获取PDF页数"""
    doc = fitz.open(filepath)
    try:
        return len(doc)
    finally:
        doc.close()



def parse_paragraphs(filepath: str, pdf_id: str, page_numbers: list[int] = None) -> list[dict]:
    """
    解析PDF段落结构
    返回：包含段落ID、文本内容、页面信息和坐标范围的列表。
    Args:
        filepath: PDF文件路径
        pdf_id: PDF ID
        page_numbers: 可选，指定要解析的页码列表 (从1开始)
    """
    doc = fitz.open(filepath)
    paragraphs = []
    
    try:
        if page_numbers:
            pages_to_process = [p - 1 for p in page_numbers if 1 <= p <= len(doc)]
        else:
            pages_to_process = range(len(doc))

        for page_idx in pages_to_process:
            page = doc[page_idx]
            page_num = page_idx + 1
            
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
                if len(clean_text.split()) < 5:  # 稍微放宽限制
                    continue

                # 生成确定性的段落ID，方便前端定位
                # 格式: pdf_chk_{pdf_id前8位}_{页码}_{块号}
                para_id = make_paragraph_id(pdf_id, page_num, block_no)

                paragraphs.append({
                    "id": para_id,
                    "page": page_num,
                    "index": block_no,
                    "bbox": [x0, y0, x1 - x0, y1 - y0], # x, y, w, h
                    "content": clean_text,
                    "wordCount": len(clean_text.split())
                })
    finally:
        doc.close()
    
    return paragraphs

def get_images_list(filepath: str, pdf_id: str, page_numbers: list[int] = None) -> list[dict]:
    """
    获取PDF所有图片的元数据列表（ID、页码、坐标），不包含Base64内容。
    如果 MinerU 已在 Celery 任务中提取过图片并写入 DB，
    这个函数主要作为回退方案使用。

    Args:
        filepath: PDF 文件路径
        pdf_id: PDF 唯一标识
        page_numbers: 可选，指定页码列表 (1-based)
    """
    doc = fitz.open(filepath)
    images_meta = []

    try:
        if page_numbers:
            pages_to_process = [p - 1 for p in page_numbers if 1 <= p <= len(doc)]
        else:
            pages_to_process = range(len(doc))

        global_index = 0
        for page_idx in pages_to_process:
            page = doc[page_idx]
            page_num = page_idx + 1
            page_images = page.get_image_info(xrefs=True)

            for img in page_images:
                xref = img['xref']
                bbox = img['bbox']
                image_id = make_image_id(pdf_id, global_index)

                images_meta.append({
                    "id": image_id,
                    "page": page_num,
                    "index": global_index,
                    "bbox": [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]],
                    "xref": xref,
                })
                global_index += 1
    finally:
        doc.close()

    return images_meta

def get_image_data(filepath: str, image_index: int) -> dict:
    """
    根据图片索引（xref）获取 Base64 编码数据。
    这是一个基础的 PyMuPDF 提取方式，
    MinerU 提取的高质量图片直接通过文件路径读取。
    """
    doc = fitz.open(filepath)
    try:
        # 遍历所有页面找到对应 xref 的图片
        # image_index 在这里是逻辑索引，需要遍历匹配
        global_idx = 0
        for page in doc:
            page_images = page.get_image_info(xrefs=True)
            for img in page_images:
                if global_idx == image_index:
                    xref = img['xref']
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    base64_str = base64.b64encode(image_bytes).decode('utf-8')
                    mime_type = f"image/{image_ext}"

                    return {
                        "mimeType": mime_type,
                        "base64": f"data:{mime_type};base64,{base64_str}"
                    }
                global_idx += 1

        raise ValueError(f"Image index {image_index} not found in PDF")
    finally:
        doc.close()


def get_image_data_from_path(image_path: str) -> dict:
    """
    从本地文件路径读取图片并返回 Base64 编码数据。
    用于读取 MinerU 提取出的高质量图片。

    Args:
        image_path: 图片文件的绝对路径

    Returns:
        {"mimeType": str, "base64": str}
    """
    from pathlib import Path
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    ext = p.suffix.lower().lstrip(".")
    mime_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "webp": "image/webp",
        "svg": "image/svg+xml",
    }
    mime_type = mime_map.get(ext, f"image/{ext}")

    with open(p, "rb") as f:
        image_bytes = f.read()

    base64_str = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "mimeType": mime_type,
        "base64": f"data:{mime_type};base64,{base64_str}",
    }
