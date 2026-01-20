"""
RAG Service - 为当前阅读的单篇论文提供上下文检索
专注于支持 AI Chat 对当前文档的理解和问答

设计思路：
1. RAGService 读取缓存数据，计算向量并提供智能检索
2. 向量数据按需计算，缓存在内存中（当前文档）

预期的缓存文件结构：
backend/cache/{pdf_id}/
  ├── paragraphs.json    # PdfService.parse_paragraphs() 输出
  │   示例: [{"id": "pdf_chk_xxx_1_0", "page": 1, "content": "Abstract...", "bbox": {...}}, ...]
  ├── images_meta.json   # PdfService.get_images_list() 输出
  │   示例: [{"id": "xxx__xref__123", "page": 2, "bbox": {...}}, ...]
  └── metadata.json      # PdfService.get_info() 输出
      示例: {"id": "xxx", "pageCount": 10, "metadata": {"title": "...", ...}}
"""

import re
from typing import List, Dict, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


class PaperChunk:
    """论文文本块"""
    def __init__(self, content: str, section: str, page: int, chunk_index: int):
        self.content = content
        self.section = section
        self.page = page
        self.chunk_index = chunk_index
        self.embedding = None  


class SectionClassifier:
    """章节分类器 - 基于段落文本识别章节类型"""
    
    SECTION_PATTERNS = {
        'abstract': r'^(abstract|summary)\s*$',
        'introduction': r'^(1\.?\s*)?(introduction|background)\s*$',
        'related_work': r'^(\d+\.?\s*)?(related work|literature review)\s*$',
        'method': r'^(\d+\.?\s*)?(method|methodology|approach|model)\s*$',
        'experiments': r'^(\d+\.?\s*)?(experiment|evaluation|results)\s*$',
        'conclusion': r'^(\d+\.?\s*)?(conclusion|discussion|future work)\s*$',
        'references': r'^(reference|bibliography)\s*$',
    }
    
    @classmethod
    def classify_paragraph(cls, paragraph: Dict) -> str:
        """
        分类段落所属章节
        
        Args:
            paragraph: PdfService.parse_paragraphs() 返回的段落字典
            
        Returns:
            章节类型 ('abstract', 'introduction', 'method', 等) 或 'content'
        """
        text = paragraph['content']
        first_line = text.split('\n')[0].strip().lower()
        
        # 检查是否匹配章节标题模式
        for section_type, pattern in cls.SECTION_PATTERNS.items():
            if re.match(pattern, first_line, re.IGNORECASE):
                return section_type
        
        return 'content'  # 默认为正文内容


