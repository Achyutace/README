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

def get_images_list(filepath: str, pdf_id: str) -> list[dict]:
    """
    获取PDF所有图片的元数据列表（ID、页码、坐标），不包含Base64内容。
    """
    '''
    doc = fitz.open(filepath)
    images_meta = []
    
    try:
        for page_num, page in enumerate(doc):
            # get_image_info(xrefs=True) 返回页面图片信息
            page_images = page.get_image_info(xrefs=True)
            
            for img in page_images:
                # 目前逻辑上将 PDF 的 xref 映射为 image_index
                image_index = img['xref']
                bbox = img['bbox']
                
                # 构造逻辑图片ID
                image_id = make_image_id(pdf_id, image_index)
                
                images_meta.append({
                    "id": image_id,
                    "page": page_num + 1,
                    "index": image_index,
                    "bbox": [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]]
                })
    finally:
        doc.close()
    return images_meta
    '''
    pass

def get_image_data(filepath: str, image_index: int) -> dict:
    """
    根据图片索引（目前为xref）获取Base64编码数据。
    """
    '''
    doc = fitz.open(filepath)
    try:
        # 目前直接使用 image_index 作为 xref 提取图片
        base_image = doc.extract_image(image_index)
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
    '''
    pass
