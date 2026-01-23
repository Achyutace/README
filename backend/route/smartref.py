"""
智能引用服务
通过 Semantic Scholar API 获取论文信息
"""
import re
import requests
from flask import Blueprint, request, jsonify, current_app

# 定义蓝图
smartref_bp = Blueprint('smartref', __name__, url_prefix='/api/smartref')

# Semantic Scholar API 配置
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
SEARCH_FIELDS = "paperId,title,authors,abstract,year,venue,citationCount,url,externalIds"

# ==================== 辅助函数 ====================

def clean_title(title: str) -> str:
    """清理论文标题，移除多余空白和换行"""
    if not title:
        return ""
    # 移除换行符和多余空格
    cleaned = re.sub(r'\s+', ' ', title.strip())
    return cleaned

def search_by_title(title: str) -> dict:
    """
    通过标题搜索论文
    """
    try:
        url = f"{SEMANTIC_SCHOLAR_API}/paper/search"
        params = {
            "query": clean_title(title),
            "fields": SEARCH_FIELDS,
            "limit": 1
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data.get("data") and len(data["data"]) > 0:
            return data["data"][0]
        return None

    except Exception as e:
        current_app.logger.error(f"Semantic Scholar search error: {e}")
        return None

def get_paper_by_doi(doi: str) -> dict:
    """
    通过 DOI 获取论文信息
    """
    try:
        url = f"{SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}"
        params = {"fields": SEARCH_FIELDS}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        current_app.logger.error(f"Semantic Scholar DOI lookup error: {e}")
        return None

def get_paper_by_arxiv(arxiv_id: str) -> dict:
    """
    通过 arXiv ID 获取论文信息
    """
    try:
        # 移除 arXiv: 前缀
        clean_id = arxiv_id.replace("arXiv:", "").strip()
        url = f"{SEMANTIC_SCHOLAR_API}/paper/arXiv:{clean_id}"
        params = {"fields": SEARCH_FIELDS}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        current_app.logger.error(f"Semantic Scholar arXiv lookup error: {e}")
        return None

def format_paper_response(paper: dict) -> dict:
    """
    格式化论文信息为前端需要的格式
    """
    if not paper:
        return None

    # 提取作者名
    authors = []
    if paper.get("authors"):
        authors = [author.get("name", "") for author in paper["authors"]]

    # 构建返回数据
    return {
        "paperId": paper.get("paperId", ""),
        "title": paper.get("title", ""),
        "authors": authors,
        "abstract": paper.get("abstract", ""),
        "year": paper.get("year"),
        "venue": paper.get("venue", ""),
        "citationCount": paper.get("citationCount", 0),
        "url": paper.get("url", ""),
        "doi": paper.get("externalIds", {}).get("DOI", ""),
        "arxivId": paper.get("externalIds", {}).get("ArXiv", ""),
    }

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

    try:
        paper = None
        search_method = None

        # 优先使用 DOI
        if doi:
            paper = get_paper_by_doi(doi)
            search_method = "doi"

        # 其次使用 arXiv ID
        if not paper and arxiv_id:
            paper = get_paper_by_arxiv(arxiv_id)
            search_method = "arxiv"

        # 最后使用标题搜索
        if not paper and title:
            paper = search_by_title(title)
            search_method = "title"

        if not paper:
            return jsonify({
                "success": False,
                "error": "Paper not found",
                "searchedBy": search_method
            }), 404

        formatted = format_paper_response(paper)

        return jsonify({
            "success": True,
            "paper": formatted,
            "searchedBy": search_method
        })

    except Exception as e:
        current_app.logger.error(f"Paper search error: {e}")
        return jsonify({"error": str(e)}), 500

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

    results = []

    for ref in references[:10]:  # 限制最多10个，避免请求过多
        title = ref.get("title", "").strip()
        doi = ref.get("doi", "").strip()
        arxiv_id = ref.get("arxivId", "").strip()

        paper = None

        if doi:
            paper = get_paper_by_doi(doi)
        elif arxiv_id:
            paper = get_paper_by_arxiv(arxiv_id)
        elif title:
            paper = search_by_title(title)

        if paper:
            results.append({
                "query": ref,
                "found": True,
                "paper": format_paper_response(paper)
            })
        else:
            results.append({
                "query": ref,
                "found": False,
                "paper": None
            })

    return jsonify({
        "success": True,
        "results": results,
        "total": len(results),
        "found": sum(1 for r in results if r["found"])
    })