class RAGService:
    """
    RAG 服务
    """
    
    def __init__(self, cache_dir: str = "./backend/cache", 
                 chunk_size: int = 800, 
                 chunk_overlap: int = 100):
        """
        Args:
            cache_dir: 缓存根目录
            chunk_size: 文本块大小（用于进一步切分长段落）
            chunk_overlap: 块之间的重叠
        """
        self.cache_dir = cache_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 文本分割器（用于切分超长段落）
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
        )
        
        # 嵌入模型（按需初始化）
        self.embeddings = None
        
        # 当前加载的文档数据（内存缓存）
        self.current_pdf_id = None
        self.current_chunks = []   # 处理后的文本块
        self.chunks_embeddings = None  # 文本块的向量表示
        self.current_metadata = None  # 论文元数据
    
    
    def load_paper(self, pdf_id: str) -> Dict:
        """
        从缓存加载论文数据到内存
        
        Args:
            pdf_id: PDF 文件ID（对应 cache 子目录名）
            
        Returns:
            {
                'success': bool,
                'metadata': {...},
                'chunks_count': int,
                'paragraphs_count': int
            }
        """
        import json
        import os
        
        try:
            cache_path = os.path.join(self.cache_dir, pdf_id)
            
            # 1. 读取缓存的段落数据
            paragraphs_file = os.path.join(cache_path, "paragraphs.json")
            if not os.path.exists(paragraphs_file):
                return {
                    'success': False,
                    'error': f'Cache not found: {paragraphs_file}. Please preprocess PDF first.'
                }
            
            with open(paragraphs_file, 'r', encoding='utf-8') as f:
                paragraphs = json.load(f)
            
            # 2. 读取元数据
            metadata_file = os.path.join(cache_path, "metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    self.current_metadata = json.load(f)
            else:
                self.current_metadata = {'id': pdf_id}
            
            # 3. 创建文本块
            chunks = []
            chunk_index = 0
            
            for para in paragraphs:
                para_content = para['content']
                para_page = para['page']
                
                # 对超长段落进行切分
                if len(para_content) > self.chunk_size:
                    sub_chunks = self.text_splitter.split_text(para_content)
                else:
                    sub_chunks = [para_content]
                
                for chunk_text in sub_chunks:
                    # 使用轻量级分类器识别章节类型
                    section_type = SectionClassifier.classify_paragraph(para)
                    
                    chunk = PaperChunk(
                        content=chunk_text,
                        section=section_type,
                        page=para_page,
                        chunk_index=chunk_index
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            
            # 4. 保存到内存
            self.current_pdf_id = pdf_id
            self.current_chunks = chunks
            self.chunks_embeddings = None  # 重置向量缓存
            
            return {
                'success': True,
                'metadata': self.current_metadata,
                'chunks_count': len(chunks),
                'paragraphs_count': len(paragraphs)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _ensure_embeddings(self):
        """确保嵌入模型已初始化"""
        if self.embeddings is None:
            self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    def _compute_chunk_embeddings(self):
        """计算所有文本块的向量表示"""
        if self.chunks_embeddings is not None:
            return  # 已经计算过
        
        if not self.current_chunks:
            return
        
        self._ensure_embeddings()
        
        # 批量计算嵌入
        texts = [chunk.content for chunk in self.current_chunks]
        embeddings = self.embeddings.embed_documents(texts)
        self.chunks_embeddings = np.array(embeddings)
        
        # 保存到每个 chunk
        for i, chunk in enumerate(self.current_chunks):
            chunk.embedding = embeddings[i]
    
    def retrieve(self, query: str, top_k: int = 3, 
                 section_filter: Optional[str] = None,
                 page_filter: Optional[int] = None) -> List[Dict]:
        """
        检索相关上下文
        
        Args:
            query: 用户查询或选中的文本
            top_k: 返回结果数量
            section_filter: 章节过滤（如 'method', 'introduction'）
            page_filter: 页码过滤
            
        Returns:
            [
                {
                    'content': '检索到的文本块',
                    'section': '章节类型',
                    'page': 页码,
                    'score': 相似度分数
                },
                ...
            ]
        """
        if not self.current_chunks:
            return []
        
        try:
            # 1. 计算文本块向量（如果还没计算）
            self._compute_chunk_embeddings()
            
            # 2. 计算查询向量
            self._ensure_embeddings()
            query_embedding = np.array(self.embeddings.embed_query(query)).reshape(1, -1)
            
            # 3. 计算相似度
            similarities = cosine_similarity(query_embedding, self.chunks_embeddings)[0]
            
            # 4. 应用过滤
            filtered_indices = []
            for i, chunk in enumerate(self.current_chunks):
                if section_filter and chunk.section != section_filter:
                    continue
                if page_filter and chunk.page != page_filter:
                    continue
                filtered_indices.append(i)
            
            # 5. 排序并获取 top_k
            if not filtered_indices:
                filtered_indices = list(range(len(self.current_chunks)))
            
            filtered_similarities = [(i, similarities[i]) for i in filtered_indices]
            filtered_similarities.sort(key=lambda x: x[1], reverse=True)
            top_indices = [i for i, _ in filtered_similarities[:top_k]]
            
            # 6. 构造返回结果
            results = []
            for idx in top_indices:
                chunk = self.current_chunks[idx]
                results.append({
                    'content': chunk.content,
                    'section': chunk.section,
                    'page': chunk.page,
                    'chunk_index': chunk.chunk_index,
                    'score': float(similarities[idx])
                })
            
            return results
            
        except Exception as e:
            print(f"Retrieval error: {e}")
            return []
    
    
    def get_section_content(self, section_type: str) -> Optional[str]:
        """
        获取特定章节的完整内容
        
        Args:
            section_type: 章节类型 (如 'abstract', 'introduction', 'method')
            
        Returns:
            章节内容文本，如果不存在返回 None
        """
        if not self.current_chunks:
            return None
        
        # 收集该章节的所有块
        section_chunks = [
            chunk for chunk in self.current_chunks 
            if chunk.section == section_type
        ]
        
        if not section_chunks:
            return None
        
        # 按顺序拼接
        section_chunks.sort(key=lambda x: x.chunk_index)
        return "\n\n".join(chunk.content for chunk in section_chunks)
    
    def get_page_context(self, page_number: int, window: int = 0) -> str:
        """
        获取特定页面的上下文
        
        Args:
            page_number: 页码
            window: 前后扩展的页数
            
        Returns:
            页面内容文本
        """
        if not self.current_chunks:
            return ""
        
        # 获取目标页面范围的所有块
        start_page = max(1, page_number - window)
        end_page = page_number + window
        
        relevant_chunks = [
            chunk for chunk in self.current_chunks
            if start_page <= chunk.page <= end_page
        ]
        
        relevant_chunks.sort(key=lambda x: (x.page, x.chunk_index))
        
        return "\n\n".join(chunk.content for chunk in relevant_chunks)
    
    
    def get_metadata(self) -> Optional[Dict]:
        """获取当前论文的元数据"""
        return self.current_metadata
    
    def get_full_text(self) -> str:
        """
        获取当前论文的全文（从所有chunks拼接）
        
        Returns:
            完整文本内容
        """
        if not self.current_chunks:
            return ""
        
        # 按顺序拼接所有块
        sorted_chunks = sorted(self.current_chunks, key=lambda x: (x.page, x.chunk_index))
        return "\n\n".join(chunk.content for chunk in sorted_chunks)
    
    def clear(self):
        """清空当前加载的文档"""
        self.current_pdf_id = None
        self.current_chunks = []
        self.chunks_embeddings = None
        self.current_metadata = None
