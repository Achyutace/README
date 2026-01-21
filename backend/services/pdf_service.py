"""
PDF服务
1. PDF upload
2. PDF delete

"""
import os
import uuid
import json
import hashlib
from pathlib import Path
import fitz  # PyMuPDF
from werkzeug.utils import secure_filename
import base64

class PdfService:
    def __init__(self, upload_folder: str, cache_folder: str = None):
        """
        初始化 PDF 服务
        
        Args:
            upload_folder: PDF 文件上传目录
            cache_folder: 缓存文件目录（可选）
        """
        self.upload_folder = upload_folder
        self.pdf_registry: dict[str, dict] = {}
        
        # 设置缓存目录
        if cache_folder:
            self.cache_folder = cache_folder
        else:
            self.cache_folder = os.path.join(os.path.dirname(upload_folder), 'cache')
        
        # 确保缓存目录存在
        os.makedirs(self.cache_folder, exist_ok=True)
        
        # 设置段落缓存子目录
        self.paragraphs_cache = os.path.join(self.cache_folder, 'paragraphs')
        os.makedirs(self.paragraphs_cache, exist_ok=True)

    def _find_filepath_by_id(self, pdf_id: str) -> str:
        """
        根据 ID (Hash) 在上传目录查找文件
        文件名约定: {hash}_{filename} 
        """
        # 1. 查内存注册表
        if pdf_id in self.pdf_registry:
            return self.pdf_registry[pdf_id]['filepath']
            
        # 2. 查磁盘 (文件名以 pdf_id 开头)
        if os.path.exists(self.upload_folder):
            prefix = f"{pdf_id}"
            for fname in os.listdir(self.upload_folder):
                if fname.startswith(prefix) and (len(fname) == len(prefix) or fname[len(prefix)] in ['_', '.']):
                    return os.path.join(self.upload_folder, fname)
        return None

    def save_and_process(self, file, file_hash: str) -> dict:
        """
        保存上传的 PDF 并提取基本信息
        
        Args:
            file: 上传的文件对象
            file_hash: 文件的 SHA256 哈希值
            
        Returns:
            包含 id, filename, pageCount, exists 的字典
        """
        pdf_id = file_hash
        filename = secure_filename(file.filename)
        
        # 1. 检查是否已存在 (秒传)
        existing_filepath = self._find_filepath_by_id(pdf_id)
        
        if existing_filepath:
            # 文件已存在，不再重复写入磁盘
            doc = fitz.open(existing_filepath)
            page_count = len(doc)
            doc.close()
            
            # 确保注册表中有它
            self.pdf_registry[pdf_id] = {
                'id': pdf_id,
                'filename': filename,
                'filepath': existing_filepath,
                'pageCount': page_count
            }
            
            return {
                'id': pdf_id,
                'filename': filename,
                'pageCount': page_count,
                'exists': True  # 标记已存在
            }

        # 2. 文件不存在，保存新文件
        # 格式: {hash}_{filename}
        save_filename = f"{pdf_id}_{filename}"
        filepath = os.path.join(self.upload_folder, save_filename)

        file.save(filepath)

        # Open PDF to get page count
        doc = fitz.open(filepath)
        page_count = len(doc)
        doc.close()

        # Store in registry
        self.pdf_registry[pdf_id] = {
            'id': pdf_id,
            'filename': filename,
            'filepath': filepath,
            'pageCount': page_count
        }

        return {
            'id': pdf_id,
            'filename': filename,
            'pageCount': page_count,
            'exists': False
        }

    def get_filepath(self, pdf_id: str) -> str:
        """Get filepath for a PDF by ID."""
        filepath = self._find_filepath_by_id(pdf_id)
        
        if filepath:
            return filepath

        raise FileNotFoundError(f"PDF not found: {pdf_id}")

    def get_info(self, pdf_id: str) -> dict:
        """Get PDF info by ID."""
        filepath = self.get_filepath(pdf_id)
        doc = fitz.open(filepath)

        info = {
            'id': pdf_id,
            'pageCount': len(doc),
            'metadata': doc.metadata
        }

        doc.close()
        return info

    def get_page_dimensions(self, pdf_id: str, page_number: int) -> dict:
        """获取特定页面的尺寸，用于坐标转换"""
        filepath = self.get_filepath(pdf_id)
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
            
    def extract_text(self, pdf_id: str, page_number: int = None) -> dict:
        """Extract text from PDF, optionally from specific page."""
        filepath = self.get_filepath(pdf_id)
        doc = fitz.open(filepath)

        blocks = []
        full_text = []

        if page_number is not None:
            # Extract from specific page (1-indexed)
            if page_number < 1 or page_number > len(doc):
                doc.close()
                raise ValueError(f"Invalid page number: {page_number}")

            page = doc[page_number - 1]
            page_blocks = self._extract_page_blocks(page, page_number)
            blocks.extend(page_blocks)
            full_text.append(page.get_text())
        else:
            # Extract from all pages
            for i, page in enumerate(doc):
                page_blocks = self._extract_page_blocks(page, i + 1)
                blocks.extend(page_blocks)
                full_text.append(page.get_text())

        doc.close()

        return {
            'text': '\n\n'.join(full_text),
            'blocks': blocks
        }

    def _extract_page_blocks(self, page, page_number: int) -> list:
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

    def parse_paragraphs(self, pdf_id: str) -> list[dict]:
        """
        预处理：
        解析PDF段落结构：识别PDF段落
        返回：包含段落ID、文本内容、页面信息和坐标范围的列表。
        使用缓存加速重复请求。
        """
        # 尝试从缓存读取
        cache_file = os.path.join(self.paragraphs_cache, f"{pdf_id}.json")
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 缓存未命中，开始解析
        filepath = self.get_filepath(pdf_id)
        doc = fitz.open(filepath)
        paragraphs = []
        
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

        doc.close()
        
        # 写入缓存
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(paragraphs, f, ensure_ascii=False, indent=2)
        
        return paragraphs
    
    def get_images_list(self, pdf_id: str) -> list[dict]:
        """
        预处理：获取PDF所有图片的元数据列表（ID、页码、坐标），不包含Base64内容。
        """
        filepath = self.get_filepath(pdf_id)
        doc = fitz.open(filepath)
        images_meta = []
        
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

        doc.close()
        return images_meta

    def get_image_data(self, image_id: str) -> dict:
        """
        根据图片ID获取Base64编码数据。
        ID格式需严格匹配 get_images_list 生成的格式。
        使用缓存加速重复请求。
        """
        # 尝试从缓存读取
        cache_file = os.path.join(self.images_cache, f"{image_id}.json")
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        try:
            # 解析 ID
            # 格式: {pdf_id}__xref__{xref}
            if "__xref__" not in image_id:
                raise ValueError("Invalid image ID format")
                
            pdf_id, xref_str = image_id.split("__xref__")
            xref = int(xref_str)
            
            filepath = self.get_filepath(pdf_id)
            doc = fitz.open(filepath)
            
            # 使用 xref 直接提取图片
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            doc.close()
            
            # 转为 Base64
            base64_str = base64.b64encode(image_bytes).decode('utf-8')
            mime_type = f"image/{image_ext}"
            
            result = {
                "id": image_id,
                "mimeType": mime_type,
                "base64": f"data:{mime_type};base64,{base64_str}"
            }
            
            # 写入缓存
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            return result
            
        except Exception as e:
            # 记录错误或抛出
            print(f"Error fetching image {image_id}: {e}")
            return None


