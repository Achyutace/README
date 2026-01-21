"""
翻译相关路由

功能：
1. 文本翻译
2. 段落翻译（带缓存）
3. 页面批量翻译
"""

from flask import Blueprint, request, jsonify, g

translate_bp = Blueprint('translate', __name__, url_prefix='/api/translate')


def init_translate_routes(db, translate_service, pdf_service_getter):
    """
    初始化翻译路由

    Args:
        db: 数据库实例
        translate_service: 翻译服务实例
        pdf_service_getter: 获取PDF服务的函数
    """

    @translate_bp.route('/text', methods=['POST'])
    def translate_text():
        """
        翻译文本

        请求体：
        {
            "text": "待翻译文本",
            "sourceLang": "en",  // 可选，默认en
            "targetLang": "zh"   // 可选，默认zh
        }

        返回：
        {
            "originalText": "原文",
            "translatedText": "译文",
            "sourceLanguage": "en",
            "targetLanguage": "zh",
            "sentences": [...]
        }
        """
        data = request.get_json()
        text = data.get('text')

        if not text:
            return jsonify({'error': 'text is required'}), 400

        source_lang = data.get('sourceLang', 'en')
        target_lang = data.get('targetLang', 'zh')

        try:
            result = translate_service.translate(text, source_lang, target_lang)
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @translate_bp.route('/paragraph', methods=['POST'])
    def translate_paragraph():
        """
        翻译段落（带缓存）

        请求体：
        {
            "pdfId": "PDF ID",
            "pageNumber": 1,
            "paragraphIndex": 0,
            "text": "段落文本",
            "force": false  // 是否强制重新翻译
        }

        返回：
        {
            "success": true,
            "translation": "译文",
            "cached": false
        }
        """
        data = request.get_json()
        pdf_id = data.get('pdfId')
        page_number = data.get('pageNumber')
        paragraph_index = data.get('paragraphIndex', 0)
        text = data.get('text')
        force = data.get('force', False)

        if not all([pdf_id, page_number is not None, text]):
            return jsonify({'error': 'pdfId, pageNumber and text are required'}), 400

        try:
            # 获取文件哈希
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            # 翻译并存储
            result = translate_service.translate_paragraph(
                file_hash=file_hash,
                page_number=page_number,
                paragraph_index=paragraph_index,
                original_text=text,
                force=force
            )

            return jsonify(result)
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @translate_bp.route('/page', methods=['POST'])
    def translate_page():
        """
        翻译整页内容

        请求体：
        {
            "pdfId": "PDF ID",
            "pageNumber": 1,
            "force": false
        }

        返回：
        {
            "success": true,
            "pageNumber": 1,
            "translations": [...],
            "total": 10,
            "translated": 10,
            "cached": 5
        }
        """
        data = request.get_json()
        pdf_id = data.get('pdfId')
        page_number = data.get('pageNumber')
        force = data.get('force', False)

        if not all([pdf_id, page_number is not None]):
            return jsonify({'error': 'pdfId and pageNumber are required'}), 400

        try:
            # 获取文件信息
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            # 获取页面段落
            paragraphs = db.get_paragraphs(file_hash, page_number)

            if not paragraphs:
                # 如果没有缓存的段落，从PDF提取
                text_result = pdf_service.extract_text(pdf_id, page_number)
                # 简单分段
                text = text_result.get('text', '')
                para_texts = [p.strip() for p in text.split('\n\n') if p.strip()]
                paragraphs = [{'index': i, 'text': t} for i, t in enumerate(para_texts)]

                # 存储段落
                for para in paragraphs:
                    db.add_paragraph(
                        file_hash=file_hash,
                        page_number=page_number,
                        paragraph_index=para['index'],
                        original_text=para['text']
                    )
            else:
                # 转换格式
                paragraphs = [{'index': p['paragraph_index'], 'text': p['original_text']}
                             for p in paragraphs]

            # 翻译
            result = translate_service.translate_page(
                file_hash=file_hash,
                page_number=page_number,
                paragraphs=paragraphs,
                force=force
            )

            return jsonify(result)
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @translate_bp.route('/batch', methods=['POST'])
    def batch_translate():
        """
        批量翻译文本

        请求体：
        {
            "texts": ["文本1", "文本2", ...]
        }

        返回：
        {
            "results": [
                {"originalText": "...", "translatedText": "..."},
                ...
            ]
        }
        """
        data = request.get_json()
        texts = data.get('texts', [])

        if not texts:
            return jsonify({'error': 'texts array is required'}), 400

        try:
            results = translate_service.batch_translate(texts)
            return jsonify({'results': results})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return translate_bp
