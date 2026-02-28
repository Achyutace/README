"""
RAG Service - 为用户论文库提供上下文检索
"""
import re
import uuid
from typing import List, Dict, Optional, Any

from core.config import settings
from core.llm_provider import resolve_llm_profile, get_langchain_embeddings
from repository.vector_repo import vector_repo
from core.logging import get_logger

logger = get_logger(__name__)

class RAGService:
    """
    RAG 服务
    
    - index_paper_from_db: 从数据库段落索引论文
    - store_chunks: 存储文本块到向量库
    - retrieve: 根据查询检索相关文本
    - delete_paper: 删除论文向量数据
    - check_exists: 检查论文是否已存储
    - get_collection_stats: 获取统计信息
    """
    
    COLLECTION_NAME = "paper_collection"

    def __init__(self):
        """
        RAG Service Initialization
        """
        # 1. 解析配置 (scene="embedding")
        self.profile = resolve_llm_profile(scene="embedding")
        
        # 嵌入模型
        if self.profile.is_available:
            self.embeddings = get_langchain_embeddings(self.profile)
            self.has_embeddings = True if self.embeddings else False
        else:
            self.embeddings = None
            self.has_embeddings = False
            logger.warning("OpenAI embeddings not available. RAG will use demo mode.")
    
    def get_collection_stats(self, user_id: Optional[uuid.UUID] = None) -> Dict:
        """
        获取知识库统计信息
        
        Args:
            user_id: 用户 ID (UUID)
            
        Returns:
            {
                'collection_name': str,
                'total_chunks': int
            }
        """
        if not vector_repo.is_available:
            return {
                'collection_name': self.COLLECTION_NAME,
                'total_chunks': 0,
                'error': 'Vector database not available'
            }
            
        try:
            filters = {'user_ids': str(user_id)} if user_id else None
            total_chunks = vector_repo.count(self.COLLECTION_NAME, filters)
            
            return {
                'collection_name': self.COLLECTION_NAME,
                'total_chunks': total_chunks,
                'user_id': str(user_id) if user_id else 'all'
            }
        except Exception as e:
            return {
                'collection_name': self.COLLECTION_NAME,
                'total_chunks': 0,
                'error': str(e)
            }
    
    def store_chunks(self, 
                     file_hash: str, 
                     chunks: List[Dict],
                     user_id: Optional[uuid.UUID] = None) -> Dict:
        """
        存储文本块到向量库
        
        Args:
            file_hash: PDF 文件哈希值
            chunks: 文本块列表
            user_id: 用户 ID
        
        Returns:
            Dict: 结果
        """
        try:
            if not chunks:
                return {
                    'success': False,
                    'message': 'No chunks provided'
                }
            
            # 如果没有 embeddings 或 vector_repo 不可用，使用 demo 模式
            if not self.has_embeddings or not vector_repo.is_available:
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
                    'chunk_index': i,
                    'page_content': chunk['content'] # 存入 payload 以便检索时获取
                }
                # 合并额外的元数据
                if 'metadata' in chunk:
                    meta.update(chunk['metadata'])
                
                metadatas.append(meta)
                
                # Qdrant requires UUIDs or unsigned integers for point IDs
                chunk_id_str = f"{file_hash}_chunk_{i}"
                chunk_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id_str))
                ids.append(chunk_uuid)
            
            user_id_str = str(user_id) if user_id else "public"
            
            # Ensure collection exists and index is built
            vector_repo.create_collection(self.COLLECTION_NAME)
            vector_repo.create_payload_index(self.COLLECTION_NAME, "file_hash")

            # 2. 生成 Embeddings
            embeddings = self.embeddings.embed_documents(texts)
            
            # Update metadata with user_ids
            for meta in metadatas:
                meta['user_ids'] = [user_id_str]
            
            # 3. 存储到 Qdrant
            vector_repo.upsert_vectors(
                collection_name=self.COLLECTION_NAME,
                vectors=embeddings,
                payloads=metadatas,
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
                 user_id: Optional[uuid.UUID] = None,
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
            List[Dict]: 检索结果
        """
        # 如果没有 embeddings 或 Repo 不可用，使用 demo 模式
        if not self.has_embeddings or not vector_repo.is_available:
            return self._demo_retrieve(query, user_id, top_k)
        
        # 生成查询向量
        try:
            query_vector = self.embeddings.embed_query(query)
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []
        
        try:
            # 构建筛选条件
            search_filters = {}
            if file_hash:
                search_filters['file_hash'] = file_hash
            if user_id:
                search_filters['user_ids'] = str(user_id)
            if filters:
                search_filters.update(filters)
            
            # 检索
            results = vector_repo.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=top_k,
                filters=search_filters
            )
            
            formatted_results = []
            # 格式化结果
            for point in results:
                payload = point.payload or {}
                content = payload.get('page_content', '')
                
                formatted_results.append({
                    'content': content,
                    'page': payload.get('page', 0),
                    'section': payload.get('section', 'content'),
                    'chunk_index': payload.get('chunk_index', 0),
                    'score': point.score,
                    'metadata': payload
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []
    
    def _demo_retrieve(self, query: str, user_id: Optional[uuid.UUID] = None, top_k: int = 4) -> List[Dict]:
        """Demo 模式的检索"""
        # 返回模拟结果
        return [
            {
                'content': f'这是与查询 "{query[:50]}..." 相关的本地文档内容片段。',
                'page': 1,
                'section': 'content',
                'chunk_index': 0,
                'score': 0.85,
                'metadata': {'file_hash': 'demo', 'page': 1, 'section': 'content'}
            }
        ]


    def retrieve_related_papers(
        self,
        query: str,
        user_id: Optional[uuid.UUID] = None,
        exclude_file_hash: Optional[str] = None,
        top_k: int = 6,
    ) -> List[Dict]:
        """
        在用户文献库的 **abstract** 段落中做相似度检索，
        返回与 query 最相关的论文列表（按论文去重，每篇只保留最高匹配）。

        适用于 Agent 跨文献库 RAG：快速定位相关论文，而非全文检索。

        Args:
            query:              查询文本
            user_id:            用户 ID（限定检索范围）
            exclude_file_hash:  需排除的 file_hash（如当前正在阅读的论文）
            top_k:              向量检索返回的最大数量（去重前）

        Returns:
            List[Dict]: 按相似度降序，每篇论文一条记录::

                {
                    "file_hash":        str,
                    "abstract_snippet": str,   # 匹配到的摘要片段
                    "score":            float, # 余弦相似度
                    "page":             int,
                    "metadata":         dict   # 完整 payload
                }
        """
        if not self.has_embeddings or not vector_repo.is_available:
            return []

        # 1. 生成查询向量
        try:
            query_vector = self.embeddings.embed_query(query)
        except Exception as e:
            logger.error(f"[retrieve_related_papers] Embedding error: {e}")
            return []

        # 2. 构建过滤条件：仅 abstract 段落 + 用户范围 + 排除当前论文
        search_filters: Dict[str, Any] = {"section": "abstract"}
        if user_id:
            search_filters["user_ids"] = str(user_id)
        if exclude_file_hash:
            search_filters["exclude_file_hash"] = exclude_file_hash

        try:
            results = vector_repo.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=top_k,
                filters=search_filters,
            )

            # 如果 abstract 检索没搜到，尝试全库搜索
            if not results:
                fallback_filters = {"user_ids": str(user_id)} if user_id else {}
                if exclude_file_hash:
                    fallback_filters["exclude_file_hash"] = exclude_file_hash
                    
                results = vector_repo.search(
                    collection_name=self.COLLECTION_NAME,
                    query_vector=query_vector,
                    limit=top_k,
                    filters=fallback_filters,
                )
        except Exception as e:
            logger.error(f"[retrieve_related_papers] search error: {e}")
            return []

        # 3. 按 file_hash 去重，只保留每篇论文的最高分结果
        best_per_paper: Dict[str, Dict] = {}
        for point in results:
            payload = point.payload or {}
            fh = payload.get("file_hash", "")

            # 同一篇论文只保留 score 最高的 chunk
            if fh in best_per_paper and point.score <= best_per_paper[fh]["score"]:
                continue

            best_per_paper[fh] = {
                "file_hash": fh,
                "abstract_snippet": payload.get("page_content", ""),
                "score": point.score,
                "page": payload.get("page", 0),
                "metadata": payload,
            }

        # 4. 按 score 降序排列返回
        return sorted(best_per_paper.values(), key=lambda x: x["score"], reverse=True)

    def delete_paper(self, file_hash: str, user_id: Optional[uuid.UUID] = None) -> bool:
        """
        取消论文关联或执行物理清理
        
        Args:
            file_hash: 文件哈希值
            user_id: 用户 ID (可选)。
                    - 若提供: 移除该用户的访问权限
                    - 若不提供: 视为维护清理。会检查是否仍有其他用户关联，若无则执行物理删除。
        """
        if not vector_repo.is_available:
            return False
            
        try:
            # 1. 获取当前向量点的元数据，检查关联用户情况
            points = vector_repo.scroll(self.COLLECTION_NAME, {'file_hash': file_hash}, limit=1)
            if not points:
                return True # 不存在
                
            current_payload = points[0].payload
            existing_users = current_payload.get('user_ids', [])
            if not isinstance(existing_users, list):
                 existing_users = [str(existing_users)] if existing_users else []

            # 2. 如果提供了 user_id，解绑
            if user_id:
                user_id_str = str(user_id)
                if user_id_str in existing_users:
                    existing_users.remove(user_id_str)
                    vector_repo.set_payload(
                        self.COLLECTION_NAME, 
                        {'user_ids': existing_users}, 
                        filters={'file_hash': file_hash}
                    )
                return True

            # 3. 如果未提供 user_id，检查是否可以物理删除
            if not existing_users:
                vector_repo.delete_vectors(self.COLLECTION_NAME, {'file_hash': file_hash})
                return True
            else:
                print(f"Skipping physical delete for {file_hash}: {len(existing_users)} users still associated.")
                return False

        except Exception as e:
            print(f"Error in delete_paper operation: {e}")
            return False
    
    
    def check_exists(self, file_hash: str, user_id: Optional[uuid.UUID] = None) -> bool:
        """
        检查论文是否已存储在向量库中
        """
        if not vector_repo.is_available:
            return False
            
        filters = {'file_hash': file_hash}
        if user_id:
            filters['user_ids'] = str(user_id)
            
        return vector_repo.count(self.COLLECTION_NAME, filters) > 0
    
    def index_paper_from_db(self, file_hash: str, paragraphs: List[Any], user_id: Optional[uuid.UUID] = None) -> Dict:
        """
        从数据库段落索引论文
        
        Args:
            file_hash: 文件哈希
            paragraphs: PdfParagraph 对象列表 (需按顺序排列)
            user_id: 用户 ID
            
        Returns:
            Dict: 索引结果
        """
        try:
            # 从段落对象创建文本块
            chunks = self._create_chunks_from_paragraphs(paragraphs)
            
            if not chunks:
                return {
                    'success': False,
                    'message': 'No text content found in paragraphs',
                    'chunks_created': 0,
                    'file_hash': file_hash
                }
            
            # 存储到向量库
            result = self.store_chunks(file_hash, chunks, user_id)
            
            return {
                'success': result['success'],
                'message': result['message'],
                'chunks_created': result.get('chunks_count', 0),
                'file_hash': file_hash
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error indexing paper from DB: {str(e)}',
                'chunks_created': 0,
                'file_hash': file_hash
            }

    def _create_chunks_from_paragraphs(self, paragraphs: List[Any], chunk_size: int = 500) -> List[Dict]:
        """
        将数据库段落对象合并为文本块
        
        Args:
            paragraphs: PdfParagraph 对象列表 (需包含 original_text, page_number)
            chunk_size: 目标块大小
        """
        chunks = []
        current_chunk_text = ""
        current_section = "content"
        # 记录当前正在构建的chunk的起始页码
        chunk_start_page = paragraphs[0].page_number if paragraphs else 1
        
        for p in paragraphs:
            text = p.original_text.strip()
            if not text:
                continue
            
            page_num = p.page_number
            
            # 检测是否为新的章节标题
            if self._is_section_header(text):
                # 遇到标题，先保存之前的累积内容（如果有）
                if current_chunk_text:
                    chunks.append({
                        'content': current_chunk_text.strip(),
                        'page': chunk_start_page, 
                        'section': current_section
                    })
                    current_chunk_text = ""
                
                # 更新当前章节名 (移除序号，保留核心标题)
                # 且标题本身不再作为chunk内容重复添加，因为它已作为元数据存在
                current_section = re.sub(r'^[\d\.\s]+', '', text).strip().lower()
                chunk_start_page = page_num
                continue
            
            # 如果当前块已经够大，则保存当前块并开始新块
            if len(current_chunk_text) >= chunk_size:
                chunks.append({
                    'content': current_chunk_text.strip(),
                    'page': chunk_start_page, 
                    'section': current_section
                })
                current_chunk_text = ""
                chunk_start_page = page_num

            # 追加当前段落文本
            if current_chunk_text:
                current_chunk_text += "\n\n" + text
            else:
                current_chunk_text = text
        
        # 处理剩余内容
        if current_chunk_text.strip():
            chunks.append({
                'content': current_chunk_text.strip(),
                'page': chunk_start_page,
                'section': current_section
            })
            
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
