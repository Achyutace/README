"""
RAG Service - 为单篇论文提供上下文检索
"""

import os
import hashlib
from typing import List, Dict, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma  

class RAGService:
    """
    RAG 服务

    - store_chunks: 存储文本块到向量库
    - retrieve: 根据查询检索相关文本
    - delete_paper: 删除论文向量数据
    - check_exists: 检查论文是否已存储
    - calculate_file_hash: 计算文件哈希值
    """
    
    def __init__(self, 
                 chroma_dir: str = "./storage/chroma_db"):
        """
        Args:
            chroma_dir: Chroma 数据库目录
        """
        self.chroma_dir = chroma_dir
        
        # 嵌入模型
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # 确保 Chroma 目录存在
        os.makedirs(chroma_dir, exist_ok=True)
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        
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
                 file_hash: str, 
                 query: str, 
                 top_k: int = 4,
                 filters: Optional[Dict] = None) -> List[Dict]:
        """
        根据查询检索相关文本
        
        Args:
            file_hash: PDF 文件哈希值
            query: 用户查询文本
            top_k: 返回结果数量
            filters: 过滤条件，例如 {'section': 'method', 'page': 5}
            
        Returns:
            [
                {
                    'content': '检索到的文本块',
                    'page': 页码,
                    'section': 章节类型,
                    'chunk_index': 块索引,
                    'score': 相似度分数 (0-1),
                    'metadata': {...}  # 其他元数据
                },
                ...
            ]
        """
        try:
            vectorstore = Chroma(
                collection_name=f"paper_{file_hash[:16]}",
                embedding_function=self.embeddings,
                persist_directory=self.chroma_dir
            )
            
            # 构建过滤条件
            where_filter = {'file_hash': file_hash}
            if filters:
                where_filter.update(filters)
            
            # 检索
            results = vectorstore.similarity_search_with_score(
                query=query,
                k=top_k,
                filter=where_filter if len(where_filter) > 1 else None
            )
            
            # 格式化结果
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    'content': doc.page_content,
                    'page': doc.metadata.get('page', 0),
                    'section': doc.metadata.get('section', 'content'),
                    'chunk_index': doc.metadata.get('chunk_index', 0),
                    'score': float(1 - score),  # Chroma 返回距离，转换为相似度
                    'metadata': doc.metadata
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"Retrieval error: {e}")
            return []
    
    
    def delete_paper(self, file_hash: str) -> Dict:
        """
        删除论文的向量数据
        
        Args:
            file_hash: PDF 文件哈希值
            
        Returns:
            {
                'success': bool,
                'message': str
            }
        """
        try:
            self._delete_from_chroma(file_hash)
            return {
                'success': True,
                'message': f'Successfully deleted paper {file_hash}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting paper: {str(e)}'
            }
    
    
    def check_exists(self, file_hash: str) -> bool:
        """
        检查论文是否已存储在向量库中
        
        Args:
            file_hash: PDF 文件哈希值
            
        Returns:
            True if exists, False otherwise
        """
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
