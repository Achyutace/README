"""
翻译
"""
import re
from flask import Blueprint, request, jsonify, current_app, g
from models.database import Database

# 定义蓝图
translate_bp = Blueprint('translate', __name__, url_prefix='/api/translate')

# ==================== 辅助工具 ====================

def get_file_hash(pdf_id: str) -> str:
    """
    通过 pdf_id 获取 file_hash
    """
    try:
        # g.pdf_service 在 app.py 的 before_request 中挂载
        filepath = g.pdf_service.get_filepath(pdf_id)
        return Database.calculate_file_hash(filepath)
    except Exception as e:
        current_app.logger.error(f"Hash calculation failed for {pdf_id}: {e}")
        return None

def parse_paragraph_id(paragraph_id: str):
    """
    从 paragraph_id 中解析出页码和索引
    假设 ID 格式为: pdf_chk_{pdf_id_prefix}_{page}_{index}
    例如: pdf_chk_a1b2c3d4_1_5 (第1页，第5个段落)
    """
    try:
        parts = paragraph_id.split('_')
        # 取最后两部分
        index = int(parts[-1])
        page = int(parts[-2])
        return page, index
    except Exception:
        return None, None

def get_original_text(pdf_id: str, target_id: str) -> str:
    """
    从 PdfService 的缓存中查找原文
    因为前端没传原文，我们需要回溯解析结果
    """
    try:
        paragraphs = g.pdf_service.parse_paragraphs(pdf_id)
        
        # 遍历查找 (如果信任 ID 里的 index，可以直接列表索引 paragraphs[index])
        for p in paragraphs:
            if p['id'] == target_id:
                return p['content']
        return None
    except Exception as e:
        current_app.logger.error(f"Fetch original text error: {e}")
        return None

# ==================== 路由接口 ====================

@translate_bp.route('/paragraph', methods=['POST'])
def translate_paragraph():
    """
    翻译段落 (按需触发)
    
    前端只需发送: { "pdfId": "...", "paragraphId": "..." }
    后端负责: 解析ID -> 找原文 -> 查库 -> (翻译) -> 存库
    """
    data = request.get_json()
    
    # 1. 参数校验
    if not data or 'pdfId' not in data or 'paragraphId' not in data:
        return jsonify({'error': 'Missing pdfId or paragraphId'}), 400

    pdf_id = data['pdfId']
    paragraph_id = data['paragraphId']
    force = data.get('force', False)

    try:
        # 2. 解析 ID 信息
        page, index = parse_paragraph_id(paragraph_id)
        if page is None or index is None:
            return jsonify({'error': 'Invalid paragraphId format'}), 400

        # 3. 获取文件哈希
        file_hash = get_file_hash(pdf_id)
        if not file_hash:
            return jsonify({'error': 'PDF file not found'}), 404

        # 4. 检查数据库缓存
        storage_service = current_app.storage_service
        translations = storage_service.get_paragraph_translations(
            file_hash, page, index
        )
        
        if translations and translations[0] and not force:
            return jsonify({
                'success': True,
                'translation': translations[0],
                'cached': True,
                'paragraphId': paragraph_id
            })

        # 5. [缓存未命中] 获取原文
        original_text = get_original_text(pdf_id, paragraph_id)
        if not original_text:
            return jsonify({'error': 'Original text not found for this paragraph'}), 404

        # 6. 调用翻译服务
        translate_service = current_app.translate_service
        
        # translate_paragraph 方法内部处理 LLM 调用和数据库存储
        result = translate_service.translate_paragraph(
            file_hash=file_hash,
            page_number=page,
            paragraph_index=index,
            original_text=original_text,
            force=force
        )

        return jsonify({
            'success': True,
            'translation': result['translation'],
            'cached': False,
            'paragraphId': paragraph_id
        })

    except Exception as e:
        current_app.logger.error(f"Translation error: {e}")
        return jsonify({'error': str(e)}), 500

@translate_bp.route('/page/<pdf_id>/<int:page_number>', methods=['GET'])
def get_page_translations(pdf_id, page_number):
    """
    获取某页的所有历史翻译
    
    场景：用户刷新页面后，前端调用此接口，批量获取并缓存之前翻译过的段落
    """
    try:
        file_hash = get_file_hash(pdf_id)
        if not file_hash:
            return jsonify({'error': 'PDF file not found'}), 404

        # 从数据库获取该页所有已翻译的段落
        storage_service = current_app.storage_service
        paragraphs = storage_service.get_paragraphs(file_hash, page_number)
        
        results = {}
        
        # 构造返回数据
        # 格式: pdf_chk_{pdf_id前8位}_{页码}_{索引}
        pdf_prefix = pdf_id[:8]
        
        for p in paragraphs:
            if p.get('translation_text'):
                # 重构 ID
                p_id = f"pdf_chk_{pdf_prefix}_{page_number}_{p['paragraph_index']}"
                results[p_id] = p['translation_text']
        
        return jsonify({
            'pdfId': pdf_id,
            'page': page_number,
            'translations': results # { "paragraphId": "翻译文本", ... }
        })

    except Exception as e:
        current_app.logger.error(f"Get page translations error: {e}")
        return jsonify({'error': str(e)}), 500

@translate_bp.route('/text', methods=['POST'])
def translate_text():
    """
    翻译选中的词句（带上下文）
    
    前端发送: { "text": "选中的文本", "pdfId": "..."  }
    后端会从数据库获取前几段文本（包含摘要）作为上下文，帮助 LLM 更准确地翻译
    
    适用场景：
    - 用户在阅读时选中某个词句需要翻译
    - 需要理解专业术语的上下文含义
    - 快速查询翻译
    """
    data = request.get_json()
    
    # 1. 参数校验
    if not data or 'text' not in data:
        return jsonify({'error': 'Missing text parameter'}), 400
    
    text = data['text']
    pdf_id = data.get('pdfId')
    context_paragraphs = data.get('contextParagraphs', 3) 
    
    if not text or not text.strip():
        return jsonify({'error': 'Text cannot be empty'}), 400
    
    try:
        # 2. 获取上下文（如果提供了 PDF ID）
        context = None
        
        if pdf_id:
            file_hash = get_file_hash(pdf_id)
            
            if file_hash:
                # 从数据库获取前 N 段作为上下文（包含摘要）
                storage_service = current_app.storage_service
                paragraphs = storage_service.get_paragraphs(file_hash)
                
                if paragraphs:
                    # 取前几段并拼接
                    context_parts = []
                    for para in paragraphs[:context_paragraphs]: 
                        context_parts.append(para['original_text'])
                    
                    context = '\n\n'.join(context_parts)
                    current_app.logger.info(f"Retrieved {len(context_parts)} paragraphs as context")
            else:
                current_app.logger.warning(f"PDF file not found for ID: {pdf_id}, will translate without context")
        
        # 3. 调用翻译服务
        translate_service = current_app.translate_service
        
        result = translate_service.translate_text(
            text=text,
            context=context
        )
        
        return jsonify({
            'success': True,
            'originalText': result['originalText'],
            'translatedText': result['translatedText'],
            'hasContext': result['hasContext'],
            'contextLength': result['contextLength']
        })
    
    except Exception as e:
        current_app.logger.error(f"Text translation error: {e}")
        return jsonify({'error': str(e)}), 500