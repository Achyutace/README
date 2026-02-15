"""
笔记相关路由
1. 创建笔记
2. 获取笔记列表
3. 更新笔记
4. 删除笔记
"""
import json
from flask import Blueprint, request, jsonify, current_app, g
from route.utils import require_auth

# 定义蓝图
notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')


@notes_bp.route('', methods=['POST'])
@require_auth
def create_note():
    """
    创建笔记

    Request Body:
    {
        "pdfId": "file_hash...",
        "content": "笔记内容（Markdown 或 JSON）",
        "keywords": ["key1", "key2"],   // 可选
        "title": "笔记标题"              // 可选
    }
    """
    data = request.get_json()

    if not data or not data.get('pdfId'):
        return jsonify({'error': 'Missing pdfId'}), 400

    try:
        pdf_id = data['pdfId']          # pdf_id == file_hash
        user_id = g.user_id_str
        title = data.get('title', '')
        content = data.get('content', '')
        keywords = data.get('keywords', [])

        note_service = current_app.note_service
        note_id = note_service.add_note(
            user_id=user_id,
            file_hash=pdf_id,
            content=content,
            title=title,
            keywords=keywords
        )

        return jsonify({
            'success': True,
            'id': note_id,
            'message': 'Note created'
        })


@notes_bp.route('/<pdf_id>', methods=['GET'])
@require_auth
def get_notes(pdf_id):
    """
    获取某 PDF 的所有笔记
    """
    try:
        user_id = g.user_id_str
        note_service = current_app.note_service

        notes = note_service.get_notes(user_id=user_id, file_hash=pdf_id)

        formatted_notes = []
        for note in notes:
            formatted_notes.append({
                'id': note['id'],
                'title': note.get('title') or '',
                'content': note.get('content') or '',
                'keywords': note.get('keywords', []),
                'createdAt': note.get('created_at'),
                'updatedAt': note.get('updated_at'),
            })

        return jsonify({
            'success': True,
            'notes': formatted_notes,
            'total': len(formatted_notes)
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching notes: {e}")
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/<int:note_id>', methods=['PUT'])
@require_auth
def update_note(note_id):
    """
    更新笔记

    Request Body:
    {
        "title": "新标题",   // 可选
        "content": "新内容", // 可选
        "keywords": [...]    // 可选
    }
    """
    data = request.get_json()

    try:
        note_service = current_app.note_service
        
        # 1. 获取现有笔记
        existing_note = note_service.get_note_by_id(note_id)
        if not existing_note:
            return jsonify({'error': 'Note not found'}), 404

        # 2. 获取更新字段
        title = data.get('title')
        content = data.get('content')
        keywords = data.get('keywords')

        # 3. 校验必填项 (至少更新一项)
        if title is None and content is None and keywords is None:
            return jsonify({'error': 'At least one field (title, content, keywords) must be provided'}), 400

        # 4. 构建新的内容
        new_content_str = None
        if title is not None or content is not None:
            # 解析现有内容
            current_raw = existing_note.content
            current_title = ""
            current_text = current_raw

            if current_raw:
                try:
                    parsed = json.loads(current_raw)
                    if isinstance(parsed, dict):
                        current_title = parsed.get('title', '')
                        current_text = parsed.get('content', '')
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # 合并
            final_title = title if title is not None else current_title
            final_content = content if content is not None else current_text

            # 如果有标题，这就得存成 JSON
            # 或者如果原来就是 JSON 格式，也要保持 JSON 格式
            if final_title:
                new_content_str = json.dumps({
                    'title': final_title,
                    'content': final_content
                })
            else:
                new_content_str = final_content

        # 5. 调用 Service 更新
        note_service.update_note_content(
            note_id=note_id,
            content=new_content_str,
            keywords=keywords
        )

        return jsonify({
            'success': True,
            'message': 'Note updated'
        })

    except Exception as e:
        current_app.logger.error(f"Error updating note: {e}")
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/<int:note_id>', methods=['DELETE'])
@require_auth
def delete_note(note_id):
    """删除笔记"""
    try:
        note_service = current_app.note_service
        success = note_service.delete_note(note_id)

        if not success:
            return jsonify({'error': 'Note not found or delete failed'}), 404

        return jsonify({
            'success': True,
            'message': 'Note deleted'
        })

    except Exception as e:
        current_app.logger.error(f"Error deleting note: {e}")
        return jsonify({'error': str(e)}), 500