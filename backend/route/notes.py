"""
笔记相关路由
1. 创建笔记
2. 获取笔记列表
3. 更新笔记
4. 删除笔记
"""
import json
from flask import Blueprint, request, jsonify, current_app, g

# 定义蓝图
notes_bp = Blueprint('notes', __name__, url_prefix='/api/notes')


def get_file_hash(pdf_id: str) -> str:
    """辅助函数：通过 PdfService 获取路径并计算 Hash"""
    try:
        filepath = g.pdf_service.get_filepath(pdf_id)
        from models.database import Database
        return Database.calculate_file_hash(filepath)
    except Exception as e:
        current_app.logger.error(f"Hash calculation failed for {pdf_id}: {e}")
        return None


@notes_bp.route('', methods=['POST'])
def create_note():
    """
    创建笔记
    
    Request Body:
    {
        "pdfId": "uuid...",
        "title": "笔记标题",
        "content": "笔记内容（Markdown）",
        "pageNumber": 1,  // 可选，关联到特定页面
        "noteType": "general",  // 可选，默认 'general'
        "color": "#FFEB3B",  // 可选，默认 '#FFEB3B'
        "position": {  // 可选，位置信息
            "x": 0.1,
            "y": 0.2
        }
    }
    """
    data = request.get_json()
    
    # 参数校验
    if not data.get('pdfId'):
        return jsonify({'error': 'Missing pdfId'}), 400
    # content 可以为空（用户可能先创建再编辑）

    try:
        pdf_id = data['pdfId']
        
        # ID 映射 (PDF ID -> File Hash)
        file_hash = get_file_hash(pdf_id)
        if not file_hash:
            return jsonify({'error': 'PDF file not found'}), 404

        # 获取参数
        title = data.get('title', '')
        content = data.get('content', '')
        note_type = data.get('noteType', 'general')
        color = data.get('color', '#FFEB3B')
        position = data.get('position')
        
        # 如果提供了标题，将标题和内容合并
        # 或者可以只存储内容，标题从前端生成
        note_content = json.dumps({
            'title': title,
            'content': content
        }) if title else content

        # 调用存储服务添加笔记
        note_id = current_app.storage_service.add_note(
            file_hash=file_hash,
            note_content=note_content,
            note_type=note_type,
            color=color,
            position=position
        )

        return jsonify({
            'success': True,
            'id': note_id,
            'message': 'Note created'
        })

    except Exception as e:
        current_app.logger.error(f"Error creating note: {e}")
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/<pdf_id>', methods=['GET'])
def get_notes(pdf_id):
    """
    获取某 PDF 的所有笔记
    
    Query Parameters:
    - page: 可选，按页筛选
    """
    try:
        file_hash = get_file_hash(pdf_id)
        if not file_hash:
            return jsonify({'error': 'PDF file not found'}), 404

        # 从数据库获取
        notes = current_app.storage_service.get_notes(
            file_hash=file_hash
        )
        
        # 解析笔记内容（如果是JSON格式）
        formatted_notes = []
        for note in notes:
            try:
                # 尝试解析为JSON（包含title和content）
                parsed = json.loads(note['note_content'])
                if isinstance(parsed, dict) and 'title' in parsed:
                    note['title'] = parsed['title']
                    note['content'] = parsed['content']
                else:
                    note['title'] = ''
                    note['content'] = note['note_content']
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON，直接使用原内容
                note['title'] = ''
                note['content'] = note['note_content']
            
            formatted_notes.append(note)
        
        return jsonify({
            'success': True,
            'notes': formatted_notes,
            'total': len(formatted_notes)
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching notes: {e}")
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """
    更新笔记
    
    Request Body:
    {
        "title": "新标题",  // 可选
        "content": "新内容",  // 必需
        "color": "#FFEB3B"  // 可选
    }
    """
    data = request.get_json()

    # content 可以为空（用户可能清空内容）

    try:
        title = data.get('title', '')
        content = data.get('content', '')
        color = data.get('color')
        
        # 合并标题和内容
        note_content = json.dumps({
            'title': title,
            'content': content
        }) if title else content

        # 更新笔记
        current_app.storage_service.update_note(
            note_id=note_id,
            note_content=note_content,
            color=color
        )
        
        return jsonify({
            'success': True,
            'message': 'Note updated'
        })

    except Exception as e:
        current_app.logger.error(f"Error updating note: {e}")
        return jsonify({'error': str(e)}), 500


@notes_bp.route('/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """删除笔记"""
    try:
        current_app.storage_service.delete_note(note_id)
        return jsonify({
            'success': True,
            'message': 'Note deleted'
        })
    except Exception as e:
        current_app.logger.error(f"Error deleting note: {e}")
        return jsonify({'error': str(e)}), 500