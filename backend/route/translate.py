"""
翻译路由
1. 段落翻译 (按需触发, 带缓存)
2. 选中文本翻译 (带上下文)
"""
from flask import Blueprint, request, jsonify, current_app, g
from route.utils import require_auth, parse_paragraph_id
from utils.pdf_engine import make_paragraph_id

# 定义蓝图
translate_bp = Blueprint('translate', __name__, url_prefix='/api/translate')

# ==================== 路由接口 ====================

@translate_bp.route('/paragraph', methods=['POST'])
@require_auth
def translate_paragraph():
    """
    翻译段落 (按需触发)
    前端发送: { "pdfId": "...", "paragraphId": "..." }
    后端负责: 解析ID -> 从 DB 找原文 -> 翻译 -> 存库
    """
    data = request.get_json()

    # 1. 参数校验
    if not data or 'pdfId' not in data or 'paragraphId' not in data:
        return jsonify({'error': 'Missing pdfId or paragraphId'}), 400

    pdf_id = data['pdfId']          # pdf_id == file_hash
    paragraph_id = data['paragraphId']
    force = data.get('force', False)

    try:
        # 2. 解析段落 ID → (page, index)
        page, index = parse_paragraph_id(paragraph_id)
        if page is None or index is None:
            return jsonify({'error': 'Invalid paragraphId format'}), 400

        # 3. 从 paper_service (DB) 获取原文
        pdf_service = g.pdf_service
        paragraph_data = pdf_service.get_paragraph(pdf_id, page_number=page, paragraph_index=index)
        original_text = paragraph_data.get('text', '').strip() if paragraph_data else ''
        if not original_text:
            return jsonify({'error': 'Original text not found for this paragraph'}), 404

        # 4. 调用 translate_service (内部处理缓存 + LLM + 存库)
        translate_service = current_app.translate_service
        result = translate_service.translate_paragraph(
            file_hash=pdf_id,
            page_number=page,
            paragraph_index=index,
            original_text=original_text,
            force=force
        )

        return jsonify({
            'success': True,
            'translation': result['translation'],
            'cached': result.get('cached', False),
            'paragraphId': paragraph_id
        })

    except Exception as e:
        current_app.logger.error(f"Translation error: {e}")
        return jsonify({'error': str(e)}), 500


@translate_bp.route('/page/<pdf_id>/<int:page_number>', methods=['GET'])
@require_auth
def get_page_translations(pdf_id, page_number):
    """
    获取某页的所有历史翻译

    场景: 用户刷新页面后, 前端批量获取并缓存之前翻译过的段落
    """
    try:
        translate_service = current_app.translate_service
        page_trans = translate_service.get_page_translations(pdf_id, page_number)

        return jsonify({
            'pdfId': pdf_id,
            'page': page_number,
            'translations': page_trans   # { "paragraphId": "翻译文本", ... }
        })

    except Exception as e:
        current_app.logger.error(f"Get page translations error: {e}")
        return jsonify({'error': str(e)}), 500


@translate_bp.route('/text', methods=['POST'])
@require_auth
def translate_text():
    """
    翻译选中的词句（带上下文）

    前端发送: { "text": "选中的文本", "pdfId": "..." }
    后端从 DB 获取前几段文本作为上下文, 帮助 LLM 更准确地翻译
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
        # 2. 获取上下文 (如果提供了 pdfId)
        context = None
        if pdf_id:
            context = translate_service_build_context(pdf_id, context_paragraphs)

        # 3. 调用 translate_service
        translate_service = current_app.translate_service
        result = translate_service.translate_text(text=text, context=context)

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


# ==================== 内部辅助 ====================

def translate_service_build_context(pdf_id: str, max_paragraphs: int = 3) -> str:
    """
    从 paper_service 获取前 N 段原文, 拼接为上下文字符串
    """
    try:
        pdf_service = g.pdf_service
        paragraph_data = pdf_service.get_paragraph(pdf_id)
        blocks = paragraph_data.get('blocks', []) if paragraph_data else []
        if blocks:
            context_parts = [b['text'] for b in blocks[:max_paragraphs]]
            return '\n\n'.join(context_parts)
    except Exception as e:
        current_app.logger.warning(f"Failed to build context for {pdf_id}: {e}")
    return None