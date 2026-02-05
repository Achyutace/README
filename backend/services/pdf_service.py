"""
PDF服务
1. PDF管理（上传：解析+存储 删除：数据库删除）
2. PDF资源获取 (根据pdf_id获取pdf资源)

"""
import os
import uuid
import json
import hashlib
from pathlib import Path
from werkzeug.utils import secure_filename
from utils import pdf_engine

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

        # 设置图片缓存子目录
        self.images_cache = os.path.join(self.cache_folder, 'images')
        os.makedirs(self.images_cache, exist_ok=True)


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
            page_count = pdf_engine.get_page_count(existing_filepath)
            
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
        page_count = pdf_engine.get_page_count(filepath)

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
        return pdf_engine.get_pdf_info(pdf_id, filepath)

    def get_page_dimensions(self, pdf_id: str, page_number: int) -> dict:
        """获取特定页面的尺寸，用于坐标转换"""
        filepath = self.get_filepath(pdf_id)
        return pdf_engine.get_page_dimensions(filepath, page_number)
            
    def extract_text(self, pdf_id: str, page_number: int = None) -> dict:
        """Extract text from PDF, optionally from specific page."""
        filepath = self.get_filepath(pdf_id)
        return pdf_engine.extract_text(filepath, page_number)

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
        paragraphs = pdf_engine.parse_paragraphs(filepath, pdf_id)
        
        # 写入缓存
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(paragraphs, f, ensure_ascii=False, indent=2)
        
        return paragraphs
    
    def get_images_list(self, pdf_id: str) -> list[dict]:
        """
        预处理：获取PDF所有图片的元数据列表（ID、页码、坐标），不包含Base64内容。
        """
        filepath = self.get_filepath(pdf_id)
        return pdf_engine.get_images_list(filepath, pdf_id)

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
            
            result = pdf_engine.get_image_data(filepath, xref)
            result['id'] = image_id
            
            # 写入缓存
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            return result
            
        except Exception as e:
            # 记录错误或抛出
            print(f"Error fetching image {image_id}: {e}")
            return None


