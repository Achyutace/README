"""
智能引用服务
通过 WebSearchService 获取论文信息
"""
from flask import Blueprint, request, jsonify
from services.websearch_service import web_search_service

# 定义蓝图
smartref_bp = Blueprint('smartref', __name__, url_prefix='/api/smartref')





# ==================== 路由接口 ====================

@smartref_bp.route('/search', methods=['POST'])
def search_paper():
    """
    搜索论文信息

    请求体:
    {
        "title": "论文标题",  // 可选
        "doi": "DOI",        // 可选
        "arxivId": "arXiv ID" // 可选
    }

    优先级: DOI > arXiv ID > 标题搜索
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Missing request body"}), 400

    title = data.get("title", "").strip()
    doi = data.get("doi", "").strip()
    arxiv_id = data.get("arxivId", "").strip()

    if not title and not doi and not arxiv_id:
        return jsonify({"error": "At least one of title, doi, or arxivId is required"}), 400

    result = web_search_service.search_paper_smart(title, doi, arxiv_id)
    
    if not result.get("success"):
        return jsonify(result), 404
        
    return jsonify(result)

@smartref_bp.route('/query', methods=['POST'])
def query_papers():
    """
    通用论文搜索 (关键词)
    
    请求体:
    {
        "query": "搜索关键词",
        "source": "arxiv" | "semantic_scholar",  // 可选，默认 arxiv
        "limit": 5                               // 可选
    }
    """
    data = request.get_json()
    
    if not data or not data.get("query"):
        return jsonify({"error": "Missing query parameter"}), 400
        
    query = data.get("query")
    source = data.get("source", "arxiv")
    limit = int(data.get("limit", 5))
    
    try:
        results = web_search_service.search_papers(query, source=source, max_results=limit)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@smartref_bp.route('/batch', methods=['POST'])
def batch_search():
    """
    批量搜索多篇论文

    请求体:
    {
        "references": [
            {"title": "论文1标题", "doi": "可选"},
            {"title": "论文2标题"}
        ]
    }
    """
    data = request.get_json()

    if not data or "references" not in data:
        return jsonify({"error": "Missing references array"}), 400

    references = data["references"]
    if not isinstance(references, list):
        return jsonify({"error": "references must be an array"}), 400

    results = web_search_service.batch_search_papers(references)

    return jsonify({
        "success": True,
        "results": results,
        "total": len(results),
        "found": sum(1 for r in results if r["found"])
    })
