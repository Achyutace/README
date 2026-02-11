import re

def clean_title(title: str) -> str:
    """清理论文标题，移除多余空白和换行"""
    if not title:
        return ""
    # 移除换行符和多余空格
    cleaned = re.sub(r'\s+', ' ', title.strip())
    return cleaned

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
