"""
SQLite 数据库模型定义

数据库结构：
1. pdf_files: PDF 文件基本信息
2. pdf_paragraphs: PDF 段落文本和翻译
3. pdf_images: PDF 图片索引（存储图片路径和元数据）
4. user_notes: 用户笔记
5. user_highlights: 用户高亮信息
6. user_info: 用户信息【 TODO 暂时不写】
"""

import sqlite3
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class Database:

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
    
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 结果可以通过列名访问
        conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
        return conn
    
    def init_database(self):
        """初始化数据库表结构"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. PDF 文件表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdf_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                user_id TEXT,
                page_count INTEGER,
                file_size INTEGER,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_access_time TIMESTAMP,
                metadata TEXT,
                UNIQUE(file_hash)
            )
        ''')
        
        # 2. PDF 段落表（存储段落解析文本和翻译）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdf_paragraphs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                paragraph_index INTEGER NOT NULL,
                original_text TEXT NOT NULL,
                translation_text TEXT,
                bbox TEXT,
                created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE CASCADE,
                UNIQUE(file_hash, page_number, paragraph_index)
            )
        ''')
        
        # 3. PDF 图片表（存储图片文件路径和元数据）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdf_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                image_index INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                image_format TEXT,
                width INTEGER,
                height INTEGER,
                file_size INTEGER,
                bbox TEXT,
                extracted_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE CASCADE,
                UNIQUE(file_hash, page_number, image_index)
            )
        ''')
        
        # 4. 用户笔记表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                user_id TEXT NOT NULL,
                page_number INTEGER,
                note_content TEXT NOT NULL,
                note_type TEXT DEFAULT 'general',
                color TEXT DEFAULT '#FFEB3B',
                position TEXT,
                created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE CASCADE
            )
        ''')
        
        # 5. 用户高亮表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_highlights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                user_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                highlighted_text TEXT NOT NULL,
                color TEXT DEFAULT '#FFFF00',
                bbox TEXT NOT NULL,
                comment TEXT,
                created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE CASCADE
            )
        ''')
        
        # 6. 聊天记录表（存储用户和AI的对话历史）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                file_hash TEXT,
                title TEXT,
                created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (file_hash) REFERENCES pdf_files(file_hash) ON DELETE SET NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
            )
        ''')
        
        # 创建索引以提高查询性能
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_paragraphs_file_hash 
            ON pdf_paragraphs(file_hash)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_paragraphs_page 
            ON pdf_paragraphs(file_hash, page_number)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_file_hash 
            ON pdf_images(file_hash)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_images_page 
            ON pdf_images(file_hash, page_number)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_notes_file_user 
            ON user_notes(file_hash, user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_highlights_file_user 
            ON user_highlights(file_hash, user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user 
            ON chat_sessions(user_id, updated_time DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session 
            ON chat_messages(session_id, created_time)
        ''')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        计算文件的 SHA256 哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件的 SHA256 哈希值
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    @staticmethod
    def calculate_stream_hash(file_stream) -> str:
        """
        计算文件流的 SHA256 哈希值
        
        Args:
            file_stream: 文件流对象（如 Flask 的 FileStorage.stream）
            
        Returns:
            文件流的 SHA256 哈希值
        """
        sha256_hash = hashlib.sha256()
        # 保存当前位置
        current_position = file_stream.tell()
        # 重置到开头
        file_stream.seek(0)
        # 读取并计算哈希
        for byte_block in iter(lambda: file_stream.read(4096), b""):
            sha256_hash.update(byte_block)
        # 恢复原来的位置
        file_stream.seek(current_position)
        return sha256_hash.hexdigest()
    
    # ==================== PDF 文件操作 ====================
    
    def add_pdf_file(self, file_path: str, filename: str, user_id: str = None, 
                     page_count: int = 0, metadata: Dict = None,
                     file_hash: Optional[str] = None) -> str:
        """
        添加 PDF 文件记录
        
        Args:
            file_path: 文件路径
            filename: 文件名
            user_id: 用户ID
            page_count: 页数
            metadata: 元数据
            file_hash: 预计算的哈希值
            
        Returns:
            文件哈希值
        """
        if not file_hash:
            file_hash = self.calculate_file_hash(file_path)
        file_size = Path(file_path).stat().st_size
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO pdf_files (file_hash, filename, file_path, user_id, 
                                      page_count, file_size, metadata, last_access_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (file_hash, filename, file_path, user_id, page_count, file_size,
                  json.dumps(metadata) if metadata else None))
            conn.commit()
        except sqlite3.IntegrityError:
            # 文件已存在，更新访问时间
            cursor.execute('''
                UPDATE pdf_files 
                SET last_access_time = CURRENT_TIMESTAMP
                WHERE file_hash = ?
            ''', (file_hash,))
            conn.commit()
        finally:
            conn.close()
        
        return file_hash
    
    def get_pdf_file(self, file_hash: str) -> Optional[Dict]:
        """
        获取 PDF 文件信息
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            文件信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM pdf_files WHERE file_hash = ?', (file_hash,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            result = dict(row)
            if result.get('metadata'):
                result['metadata'] = json.loads(result['metadata'])
            return result
        return None
    
    def list_pdf_files(self, user_id: str = None, limit: int = 100) -> List[Dict]:
        """
        列出 PDF 文件
        
        Args:
            user_id: 用户ID（可选）
            limit: 返回数量限制
            
        Returns:
            文件列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT * FROM pdf_files 
                WHERE user_id = ? 
                ORDER BY last_access_time DESC 
                LIMIT ?
            ''', (user_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM pdf_files 
                ORDER BY last_access_time DESC 
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get('metadata'):
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)
        return results
    
    def delete_pdf_file(self, file_hash: str) -> Dict[str, int]:
        """
        删除 PDF 文件及其所有关联数据
        
        由于设置了外键级联删除（ON DELETE CASCADE），删除 PDF 文件时会自动删除：
        - pdf_paragraphs（段落）
        - pdf_images（图片记录）
        - user_notes（笔记）
        - user_highlights（高亮）
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            删除统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {
            'pdf_deleted': 0,
            'paragraphs_deleted': 0,
            'images_deleted': 0,
            'notes_deleted': 0,
            'highlights_deleted': 0
        }
        
        try:
            # 统计关联数据数量（在删除前）
            cursor.execute('SELECT COUNT(*) FROM pdf_paragraphs WHERE file_hash = ?', (file_hash,))
            stats['paragraphs_deleted'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM pdf_images WHERE file_hash = ?', (file_hash,))
            stats['images_deleted'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM user_notes WHERE file_hash = ?', (file_hash,))
            stats['notes_deleted'] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM user_highlights WHERE file_hash = ?', (file_hash,))
            stats['highlights_deleted'] = cursor.fetchone()[0]
            
            # 删除 PDF 文件（级联删除会自动处理关联数据）
            cursor.execute('DELETE FROM pdf_files WHERE file_hash = ?', (file_hash,))
            stats['pdf_deleted'] = cursor.rowcount
            
            conn.commit()
        
        except Exception as e:
            conn.rollback()
            raise e
        
        finally:
            conn.close()
        
        return stats
    
    def check_pdf_exists(self, file_hash: str) -> bool:
        """
        检查 PDF 文件是否存在
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            文件是否存在
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM pdf_files WHERE file_hash = ?', (file_hash,))
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    # ==================== 段落操作 ====================
    
    def add_paragraph(self, file_hash: str, page_number: int, paragraph_index: int,
                     original_text: str, translation_text: str = None, 
                     bbox: Dict = None) -> int:
        """
        添加段落
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            paragraph_index: 段落索引
            original_text: 原文
            translation_text: 翻译文本
            bbox: 边界框坐标
            
        Returns:
            段落ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO pdf_paragraphs 
                (file_hash, page_number, paragraph_index, original_text, 
                 translation_text, bbox)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (file_hash, page_number, paragraph_index, original_text,
                  translation_text, json.dumps(bbox) if bbox else None))
            conn.commit()
            paragraph_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            # 段落已存在，更新内容
            cursor.execute('''
                UPDATE pdf_paragraphs 
                SET original_text = ?, translation_text = ?, bbox = ?,
                    updated_time = CURRENT_TIMESTAMP
                WHERE file_hash = ? AND page_number = ? AND paragraph_index = ?
            ''', (original_text, translation_text, 
                  json.dumps(bbox) if bbox else None,
                  file_hash, page_number, paragraph_index))
            conn.commit()
            cursor.execute('''
                SELECT id FROM pdf_paragraphs 
                WHERE file_hash = ? AND page_number = ? AND paragraph_index = ?
            ''', (file_hash, page_number, paragraph_index))
            paragraph_id = cursor.fetchone()[0]
        finally:
            conn.close()
        
        return paragraph_id
    
    def add_paragraphs_batch(self, file_hash: str, paragraphs: List[Dict]) -> int:
        """
        批量添加段落
        
        Args:
            file_hash: 文件哈希值
            paragraphs: 段落列表，每个段落包含:
                - page: 页码
                - index: 段落索引（可选，默认使用列表索引）
                - content: 原文内容
                - bbox: 边界框坐标（可选）
                
        Returns:
            成功添加的段落数量
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        added_count = 0
        
        try:
            for para in paragraphs:
                page_number = para.get('page', 1)
                paragraph_index = para.get('index', 0)
                original_text = para.get('content', '')
                bbox = para.get('bbox')
                
                if not original_text:
                    continue
                
                try:
                    cursor.execute('''
                        INSERT INTO pdf_paragraphs 
                        (file_hash, page_number, paragraph_index, original_text, bbox)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (file_hash, page_number, paragraph_index, original_text,
                          json.dumps(bbox) if bbox else None))
                    added_count += 1
                except sqlite3.IntegrityError:
                    # 段落已存在，更新内容
                    cursor.execute('''
                        UPDATE pdf_paragraphs 
                        SET original_text = ?, bbox = ?, updated_time = CURRENT_TIMESTAMP
                        WHERE file_hash = ? AND page_number = ? AND paragraph_index = ?
                    ''', (original_text, json.dumps(bbox) if bbox else None,
                          file_hash, page_number, paragraph_index))
                    added_count += 1
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
        
        return added_count
    
    def update_paragraph_translation(self, file_hash: str, page_number: int,
                                    paragraph_index: int, translation_text: str):
        """
        更新段落翻译
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            paragraph_index: 段落索引
            translation_text: 翻译文本
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pdf_paragraphs 
            SET translation_text = ?, updated_time = CURRENT_TIMESTAMP
            WHERE file_hash = ? AND page_number = ? AND paragraph_index = ?
        ''', (translation_text, file_hash, page_number, paragraph_index))
        conn.commit()
        conn.close()
    
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
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT translation_text FROM pdf_paragraphs 
            WHERE file_hash = ? AND page_number = ? AND paragraph_index = ?
        ''', (file_hash, page_number, paragraph_index))
        row = cursor.fetchone()
        conn.close()
        
        if row and row['translation_text']:
            return row['translation_text']
        return None
    
    def get_paragraphs(self, file_hash: str, page_number: int = None) -> List[Dict]:
        """
        获取段落列表
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码（可选，如果不指定则返回所有页）
            
        Returns:
            段落列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if page_number is not None:
            cursor.execute('''
                SELECT * FROM pdf_paragraphs 
                WHERE file_hash = ? AND page_number = ?
                ORDER BY paragraph_index
            ''', (file_hash, page_number))
        else:
            cursor.execute('''
                SELECT * FROM pdf_paragraphs 
                WHERE file_hash = ?
                ORDER BY page_number, paragraph_index
            ''', (file_hash,))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get('bbox'):
                result['bbox'] = json.loads(result['bbox'])
            results.append(result)
        return results
    
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
        paragraphs = self.get_paragraphs(file_hash, page_number)
        
        if not paragraphs:
            return ""
        
        if include_translation:
            # 包含原文和译文
            text_parts = []
            for para in paragraphs:
                text_parts.append(para['original_text'])
                if para.get('translation_text'):
                    text_parts.append(f"[译文] {para['translation_text']}")
            return '\n\n'.join(text_parts)
        else:
            # 仅原文
            return '\n\n'.join(para['original_text'] for para in paragraphs)
    
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
        paragraphs = self.get_paragraphs(file_hash, page_number)
        
        if not paragraphs:
            return {
                'page_number': page_number,
                'original_text': '',
                'translation_text': ''
            }
        
        original_text = '\n\n'.join(para['original_text'] for para in paragraphs)
        
        translation_text = ''
        if include_translation:
            translations = [
                para['translation_text'] 
                for para in paragraphs 
                if para.get('translation_text')
            ]
            translation_text = '\n\n'.join(translations)
        
        return {
            'page_number': page_number,
            'original_text': original_text,
            'translation_text': translation_text,
            'paragraph_count': len(paragraphs),
            'translated_count': sum(1 for p in paragraphs if p.get('translation_text'))
        }
    
    # ==================== 图片操作 TODO ====================
    
    def add_image(self, file_hash: str, page_number: int, image_index: int,
                  image_path: str, image_format: str = None,
                  width: int = None, height: int = None,
                  file_size: int = None, bbox: Dict = None) -> int:
        """
        添加图片记录
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码
            image_index: 图片索引
            image_path: 图片文件路径（相对路径）
            image_format: 图片格式（png, jpg等）
            width: 图片宽度
            height: 图片高度
            file_size: 文件大小
            bbox: 边界框坐标
            
        Returns:
            图片ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO pdf_images 
                (file_hash, page_number, image_index, image_path, 
                 image_format, width, height, file_size, bbox)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (file_hash, page_number, image_index, image_path,
                  image_format, width, height, file_size,
                  json.dumps(bbox) if bbox else None))
            conn.commit()
            image_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            # 图片已存在，更新路径
            cursor.execute('''
                UPDATE pdf_images 
                SET image_path = ?, image_format = ?, width = ?, height = ?,
                    file_size = ?, bbox = ?
                WHERE file_hash = ? AND page_number = ? AND image_index = ?
            ''', (image_path, image_format, width, height, file_size,
                  json.dumps(bbox) if bbox else None,
                  file_hash, page_number, image_index))
            conn.commit()
            cursor.execute('''
                SELECT id FROM pdf_images 
                WHERE file_hash = ? AND page_number = ? AND image_index = ?
            ''', (file_hash, page_number, image_index))
            image_id = cursor.fetchone()[0]
        finally:
            conn.close()
        
        return image_id
    
    def get_images(self, file_hash: str, page_number: int = None) -> List[Dict]:
        """
        获取图片列表
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码（可选，如果不指定则返回所有页）
            
        Returns:
            图片列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if page_number is not None:
            cursor.execute('''
                SELECT * FROM pdf_images 
                WHERE file_hash = ? AND page_number = ?
                ORDER BY image_index
            ''', (file_hash, page_number))
        else:
            cursor.execute('''
                SELECT * FROM pdf_images 
                WHERE file_hash = ?
                ORDER BY page_number, image_index
            ''', (file_hash,))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get('bbox'):
                result['bbox'] = json.loads(result['bbox'])
            results.append(result)
        return results
    
    def delete_images(self, file_hash: str, page_number: int = None):
        """
        删除图片记录
        
        Args:
            file_hash: 文件哈希值
            page_number: 页码（可选，如果不指定则删除所有页的图片）
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if page_number is not None:
            cursor.execute('''
                DELETE FROM pdf_images 
                WHERE file_hash = ? AND page_number = ?
            ''', (file_hash, page_number))
        else:
            cursor.execute('''
                DELETE FROM pdf_images 
                WHERE file_hash = ?
            ''', (file_hash,))
        
        conn.commit()
        conn.close()
    
    # ==================== 笔记操作 TODO ====================
    
    def add_note(self, file_hash: str, user_id: str, note_content: str,
                page_number: int = None, note_type: str = 'general',
                color: str = '#FFEB3B', position: Dict = None) -> int:
        """
        添加笔记
        
        Args:
            file_hash: 文件哈希值
            user_id: 用户ID
            note_content: 笔记内容
            page_number: 页码
            note_type: 笔记类型
            color: 颜色
            position: 位置信息
            
        Returns:
            笔记ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_notes 
            (file_hash, user_id, page_number, note_content, note_type, color, position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (file_hash, user_id, page_number, note_content, note_type, color,
              json.dumps(position) if position else None))
        conn.commit()
        note_id = cursor.lastrowid
        conn.close()
        return note_id
    
    def update_note(self, note_id: int, note_content: str, color: str = None):
        """
        更新笔记
        
        Args:
            note_id: 笔记ID
            note_content: 笔记内容
            color: 颜色
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if color:
            cursor.execute('''
                UPDATE user_notes 
                SET note_content = ?, color = ?, updated_time = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (note_content, color, note_id))
        else:
            cursor.execute('''
                UPDATE user_notes 
                SET note_content = ?, updated_time = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (note_content, note_id))
        
        conn.commit()
        conn.close()
    
    def delete_note(self, note_id: int):
        """删除笔记"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_notes WHERE id = ?', (note_id,))
        conn.commit()
        conn.close()
    
    def get_notes(self, file_hash: str, user_id: str, 
                 page_number: int = None) -> List[Dict]:
        """
        获取笔记列表
        
        Args:
            file_hash: 文件哈希值
            user_id: 用户ID
            page_number: 页码（可选）
            
        Returns:
            笔记列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if page_number is not None:
            cursor.execute('''
                SELECT * FROM user_notes 
                WHERE file_hash = ? AND user_id = ? AND page_number = ?
                ORDER BY created_time DESC
            ''', (file_hash, user_id, page_number))
        else:
            cursor.execute('''
                SELECT * FROM user_notes 
                WHERE file_hash = ? AND user_id = ?
                ORDER BY page_number, created_time DESC
            ''', (file_hash, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get('position'):
                result['position'] = json.loads(result['position'])
            results.append(result)
        return results
    
    # ==================== 高亮操作 TODO ====================
    
    def add_highlight(self, file_hash: str, user_id: str, page_number: int,
                     highlighted_text: str, bbox: Dict, color: str = '#FFFF00',
                     comment: str = None) -> int:
        """
        添加高亮
        
        Args:
            file_hash: 文件哈希值
            user_id: 用户ID
            page_number: 页码
            highlighted_text: 高亮文本
            bbox: 边界框坐标
            color: 颜色
            comment: 注释
            
        Returns:
            高亮ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_highlights 
            (file_hash, user_id, page_number, highlighted_text, color, bbox, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (file_hash, user_id, page_number, highlighted_text, color,
              json.dumps(bbox), comment))
        conn.commit()
        highlight_id = cursor.lastrowid
        conn.close()
        return highlight_id
    
    def update_highlight(self, highlight_id: int, color: str = None, 
                        comment: str = None):
        """
        更新高亮
        
        Args:
            highlight_id: 高亮ID
            color: 颜色
            comment: 注释
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if color:
            updates.append('color = ?')
            params.append(color)
        if comment is not None:
            updates.append('comment = ?')
            params.append(comment)
        
        if updates:
            params.append(highlight_id)
            cursor.execute(f'''
                UPDATE user_highlights 
                SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
            conn.commit()
        
        conn.close()
    
    def delete_highlight(self, highlight_id: int):
        """删除高亮"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_highlights WHERE id = ?', (highlight_id,))
        conn.commit()
        conn.close()
    
    def get_highlights(self, file_hash: str, user_id: str,
                      page_number: int = None) -> List[Dict]:
        """
        获取高亮列表
        
        Args:
            file_hash: 文件哈希值
            user_id: 用户ID
            page_number: 页码（可选）
            
        Returns:
            高亮列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if page_number is not None:
            cursor.execute('''
                SELECT * FROM user_highlights 
                WHERE file_hash = ? AND user_id = ? AND page_number = ?
                ORDER BY created_time
            ''', (file_hash, user_id, page_number))
        else:
            cursor.execute('''
                SELECT * FROM user_highlights 
                WHERE file_hash = ? AND user_id = ?
                ORDER BY page_number, created_time
            ''', (file_hash, user_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get('bbox'):
                result['bbox'] = json.loads(result['bbox'])
            results.append(result)
        return results
    
    # ==================== 聊天记录操作 ====================
    
    def create_chat_session(self, session_id: str, user_id: str, 
                           file_hash: str = None, title: str = None) -> int:
        """
        创建聊天会话
        
        Args:
            session_id: 会话ID（UUID）
            user_id: 用户ID
            file_hash: 关联的PDF文件哈希值（可选）
            title: 会话标题（可选）
            
        Returns:
            会话数据库ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO chat_sessions 
                (session_id, user_id, file_hash, title)
                VALUES (?, ?, ?, ?)
            ''', (session_id, user_id, file_hash, title or '新对话'))
            conn.commit()
            db_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            # 会话已存在，获取ID
            cursor.execute('''
                SELECT id FROM chat_sessions WHERE session_id = ?
            ''', (session_id,))
            db_id = cursor.fetchone()[0]
        finally:
            conn.close()
        
        return db_id
    
    def add_chat_message(self, session_id: str, role: str, content: str,
                        citations: List[Dict] = None) -> int:
        """
        添加聊天消息
        
        Args:
            session_id: 会话ID
            role: 角色（user/assistant）
            content: 消息内容
            citations: 引用信息（可选）
            
        Returns:
            消息ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chat_messages 
            (session_id, role, content, citations)
            VALUES (?, ?, ?, ?)
        ''', (session_id, role, content, 
              json.dumps(citations) if citations else None))
        
        # 更新会话的更新时间
        cursor.execute('''
            UPDATE chat_sessions 
            SET updated_time = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        message_id = cursor.lastrowid
        conn.close()
        
        return message_id
    
    def get_chat_session(self, session_id: str) -> Optional[Dict]:
        """
        获取聊天会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM chat_sessions WHERE session_id = ?
        ''', (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_chat_messages(self, session_id: str) -> List[Dict]:
        """
        获取会话的所有消息
        
        Args:
            session_id: 会话ID
            
        Returns:
            消息列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM chat_messages 
            WHERE session_id = ?
            ORDER BY created_time
        ''', (session_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get('citations'):
                result['citations'] = json.loads(result['citations'])
            results.append(result)
        return results
    
    def list_chat_sessions(self, user_id: str, file_hash: str = None, limit: int = 50) -> List[Dict]:
        """
        列出用户的聊天会话

        Args:
            user_id: 用户ID
            file_hash: 可选，按 PDF 文件哈希筛选
            limit: 返回数量限制

        Returns:
            会话列表，包含消息数量
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if file_hash:
            cursor.execute('''
                SELECT
                    cs.*,
                    COUNT(cm.id) as message_count
                FROM chat_sessions cs
                LEFT JOIN chat_messages cm ON cs.session_id = cm.session_id
                WHERE cs.user_id = ? AND cs.file_hash = ?
                GROUP BY cs.session_id
                ORDER BY cs.updated_time DESC
                LIMIT ?
            ''', (user_id, file_hash, limit))
        else:
            cursor.execute('''
                SELECT
                    cs.*,
                    COUNT(cm.id) as message_count
                FROM chat_sessions cs
                LEFT JOIN chat_messages cm ON cs.session_id = cm.session_id
                WHERE cs.user_id = ?
                GROUP BY cs.session_id
                ORDER BY cs.updated_time DESC
                LIMIT ?
            ''', (user_id, limit))

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append(dict(row))
        return results
    
    def update_chat_session_title(self, session_id: str, title: str):
        """
        更新会话标题
        
        Args:
            session_id: 会话ID
            title: 新标题
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE chat_sessions 
            SET title = ?, updated_time = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (title, session_id))
        
        conn.commit()
        conn.close()
    
    def delete_chat_session(self, session_id: str) -> int:
        """
        删除聊天会话及其所有消息
        
        Args:
            session_id: 会话ID
            
        Returns:
            删除的消息数量
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 统计消息数量
        cursor.execute('''
            SELECT COUNT(*) FROM chat_messages WHERE session_id = ?
        ''', (session_id,))
        message_count = cursor.fetchone()[0]
        
        # 删除会话（级联删除会自动删除消息）
        cursor.execute('''
            DELETE FROM chat_sessions WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()
        
        return message_count
    
    def get_chat_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """
        获取聊天历史（用于上下文）
        
        Args:
            session_id: 会话ID
            limit: 最近的消息数量
            
        Returns:
            消息列表，格式化为 {role, content}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role, content FROM chat_messages 
            WHERE session_id = ?
            ORDER BY created_time DESC
            LIMIT ?
        ''', (session_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 反转顺序（从旧到新）
        messages = [{'role': row['role'], 'content': row['content']} 
                   for row in reversed(rows)]
        return messages
