import os
import uuid
import fitz  # PyMuPDF
from werkzeug.utils import secure_filename
import base64


class PdfService:
    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        self.pdf_registry: dict[str, dict] = {}

    def save_and_process(self, file) -> dict:
        """Save uploaded PDF and extract basic info."""
        pdf_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        filepath = os.path.join(self.upload_folder, f"{pdf_id}_{filename}")

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
            'pageCount': page_count
        }

    def get_filepath(self, pdf_id: str) -> str:
        """Get filepath for a PDF by ID."""
        if pdf_id in self.pdf_registry:
            return self.pdf_registry[pdf_id]['filepath']

        # Search in upload folder if not in registry
        for filename in os.listdir(self.upload_folder):
            if filename.startswith(pdf_id):
                filepath = os.path.join(self.upload_folder, filename)
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
        """
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
        """
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
            
            return {
                "id": image_id,
                "mimeType": mime_type,
                "base64": f"data:{mime_type};base64,{base64_str}"
            }
            
        except Exception as e:
            # 记录错误或抛出
            print(f"Error fetching image {image_id}: {e}")
            return None
        
    
    