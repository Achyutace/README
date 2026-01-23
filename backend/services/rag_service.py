"""
RAG Service - 为单篇论文提供上下文检索
"""
import os
import re
import hashlib
from typing import List, Dict, Optional

from config import settings

# 禁用 ChromaDB 遥测以避免错误
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

try:
    from langchain_openai import OpenAIEmbeddings
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from langchain_community.vectorstores import Chroma
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False  

class RAGService:
    """
    RAG 服务

    - index_paper: 索引论文（从PDF提取文本并存储）
    - store_chunks: 存储文本块到向量库
    - retrieve: 根据查询检索相关文本
    - delete_paper: 删除论文向量数据
    - check_exists: 检查论文是否已存储
    - get_collection_stats: 获取统计信息
    - calculate_file_hash: 计算文件哈希值
    """
    
    def __init__(self, 
                 chroma_dir: str = "./storage/chroma_db",
                 api_base: str = None):
        """
        Args:
            chroma_dir: Chroma 数据库目录
            api_base: OpenAI API 基础 URL (可选,例如使用代理或其他兼容服务)
        """
        self.chroma_dir = chroma_dir
        
        # 嵌入模型
        if HAS_OPENAI and settings.has_openai_key:
            embedding_kwargs = {
                "model": "text-embedding-3-small"
            }
            if api_base or settings.openai.api_base:
                embedding_kwargs["openai_api_base"] = api_base or settings.openai.api_base

            self.embeddings = OpenAIEmbeddings(
                api_key=settings.openai.api_key,
                **embedding_kwargs
            )
            self.has_embeddings = True
        else:
            self.embeddings = None
            self.has_embeddings = False
            print("Warning: OpenAI embeddings not available. RAG will use demo mode.")
        
        # 确保 Chroma 目录存在
        os.makedirs(chroma_dir, exist_ok=True)
        
        # 内存缓存（用于 demo 模式或备份）
        self._paper_cache: Dict[str, Dict] = {}
    
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
    
    def index_paper(self, pdf_path: str, paper_id: str, user_id: str = "default") -> Dict:
        """
        索引论文 - 从 PDF 提取文本并存储到向量库
        
        Args:
            pdf_path: PDF 文件路径
            paper_id: 论文 ID
            user_id: 用户 ID
            
        Returns:
            {
                'success': bool,
                'message': str,
                'chunks_created': int,
                'file_hash': str
            }
        """
        try:
            # 计算文件哈希
            file_hash = self.calculate_file_hash(pdf_path)
            
            # 从 PDF 提取文本块
            chunks = self._extract_chunks_from_pdf(pdf_path)
            
            if not chunks:
                return {
                    'success': False,
                    'message': 'Failed to extract text from PDF',
                    'chunks_created': 0,
                    'file_hash': file_hash
                }
            
            # 存储到向量库
            result = self.store_chunks(file_hash, chunks)
            
            # 缓存元数据
            self._paper_cache[paper_id] = {
                'file_hash': file_hash,
                'user_id': user_id,
                'chunks_count': len(chunks)
            }
            
            return {
                'success': result['success'],
                'message': result['message'],
                'chunks_created': result.get('chunks_count', 0),
                'file_hash': file_hash
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error indexing paper: {str(e)}',
                'chunks_created': 0,
                'file_hash': ''
            }
    
    def _extract_chunks_from_pdf(self, pdf_path: str, chunk_size: int = 500) -> List[Dict]:
        """
        从 PDF 提取文本块
        
        Args:
            pdf_path: PDF 文件路径
            chunk_size: 每个块的大约字符数
            
        Returns:
            文本块列表
        """
        chunks = []
        
        if HAS_FITZ:
            try:
                doc = fitz.open(pdf_path)
                for page_num, page in enumerate(doc, 1):
                    text = page.get_text()
                    if not text.strip():
                        continue
                    
                    # 按段落分割
                    paragraphs = text.split('\n\n')
                    current_chunk = ""
                    current_section = "content"
                    
                    for para in paragraphs:
                        para = para.strip()
                        if not para:
                            continue
                        
                        # 检测章节标题
                        if self._is_section_header(para):
                            if current_chunk:
                                chunks.append({
                                    'content': current_chunk,
                                    'page': page_num,
                                    'section': current_section
                                })
                                current_chunk = ""
                            current_section = para.lower()
                        
                        current_chunk += para + "\n\n"
                        
                        # 如果块足够大，创建新块
                        if len(current_chunk) >= chunk_size:
                            chunks.append({
                                'content': current_chunk.strip(),
                                'page': page_num,
                                'section': current_section
                            })
                            current_chunk = ""
                    
                    # 处理剩余内容
                    if current_chunk.strip():
                        chunks.append({
                            'content': current_chunk.strip(),
                            'page': page_num,
                            'section': current_section
                        })
                
                doc.close()
            except Exception as e:
                print(f"Error extracting PDF with PyMuPDF: {e}")
        
        return chunks
    
    def _is_section_header(self, text: str) -> bool:
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
    
    def get_collection_stats(self, user_id: str = "default") -> Dict:
        """
        获取知识库统计信息
        
        Args:
            user_id: 用户 ID
            
        Returns:
            {
                'collection_name': str,
                'total_chunks': int,
                'papers_indexed': int
            }
        """
        try:
            # 统计缓存中的论文
            papers_count = len([p for p in self._paper_cache.values() 
                              if p.get('user_id') == user_id or user_id == 'default'])
            
            total_chunks = sum(p.get('chunks_count', 0) 
                             for p in self._paper_cache.values()
                             if p.get('user_id') == user_id or user_id == 'default')
            
            return {
                'collection_name': f'user_{user_id}',
                'total_chunks': total_chunks,
                'papers_indexed': papers_count
            }
        except Exception as e:
            return {
                'collection_name': f'user_{user_id}',
                'total_chunks': 0,
                'papers_indexed': 0,
                'error': str(e)
            }
    
    def store_chunks(self, 
                     file_hash: str, 
                     chunks: List[Dict]) -> Dict:
        """
        存储文本块到向量库
        
        Args:
            file_hash: PDF 文件哈希值
            chunks: 文本块列表，每个元素格式：
                {
                    'content': str,      # 文本内容（必需）
                    'page': int,         # 页码（必需）
                    'section': str,      # 章节类型（可选，默认 'content'）
                    'metadata': Dict     # 其他元数据（可选）
                }
        
        Returns:
            {
                'success': bool,
                'message': str,
                'chunks_count': int
            }
        """
        try:
            if not chunks:
                return {
                    'success': False,
                    'message': 'No chunks provided'
                }
            
            # 如果没有 embeddings，使用 demo 模式
            if not self.has_embeddings or not HAS_CHROMA:
                return {
                    'success': True,
                    'message': f'Demo mode: {len(chunks)} chunks cached (not persisted)',
                    'chunks_count': len(chunks)
                }
            
            # 准备数据
            texts = []
            metadatas = []
            ids = []
            
            for i, chunk in enumerate(chunks):
                texts.append(chunk['content'])
                
                # 构建元数据
                meta = {
                    'file_hash': file_hash,  # 使用 file_hash 
                    'page': chunk.get('page', 0),
                    'section': chunk.get('section', 'content'),
                    'chunk_index': i
                }
                # 合并额外的元数据
                if 'metadata' in chunk:
                    meta.update(chunk['metadata'])
                
                metadatas.append(meta)
                ids.append(f"{file_hash}_chunk_{i}")
            
            # 先删除旧数据
            self._delete_from_chroma(file_hash)
            
            # 存储到 Chroma
            vectorstore = Chroma(
                collection_name=f"paper_{file_hash[:16]}",  # 使用前16位避免名称过长
                embedding_function=self.embeddings,
                persist_directory=self.chroma_dir
            )
            
            vectorstore.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=ids
            )
            
            return {
                'success': True,
                'message': f'Successfully stored {len(chunks)} chunks for {file_hash}',
                'chunks_count': len(chunks)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error storing chunks: {str(e)}',
                'chunks_count': 0
            }
    
    
    def retrieve(self, 
                 query: str,
                 file_hash: str = None,
                 user_id: str = None,
                 top_k: int = 4,
                 filters: Optional[Dict] = None) -> List[Dict]:
        """
        根据查询检索相关文本
        
        Args:
            query: 用户查询文本
            file_hash: PDF 文件哈希值（可选，如果不提供则根据 user_id 检索）
            user_id: 用户 ID（可选，用于查找关联的论文）
            top_k: 返回结果数量
            filters: 过滤条件，例如 {'section': 'method', 'page': 5}
            
        Returns:
            [
                {
                    'content': '检索到的文本块',
                    'parent_content': '父级内容（完整块）',
                    'page': 页码,
                    'section': 章节类型,
                    'chunk_index': 块索引,
                    'score': 相似度分数 (0-1),
                    'metadata': {...}
                },
                ...
            ]
        """
        # 如果没有 embeddings，使用 demo 模式
        if not self.has_embeddings or not HAS_CHROMA:
            return self._demo_retrieve(query, user_id, top_k)
        
        # 确定要检索的文件哈希列表
        file_hashes = []
        if file_hash:
            file_hashes = [file_hash]
        elif user_id:
            # 根据 user_id 查找关联的论文
            file_hashes = [p['file_hash'] for p in self._paper_cache.values() 
                         if p.get('user_id') == user_id]
        
        if not file_hashes:
            return self._demo_retrieve(query, user_id, top_k)
        
        all_results = []
        
        for fh in file_hashes:
            try:
                vectorstore = Chroma(
                    collection_name=f"paper_{fh[:16]}",
                    embedding_function=self.embeddings,
                    persist_directory=self.chroma_dir
                )
                
                # 构建过滤条件
                where_filter = {'file_hash': fh}
                if filters:
                    where_filter.update(filters)
                
                # 检索
                results = vectorstore.similarity_search_with_score(
                    query=query,
                    k=top_k,
                    filter=where_filter if len(where_filter) > 1 else None
                )
                
                # 格式化结果
                for doc, score in results:
                    all_results.append({
                        'content': doc.page_content,
                        'parent_content': doc.page_content,  # 兼容 agent_service
                        'page': doc.metadata.get('page', 0),
                        'section': doc.metadata.get('section', 'content'),
                        'chunk_index': doc.metadata.get('chunk_index', 0),
                        'score': float(1 - score),
                        'metadata': doc.metadata
                    })
                
            except Exception as e:
                print(f"Retrieval error for {fh}: {e}")
                continue
        
        # 按分数排序，返回 top_k
        all_results.sort(key=lambda x: x['score'], reverse=True)
        return all_results[:top_k]
    
    def _demo_retrieve(self, query: str, user_id: str = None, top_k: int = 4) -> List[Dict]:
        """Demo 模式的检索"""
        # 返回模拟结果
        return [
            {
                'content': f'这是与查询 "{query[:50]}..." 相关的本地文档内容片段。',
                'parent_content': f'这是与查询 "{query[:50]}..." 相关的本地文档完整内容。在实际使用中，这里会显示从 PDF 中检索到的相关段落。',
                'page': 1,
                'section': 'content',
                'chunk_index': 0,
                'score': 0.85,
                'metadata': {'file_hash': 'demo', 'page': 1, 'section': 'content'}
            }
        ]
    
    
    def delete_paper(self, paper_id_or_hash: str, user_id: str = None) -> bool:
        """
        删除论文的向量数据
        
        Args:
            paper_id_or_hash: 论文 ID 或文件哈希值
            user_id: 用户 ID（可选，用于验证权限）
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 尝试从缓存中获取 file_hash
            file_hash = paper_id_or_hash
            if paper_id_or_hash in self._paper_cache:
                file_hash = self._paper_cache[paper_id_or_hash].get('file_hash', paper_id_or_hash)
                # 从缓存中删除
                del self._paper_cache[paper_id_or_hash]
            
            self._delete_from_chroma(file_hash)
            return True
        except Exception as e:
            print(f"Error deleting paper: {e}")
            return False
    
    
    def check_exists(self, file_hash: str) -> bool:
        """
        检查论文是否已存储在向量库中
        
        Args:
            file_hash: PDF 文件哈希值
            
        Returns:
            True if exists, False otherwise
        """
        if not self.has_embeddings or not HAS_CHROMA:
            return False
            
        try:
            vectorstore = Chroma(
                collection_name=f"paper_{file_hash[:16]}",
                embedding_function=self.embeddings,
                persist_directory=self.chroma_dir
            )
            collection = vectorstore._collection
            return collection.count() > 0
        except:
            return False
    
    
    def _delete_from_chroma(self, file_hash: str):
        """从 Chroma 删除指定论文的所有数据"""
        if not self.has_embeddings or not HAS_CHROMA:
            return
            
        try:
            vectorstore = Chroma(
                collection_name=f"paper_{file_hash[:16]}",
                embedding_function=self.embeddings,
                persist_directory=self.chroma_dir
            )
            
            # 删除集合
            vectorstore.delete_collection()
            
        except Exception as e:
            # 如果集合不存在，忽略错误
            pass