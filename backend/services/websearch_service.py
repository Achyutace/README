import logging
import json
import requests
import arxiv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any, Optional, Literal
from utils.search_refine import clean_title, format_paper_response
from core.config import settings

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

logger = logging.getLogger(__name__)

class WebSearchService:
    """
    Unified Web Search Service integrating general web search (Tavily)
    and academic paper search (ArXiv, Semantic Scholar).
    """

    S2_SEARCH_FIELDS = "paperId,title,authors,abstract,year,venue,citationCount,url,externalIds"

    def __init__(self, tavily_api_key: Optional[str] = None):
        """
        Initialize the service.
        """
        self._tavily_api_key = tavily_api_key or (settings.tavily.api_key if hasattr(settings, 'tavily') else None)
        self.tavily_client = None
        self._init_tavily()

        # Clients for academic search
        self._arxiv_client = None
        self._s2_session = None

    def _init_tavily(self):
        if self._tavily_api_key and TavilyClient:
            try:
                self.tavily_client = TavilyClient(api_key=self._tavily_api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Tavily client: {e}")
        else:
            if not self._tavily_api_key:
                logger.warning("Tavily API key not found. Web search will use demo mode.")
            if not TavilyClient:
                logger.warning("tavily-python not installed. Web search will use demo mode.")

    @property
    def arxiv_client(self) -> arxiv.Client:
        if self._arxiv_client is None:
            self._arxiv_client = arxiv.Client(
                page_size=100,
                delay_seconds=3,
                num_retries=3
            )
        return self._arxiv_client

    @property
    def s2_session(self) -> requests.Session:
        if self._s2_session is None:
            self._s2_session = requests.Session()
            
            # Configure retry strategy
            retries = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retries)
            self._s2_session.mount('http://', adapter)
            self._s2_session.mount('https://', adapter)
            
            # Configure Proxies
            proxies = {}
            if settings.proxy.http:
                proxies["http"] = settings.proxy.http
            if settings.proxy.https:
                proxies["https"] = settings.proxy.https
            
            if proxies:
                self._s2_session.proxies.update(proxies)
            
            # Read API Key
            s2_key = settings.scientific.semantic_scholar_api_key if hasattr(settings, 'scientific') else None
            if s2_key:
                self._s2_session.headers.update({"x-api-key": s2_key})
        
        return self._s2_session

    # -------------------------------------------------------------------------
    # Web Search Methods (Tavily)
    # -------------------------------------------------------------------------

    def search_web(self, 
               query: str, 
               time_range: Optional[Literal["day", "week", "month", "year"]] = None,
               topic: Optional[Literal["general", "news"]] = "general",
               include_domains: Optional[List[str]] = None,
               exclude_domains: Optional[List[str]] = None,
               max_results: int = 15) -> List[Dict]:
        """
        Execute web search.
        """
        if self.tavily_client:
            try:
                search_params = {
                    "query": query,
                    "max_results": max_results
                }
                
                if time_range:
                    search_params["days"] = {
                        "day": 1,
                        "week": 7,
                        "month": 30,
                        "year": 365
                    }.get(time_range, None)
                
                if topic:
                    search_params["topic"] = topic
                
                if include_domains:
                    search_params["include_domains"] = include_domains
                if exclude_domains:
                    search_params["exclude_domains"] = exclude_domains
                
                response = self.tavily_client.search(**search_params)
                
                cleaned_results = []
                for result in response.get("results", []):
                    cleaned_results.append({
                        'title': result.get('title', 'No title'),
                        'url': result.get('url', ''),
                        'snippet': result.get('content', ''),
                        'published_date': result.get('published_date', ''),
                        'score': result.get('score', 0),
                        'source': 'web'
                    })
                return cleaned_results
            
            except Exception as e:
                logger.error(f"Tavily search error: {e}")
                return None
        
        return None

    # -------------------------------------------------------------------------
    # Academic Paper Search Methods (ArXiv & Semantic Scholar)
    # -------------------------------------------------------------------------

    def _search_arxiv(
        self,
        query: str, 
        max_results: int = 5,
        sort_by: Literal['relevance', 'lastUpdatedDate', 'submittedDate'] = 'relevance',
        sort_order: Literal['descending', 'ascending'] = 'descending'
    ) -> List[Dict[str, Any]]:
        """
        Search for papers on arXiv (Internal).
        """
        if not query:
            return []

        try:
            client = self.arxiv_client
            
            sort_map = {
                'relevance': arxiv.SortCriterion.Relevance,
                'lastUpdatedDate': arxiv.SortCriterion.LastUpdatedDate,
                'submittedDate': arxiv.SortCriterion.SubmittedDate
            }
            order_map = {
                'descending': arxiv.SortOrder.Descending,
                'ascending': arxiv.SortOrder.Ascending
            }

            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=sort_map.get(sort_by, arxiv.SortCriterion.Relevance),
                sort_order=order_map.get(sort_order, arxiv.SortOrder.Descending)
            )
            
            results = []
            for r in client.results(search):
                results.append({
                    "title": r.title,
                    "url": r.pdf_url,
                    "snippet": r.summary.replace("\n", " ")[:500] + "...", 
                    "published_date": r.published.strftime("%Y-%m-%d"),
                    "authors": [a.name for a in r.authors],
                    "source": "arxiv"
                })
                
            return results

        except Exception as e:
            logger.error(f"Arxiv search error: {e}")
            return []

    def _search_semantic_scholar(
        self,
        query: str, 
        max_results: int = 5,
        year: str = None, 
        fields_of_study: str = None,
        open_access_pdf: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for papers on Semantic Scholar (Internal).
        """
        if not query:
            return []
            
        try:
            session = self.s2_session
            
            params = {
                "query": query,
                "limit": max_results,
                "fields": "title,url,abstract,publicationDate,authors,openAccessPdf"
            }
            
            if year:
                params["year"] = year
            if fields_of_study:
                params["fieldsOfStudy"] = fields_of_study

            url = f"{settings.scientific.semantic_scholar_api_url}/paper/search"
            
            response = session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            papers = []
            for item in data.get("data", []):
                pdf_url = None
                if item.get("openAccessPdf"):
                     pdf_url = item["openAccessPdf"].get("url")
                
                if open_access_pdf and not pdf_url:
                    continue

                papers.append({
                    "title": item.get("title"),
                    "url": pdf_url or item.get("url"),
                    "snippet": (item.get("abstract") or "No abstract available.").replace("\n", " ")[:500] + "...",
                    "published_date": item.get("publicationDate", ""),
                    "authors": [a.get("name") for a in item.get("authors", [])],
                    "source": "semantic_scholar"
                })
                
            return papers

        except Exception as e:
            logger.error(f"Semantic Scholar search error: {e}")
            return []  

    def _search_s2_single(self, query: str) -> Optional[Dict]:
        """Internal helper to search a single paper by query (title or text snippet)"""
        try:
            url = f"{settings.scientific.semantic_scholar_api_url}/paper/search"
            params = {
                "query": clean_title(query),
                "fields": self.S2_SEARCH_FIELDS,
                "limit": 1
            }
            response = self.s2_session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data["data"][0] if data.get("data") else None
        except Exception as e:
            logger.error(f"Semantic Scholar search error for '{query[:50]}...': {e}")
            return None

    def search_paper_smart(self, title: str = "", doi: str = "", arxiv_id: str = "", text: str = "") -> Dict[str, Any]:
        """
        Smart search for paper info with priority: DOI > arXiv > Title > Text
        """
        paper = None
        method = None

        if doi:
            paper, method = self._fetch_s2_paper(f"DOI:{doi}"), "doi"
        
        if not paper and arxiv_id:
            paper, method = self._fetch_s2_paper(f"ArXiv:{arxiv_id.replace('arXiv:', '')}"), "arxiv"
            
        if not paper and title:
            paper, method = self._search_s2_single(title), "title"
            
        if not paper and text:
            paper, method = self._search_s2_single(text), "text"

        if not paper:
            return {"success": False, "error": "Paper not found", "searchedBy": method}

        return {
            "success": True, 
            "paper": format_paper_response(paper), 
            "searchedBy": method,
            "valid": 1 if paper.get("title") and paper.get("authors") else 0
        }

    def batch_search_papers(self, references: List[Dict]) -> List[Dict]:
        """Batch search for multiple papers using search_paper_smart logic"""
        results = []
        for ref in references[:10]:
            title = ref.get("title", "").strip()
            doi = ref.get("doi", "").strip()
            arxiv_id = ref.get("arxivId", "").strip()
            text = ref.get("text", "").strip()

            res = self.search_paper_smart(title=title, doi=doi, arxiv_id=arxiv_id, text=text)
            results.append({
                "query": ref,
                "found": res["success"],
                "paper": res.get("paper")
            })
        return results

    def search_papers(self, query: str, source: Literal["arxiv", "semantic_scholar"] = "arxiv", max_results: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """
        Unified paper search.
        sources: 'arxiv', 'semantic_scholar'
        """
        if source == "semantic_scholar":
            return self._search_semantic_scholar(query, max_results=max_results, **kwargs)
        return self._search_arxiv(query, max_results=max_results, **kwargs)

# Create a singleton instance for easy import
web_search_service = WebSearchService()
