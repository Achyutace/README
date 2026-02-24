"""
笔记相关路由
1. 创建笔记
2. 获取笔记列表
3. 更新笔记
4. 删除笔记
"""
import json
from flask import Blueprint, request, jsonify, current_app, g
from core.security import jwt_required

# 定义蓝图
notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')


@notes_bp.route('', methods=['POST'])
@jwt_required()
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

    pdf_id = data['pdfId']          # pdf_id == file_hash
    user_id = g.user_id
    title = data.get('title', '')
    content = data.get('content', '')
    keywords = data.get('keywords', [])

    note_service = g.note_service
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
@jwt_required()
def get_notes(pdf_id):
    """
    获取某 PDF 的所有笔记
    """
    user_id = g.user_id
    note_service = g.note_service

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


@notes_bp.route('/<int:note_id>', methods=['PUT'])
@jwt_required()
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

    # 1. 简单校验
    title = data.get('title')
    content = data.get('content')
    keywords = data.get('keywords')

    if title is None and content is None and keywords is None:
        return jsonify({'error': 'At least one field (title, content, keywords) must be provided'}), 400

    # 2. 调用 Service 更新
    note_service = g.note_service
    note_service.update_note_content(
        note_id=note_id,
        title=title,
        content=content,
        keywords=keywords
    )

    return jsonify({
        'success': True,
        'message': 'Note updated'
    })


@notes_bp.route('/<int:note_id>', methods=['DELETE'])
@jwt_required()
def delete_note(note_id):
    """删除笔记"""
    note_service = g.note_service
    success = note_service.delete_note(note_id)

    if not success:
        return jsonify({'error': 'Note not found or delete failed'}), 404

    return jsonify({
        'success': True,
        'message': 'Note deleted'
    })