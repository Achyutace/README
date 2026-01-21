"""
笔记相关路由

功能：
1. 高亮管理（增删改查）
2. 笔记管理（增删改查）
"""

from flask import Blueprint, request, jsonify, g

notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')


def init_notes_routes(db, pdf_service_getter):
    """
    初始化笔记路由

    Args:
        db: 数据库实例
        pdf_service_getter: 获取PDF服务的函数
    """

    # ==================== 高亮相关路由 ====================

    @notes_bp.route('/highlights', methods=['GET'])
    def list_highlights():
        """
        获取高亮列表

        查询参数：
        - pdfId: PDF ID（必需）
        - page: 页码（可选）

        返回：
        {
            "highlights": [
                {
                    "id": int,
                    "page_number": int,
                    "start_offset": int,
                    "end_offset": int,
                    "text": str,
                    "color": str,
                    "rects": [...],
                    "created_time": str
                },
                ...
            ]
        }
        """
        pdf_id = request.args.get('pdfId')
        page_number = request.args.get('page', type=int)

        if not pdf_id:
            return jsonify({'error': 'pdfId is required'}), 400

        try:
            # 获取文件哈希
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            # 获取高亮
            highlights = db.get_highlights(file_hash, g.user_id, page_number)

            return jsonify({'highlights': highlights})
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @notes_bp.route('/highlights', methods=['POST'])
    def add_highlight():
        """
        添加高亮

        请求体：
        {
            "pdfId": "PDF ID",
            "pageNumber": 1,
            "startOffset": 0,
            "endOffset": 100,
            "text": "高亮文本",
            "color": "#FFEB3B",
            "rects": [[x0, y0, x1, y1], ...]  // 可选
        }

        返回：
        {
            "success": true,
            "id": 高亮ID
        }
        """
        data = request.get_json()
        pdf_id = data.get('pdfId')
        page_number = data.get('pageNumber')
        start_offset = data.get('startOffset')
        end_offset = data.get('endOffset')
        text = data.get('text', '')
        color = data.get('color', '#FFEB3B')
        rects = data.get('rects')

        if not all([pdf_id, page_number is not None, start_offset is not None, end_offset is not None]):
            return jsonify({'error': 'pdfId, pageNumber, startOffset, endOffset are required'}), 400

        try:
            # 获取文件哈希
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            # 添加高亮
            highlight_id = db.add_highlight(
                file_hash=file_hash,
                user_id=g.user_id,
                page_number=page_number,
                start_offset=start_offset,
                end_offset=end_offset,
                text=text,
                color=color,
                rects=rects
            )

            return jsonify({
                'success': True,
                'id': highlight_id
            })
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @notes_bp.route('/highlights/<int:highlight_id>', methods=['PUT'])
    def update_highlight(highlight_id):
        """
        更新高亮

        请求体：
        {
            "color": "#FF5722",  // 可选
            "text": "更新的文本"  // 可选
        }

        返回：
        {
            "success": true
        }
        """
        data = request.get_json()
        color = data.get('color')
        text = data.get('text')

        try:
            db.update_highlight(highlight_id, color=color, text=text)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @notes_bp.route('/highlights/<int:highlight_id>', methods=['DELETE'])
    def delete_highlight(highlight_id):
        """
        删除高亮

        返回：
        {
            "success": true
        }
        """
        try:
            db.delete_highlight(highlight_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ==================== 笔记相关路由 ====================

    @notes_bp.route('/', methods=['GET'])
    def list_notes():
        """
        获取笔记列表

        查询参数：
        - pdfId: PDF ID（必需）
        - page: 页码（可选）

        返回：
        {
            "notes": [
                {
                    "id": int,
                    "note_content": str,
                    "highlight_id": int,
                    "page_number": int,
                    "color": str,
                    "created_time": str,
                    "updated_time": str
                },
                ...
            ]
        }
        """
        pdf_id = request.args.get('pdfId')
        page_number = request.args.get('page', type=int)

        if not pdf_id:
            return jsonify({'error': 'pdfId is required'}), 400

        try:
            # 获取文件哈希
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            # 获取笔记
            notes = db.get_notes(file_hash, g.user_id, page_number)

            return jsonify({'notes': notes})
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @notes_bp.route('/', methods=['POST'])
    def add_note():
        """
        添加笔记

        请求体：
        {
            "pdfId": "PDF ID",
            "content": "笔记内容",
            "highlightId": 关联的高亮ID（可选）,
            "pageNumber": 页码（可选）,
            "color": "#4CAF50"  // 可选
        }

        返回：
        {
            "success": true,
            "id": 笔记ID
        }
        """
        data = request.get_json()
        pdf_id = data.get('pdfId')
        content = data.get('content')
        highlight_id = data.get('highlightId')
        page_number = data.get('pageNumber')
        color = data.get('color', '#4CAF50')

        if not pdf_id or not content:
            return jsonify({'error': 'pdfId and content are required'}), 400

        try:
            # 获取文件哈希
            pdf_service = pdf_service_getter(g.user_id)
            filepath = pdf_service.get_filepath(pdf_id)

            from services.rag_service import RAGService
            file_hash = RAGService.calculate_file_hash(filepath)

            # 添加笔记
            note_id = db.add_note(
                file_hash=file_hash,
                user_id=g.user_id,
                note_content=content,
                highlight_id=highlight_id,
                page_number=page_number,
                color=color
            )

            return jsonify({
                'success': True,
                'id': note_id
            })
        except FileNotFoundError:
            return jsonify({'error': 'PDF not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @notes_bp.route('/<int:note_id>', methods=['PUT'])
    def update_note(note_id):
        """
        更新笔记

        请求体：
        {
            "content": "更新的笔记内容",
            "color": "#FF5722"  // 可选
        }

        返回：
        {
            "success": true
        }
        """
        data = request.get_json()
        content = data.get('content')
        color = data.get('color')

        if not content:
            return jsonify({'error': 'content is required'}), 400

        try:
            db.update_note(note_id, note_content=content, color=color)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @notes_bp.route('/<int:note_id>', methods=['DELETE'])
    def delete_note(note_id):
        """
        删除笔记

        返回：
        {
            "success": true
        }
        """
        try:
            db.delete_note(note_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return notes_bp
