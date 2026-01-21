"""
存储服务 TODO

提供 PDF 文件、段落、图片、笔记和高亮的统一存储接口
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from models.database import Database
from PIL import Image


class StorageService:
    """封装数据库操作"""
    
    def __init__(self, storage_root: str, user_id: str = 'default'):
        """
        初始化存储服务
        
        Args:
            storage_root: 存储根目录
            user_id: 用户ID
        """
        self.storage_root = Path(storage_root)
        self.user_id = user_id
        
        # 存储根目录存在
        self.storage_root.mkdir(parents=True, exist_ok=True)
        
        # 创建图片存储目录（按 file_hash 分组）
        self.images_folder = self.storage_root / 'images'
        self.images_folder.mkdir(parents=True, exist_ok=True)

        # 创建PDF存储目录 (全局数据共享)
        self.uploads_folder = self.storage_root / 'uploads'
        self.uploads_folder.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库（全局共享数据库，通过 user_id 区分用户）
        db_path = self.storage_root / 'app.db'
        self.db = Database(str(db_path))
    
    # ==================== PDF 文件管理 ====================
    
    def register_pdf(self, file_path: str, filename: str, 
                    page_count: int = 0, metadata: Dict = None) -> str:
        """
        注册 PDF 文件
        
        Args:
            file_path: 文件路径
            filename: 文件名
            page_count: 页数
            metadata: 元数据
            
        Returns:
            文件哈希值
        """
        return self.db.add_pdf_file(
            file_path=file_path,
            filename=filename,
            user_id=self.user_id,
            page_count=page_count,
            metadata=metadata
        )
    
    def persist_pdf_parsing(self, 
                          file_path: str, 
                          file_hash: str, 
                          filename: str,
                          page_count: int,
                          paragraphs: List[Dict],
                          images: List[Dict] = None,
                          user_id: str = "default") -> bool:
        """
        将 PDF 解析结果（元数据、段落、图片索引）持久化到数据库
        通常在 PdfService 解析完文件后调用
        """
        try:
            # 1. 保存文件元数据
            self.db.add_pdf_file(
                file_path=file_path,
                filename=filename,
                user_id=user_id,
                page_count=page_count,
                file_hash=file_hash
            )

            # 2. 批量保存段落
            if paragraphs:
                # 预处理 paragraphs，确保包含 index
                processed_paras = []
                for idx, p in enumerate(paragraphs):
                    # 如果 pdf_service 没给 index，手动加上
                    if 'index' not in p:
                        p['index'] = idx
                    processed_paras.append(p)
                
                self.db.add_paragraphs_batch(file_hash, processed_paras)

            return True
        except Exception as e:
            print(f"Error persisting PDF data: {e}")
            return False
        
    def get_pdf_info(self, file_hash: str) -> Optional[Dict]:
        """
        获取 PDF 文件信息
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            文件信息
        """
        return self.db.get_pdf_file(file_hash)
    
    def list_pdfs(self, limit: int = 100) -> List[Dict]:
        """
        列出用户的所有 PDF 文件
        
        Args:
            limit: 返回数量限制
            
        Returns:
            文件列表
        """
        return self.db.list_pdf_files(user_id=self.user_id, limit=limit)
    
    def delete_pdf(self, file_hash: str, delete_physical_file: bool = True) -> Dict:
        """
        删除 PDF 文件及其所有关联数据
        
        Args:
            file_hash: 文件哈希值
            delete_physical_file: 是否删除物理文件（默认 True）
            
        Returns:
            删除结果字典
        """
        # 获取文件信息
        pdf_info = self.get_pdf_info(file_hash)
        if not pdf_info:
            return {
                'success': False,
                'error': 'PDF file not found'
            }
        
        # 获取图片列表（用于删除物理图片文件）
        images = self.get_images(file_hash)
        
        # 删除数据库记录（级联删除关联数据）
        stats = self.db.delete_pdf_file(file_hash)
        
        result = {
            'success': True,
            'stats': stats,
            'physical_file_deleted': False,
            'image_files_deleted': 0
        }
        
        # 删除物理文件
        if delete_physical_file:
            try:
                file_path = Path(pdf_info['file_path'])
                if file_path.exists():
                    file_path.unlink()
                    result['physical_file_deleted'] = True
            except Exception as e:
                result['physical_file_delete_error'] = str(e)
        
        # 删除图片文件
        if images:
            try:
                self.delete_images(file_hash)
                result['image_files_deleted'] = len(images)
            except Exception as e:
                result['image_files_delete_error'] = str(e)
        
        return result
    
    def check_pdf_exists(self, file_hash: str) -> bool:
        """
        检查 PDF 文件是否存在
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            文件是否存在
        """
        return self.db.check_pdf_exists(file_hash)
    
    # ==================== 供段落翻译使用 ====================
    
    def save_paragraphs(self, file_hash: str, page_number: int, 
                       paragraphs: List[Dict]) -> List[int]:
        """
        批量保存段落
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            paragraphs: 段落列表，每个段落包含 text, bbox 等字段
            
        Returns:
            段落ID列表
        """
        paragraph_ids = []
        for idx, para in enumerate(paragraphs):
            para_id = self.db.add_paragraph(
                file_hash=file_hash,
                page_number=page_number,
                paragraph_index=idx,
                original_text=para.get('text', ''),
                translation_text=para.get('translation'),
                bbox=para.get('bbox')
            )
            paragraph_ids.append(para_id)
        return paragraph_ids
    
    def save_paragraph_translation(self, file_hash: str, page_number: int,
                                  paragraph_index: int, translation: str):
        """
        保存段落翻译
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            paragraph_index: 段落索引
            translation: 翻译文本
        """
        self.db.update_paragraph_translation(
            file_hash=file_hash,
            page_number=page_number,
            paragraph_index=paragraph_index,
            translation_text=translation
        )
    
    def get_paragraphs(self, file_hash: str, page_number: int = None) -> List[Dict]:
        """
        获取段落列表
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码（可选）
            
        Returns:
            段落列表
        """
        return self.db.get_paragraphs(file_hash, page_number)
    
    def get_page_content(self, file_hash: str, page_number: int) -> Dict:
        """
        获取页面完整内容（包括原文和翻译）
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            
        Returns:
            页面内容字典
        """
        paragraphs = self.get_paragraphs(file_hash, page_number)
        
        original_texts = []
        translations = []
        
        for para in paragraphs:
            original_texts.append(para['original_text'])
            if para.get('translation_text'):
                translations.append(para['translation_text'])
        
        return {
            'page_number': page_number,
            'paragraphs': paragraphs,
            'original_full_text': '\n\n'.join(original_texts),
            'translation_full_text': '\n\n'.join(translations) if translations else None
        }
    
    def get_paragraph_translation(self, file_hash: str, page_number: int, 
                                  paragraph_index: int) -> Optional[str]:
        """
        获取段落翻译
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            paragraph_index: 段落索引
            
        Returns:
            翻译文本，如果不存在返回 None
        """
        return self.db.get_paragraph_translation(file_hash, page_number, paragraph_index)
    
    def get_full_text(self, file_hash: str, include_translation: bool = False,
                     page_number: int = None) -> str:
        """
        获取 PDF 的完整文本内容
        
        Args:
            file_hash: 文件哈希值
            include_translation: 是否包含翻译（如果为 True，将原文和译文拼接）
            page_number: 页码（可选，如果不指定则返回整个文档）
            
        Returns:
            完整文本内容，段落之间用双换行符分隔
        """
        return self.db.get_full_text(file_hash, include_translation, page_number)
    
    def get_page_text(self, file_hash: str, page_number: int, 
                     include_translation: bool = False) -> Dict[str, str]:
        """
        获取指定页面的文本内容
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            include_translation: 是否包含翻译
            
        Returns:
            包含原文和译文的字典
        """
        return self.db.get_page_text(file_hash, page_number, include_translation)
    
    # ==================== 图片管理 TODO====================
    
    def save_image(self, file_hash: str, page_number: int, image_index: int,
                   image_data: bytes, image_format: str = 'png',
                   bbox: Dict = None) -> Dict:
        """
        保存图片到文件系统并在数据库中创建索引
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            image_index: 图片索引
            image_data: 图片二进制数据
            image_format: 图片格式
            bbox: 边界框坐标
            
        Returns:
            图片信息字典
        """
        # 创建文件专属图片目录
        image_dir = self.images_folder / file_hash
        image_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成图片文件名
        image_filename = f"page_{page_number}_img_{image_index}.{image_format}"
        image_path = image_dir / image_filename
        
        # 保存图片文件
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        # 获取图片尺寸和大小
        try:
            with Image.open(image_path) as img:
                width, height = img.size
        except:
            width, height = None, None
        
        file_size = image_path.stat().st_size
        
        # 存储相对路径（相对于 images_folder）
        relative_path = f"{file_hash}/{image_filename}"
        
        # 在数据库中创建索引
        image_id = self.db.add_image(
            file_hash=file_hash,
            page_number=page_number,
            image_index=image_index,
            image_path=relative_path,
            image_format=image_format,
            width=width,
            height=height,
            file_size=file_size,
            bbox=bbox
        )
        
        return {
            'id': image_id,
            'image_path': relative_path,
            'full_path': str(image_path),
            'width': width,
            'height': height,
            'file_size': file_size,
            'format': image_format
        }
    
    def get_images(self, file_hash: str, page_number: int = None) -> List[Dict]:
        """
        获取图片列表
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码（可选）
            
        Returns:
            图片列表
        """
        images = self.db.get_images(file_hash, page_number)
        
        # 补充完整路径
        for img in images:
            img['full_path'] = str(self.images_folder / img['image_path'])
            img['url_path'] = f"/api/storage/images/{img['image_path']}"
        
        return images
    
    def get_image_path(self, file_hash: str, page_number: int, 
                      image_index: int) -> Optional[str]:
        """
        获取图片的完整文件路径
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            image_index: 图片索引
            
        Returns:
            图片文件路径
        """
        images = self.db.get_images(file_hash, page_number)
        for img in images:
            if img['image_index'] == image_index:
                return str(self.images_folder / img['image_path'])
        return None
    
    def delete_images(self, file_hash: str, page_number: int = None):
        """
        删除图片文件和数据库记录
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码（可选，不指定则删除所有页）
        """
        # 获取要删除的图片列表
        images = self.db.get_images(file_hash, page_number)
        
        # 删除文件
        for img in images:
            image_path = self.images_folder / img['image_path']
            if image_path.exists():
                image_path.unlink()
        
        # 删除数据库记录
        self.db.delete_images(file_hash, page_number)
        
        # 如果目录为空，删除目录
        image_dir = self.images_folder / file_hash
        if image_dir.exists() and not any(image_dir.iterdir()):
            image_dir.rmdir()
    
    # ==================== 笔记管理 TODO====================
    
    def add_note(self, file_hash: str, note_content: str,
                page_number: int = None, note_type: str = 'general',
                color: str = '#FFEB3B', position: Dict = None) -> int:
        """
        添加笔记
        
        Args:
            file_hash: 文件哈希值
            note_content: 笔记内容
            page_number: 页码
            note_type: 笔记类型 (general, summary, question, idea)
            color: 颜色
            position: 位置信息 {x, y, width, height}
            
        Returns:
            笔记ID
        """
        return self.db.add_note(
            file_hash=file_hash,
            user_id=self.user_id,
            note_content=note_content,
            page_number=page_number,
            note_type=note_type,
            color=color,
            position=position
        )
    
    def update_note(self, note_id: int, note_content: str, color: str = None):
        """
        更新笔记
        
        Args:
            note_id: 笔记ID
            note_content: 笔记内容
            color: 颜色
        """
        self.db.update_note(note_id, note_content, color)
    
    def delete_note(self, note_id: int):
        """
        删除笔记
        
        Args:
            note_id: 笔记ID
        """
        self.db.delete_note(note_id)
    
    def get_notes(self, file_hash: str, page_number: int = None) -> List[Dict]:
        """
        获取笔记列表
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码（可选）
            
        Returns:
            笔记列表
        """
        return self.db.get_notes(file_hash, self.user_id, page_number)
    
    # ==================== 高亮管理 TODO====================
    
    def add_highlight(self, file_hash: str, page_number: int,
                     highlighted_text: str, bbox: Dict,
                     color: str = '#FFFF00', comment: str = None) -> int:
        """
        添加高亮
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            highlighted_text: 高亮文本
            bbox: 边界框坐标 {x0, y0, x1, y1}
            color: 颜色
            comment: 注释
            
        Returns:
            高亮ID
        """
        return self.db.add_highlight(
            file_hash=file_hash,
            user_id=self.user_id,
            page_number=page_number,
            highlighted_text=highlighted_text,
            bbox=bbox,
            color=color,
            comment=comment
        )
    
    def update_highlight(self, highlight_id: int, color: str = None,
                        comment: str = None):
        """
        更新高亮
        
        Args:
            highlight_id: 高亮ID
            color: 颜色
            comment: 注释
        """
        self.db.update_highlight(highlight_id, color, comment)
    
    def delete_highlight(self, highlight_id: int):
        """
        删除高亮
        
        Args:
            highlight_id: 高亮ID
        """
        self.db.delete_highlight(highlight_id)
    
    def get_highlights(self, file_hash: str, page_number: int = None) -> List[Dict]:
        """
        获取高亮列表
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码（可选）
            
        Returns:
            高亮列表
        """
        return self.db.get_highlights(file_hash, self.user_id, page_number)
    
    # ==================== 综合查询 TODO====================
    
    def get_page_annotations(self, file_hash: str, page_number: int) -> Dict:
        """
        获取页面的所有标注信息（笔记+高亮）
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            
        Returns:
            标注信息字典
        """
        return {
            'page_number': page_number,
            'notes': self.get_notes(file_hash, page_number),
            'highlights': self.get_highlights(file_hash, page_number)
        }
    
    def get_document_summary(self, file_hash: str) -> Dict:
        """
        获取文档摘要信息
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            文档摘要
        """
        pdf_info = self.get_pdf_info(file_hash)
        if not pdf_info:
            return None
        
        all_notes = self.get_notes(file_hash)
        all_highlights = self.get_highlights(file_hash)
        all_paragraphs = self.get_paragraphs(file_hash)
        
        # 统计翻译进度
        total_paragraphs = len(all_paragraphs)
        translated_paragraphs = sum(
            1 for p in all_paragraphs if p.get('translation_text')
        )
        
        return {
            'file_info': pdf_info,
            'statistics': {
                'total_pages': pdf_info.get('page_count', 0),
                'total_paragraphs': total_paragraphs,
                'translated_paragraphs': translated_paragraphs,
                'translation_progress': (
                    (translated_paragraphs / total_paragraphs * 100) 
                    if total_paragraphs > 0 else 0
                ),
                'total_notes': len(all_notes),
                'total_highlights': len(all_highlights)
            },
            'recent_notes': all_notes[:5],  # 最近5条笔记
            'recent_highlights': all_highlights[:5]  # 最近5条高亮
        }
