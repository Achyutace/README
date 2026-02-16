from flask import Blueprint, request, jsonify, g
from services.websearch_service import web_search_service
from route.utils import require_auth, _parse_paragraph_id

link_bp = Blueprint('link', __name__, url_prefix='/api/link')

@link_bp.route('/data', methods=['POST'])
@require_auth
def get_link_data():
    """
    根据 pdfId 和 targetParagraphId 获取论文信息
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    
    pdf_id = data.get("pdfId")
    para_id = data.get("targetParagraphId")
    
    if not isinstance(pdf_id, str) or not pdf_id.strip():
        return jsonify({"error": "pdfId is required"}), 400
    if not isinstance(para_id, str) or not para_id.strip():
        return jsonify({"error": "targetParagraphId is required"}), 400

    pdf_id = pdf_id.strip()
    para_id = para_id.strip()
    
    # 1. 解析段落 ID
    para_info = _parse_paragraph_id(para_id)
    if not para_info:
        return jsonify({"error": "Invalid targetParagraphId format"}), 400
    
    # 2. 从 PdfService 获取段落文本
    try:
        if not hasattr(g, 'pdf_service'):
            return jsonify({"error": "Service not initialized"}), 500

        paragraphs = g.pdf_service.get_paragraph(
            pdf_id=pdf_id, 
            pagenumber=para_info['page_number'], 
            paraid=para_info['index']
        )
        
        query_text = paragraphs[0].get('original_text', '') if paragraphs else ''
        if not query_text:
            return jsonify({"error": "Paragraph content empty"}), 404
            
    except FileNotFoundError:
        return jsonify({"error": "PDF file not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to get paragraph: {str(e)}"}), 500

    # 3. 搜索论文信息
    try:
        search_res = web_search_service.search_paper_smart(text=query_text)
        
        if not search_res.get("success"):
            return jsonify({
                "title": "",
                "url": "",
                "snippet": "未找到相关论文信息",
                "published_date": "",
                "authors": [],
                "source": "semantic_scholar",
                "valid": 0
            })
            
        result = search_res["paper"] # Now it returns 'paper' formatted
        
        return jsonify({
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "snippet": result.get("abstract", ""),
            "published_date": str(result.get("year", "")),
            "authors": result.get("authors", []),
            "source": "semantic_scholar",
            "valid": search_res.get("valid", 0)
        })
    except Exception as e:
         return jsonify({"error": f"Search failed: {str(e)}"}), 500
