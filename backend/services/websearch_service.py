import logging
import json
import requests
import arxiv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any, Optional, Literal
from utils.paper_utils import clean_title, format_paper_response
from config import settings

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

    SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
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
                return self._demo_search(query)
        
        return self._demo_search(query)
    
    def _demo_search(self, query: str) -> List[Dict]:
        """Return demo search results."""
        return [
            {
                'title': f'Search Result 1: {query}',
                'url': 'https://example.com/1',
                'snippet': f'This is the latest info about "{query}". According to recent studies...',
                'source': 'web_demo'
            },
            {
                'title': f'Search Result 2: {query} Details',
                'url': 'https://example.com/2',
                'snippet': f'In-depth analysis of "{query}" background and applications...',
                'source': 'web_demo'
            },
            {
                'title': f'{query} - Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/' + query.replace(' ', '_'),
                'snippet': f'{query} is an important concept involving multiple fields...',
                'source': 'web_demo'
            }
        ]

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

            url = f"{self.SEMANTIC_SCHOLAR_API}/paper/search"
            
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
    
    def get_paper_by_doi(self, doi: str) -> Optional[Dict]:
        """Fetch paper info by DOI using Semantic Scholar"""
        try:
            url = f"{self.SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}"
            params = {"fields": self.S2_SEARCH_FIELDS}
            response = self.s2_session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Semantic Scholar DOI lookup error: {e}")
            return None

    def get_paper_by_arxiv(self, arxiv_id: str) -> Optional[Dict]:
        """Fetch paper info by arXiv ID using Semantic Scholar"""
        try:
            clean_id = arxiv_id.replace("arXiv:", "").strip()
            url = f"{self.SEMANTIC_SCHOLAR_API}/paper/arXiv:{clean_id}"
            params = {"fields": self.S2_SEARCH_FIELDS}
            response = self.s2_session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Semantic Scholar arXiv lookup error: {e}")
            return None

    def search_by_title_single(self, title: str) -> Optional[Dict]:
        """Search a single paper by title using Semantic Scholar"""
        try:
            url = f"{self.SEMANTIC_SCHOLAR_API}/paper/search"
            params = {
                "query": clean_title(title),
                "fields": self.S2_SEARCH_FIELDS,
                "limit": 1
            }
            response = self.s2_session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("data") and len(data["data"]) > 0:
                return data["data"][0]
            return None
        except Exception as e:
            logger.error(f"Semantic Scholar title search error: {e}")
            return None

    def search_paper_smart(self, title: str = "", doi: str = "", arxiv_id: str = "") -> Dict[str, Any]:
        """
        Smart search for paper info with priority: DOI > arXiv > Title
        """
        paper = None
        search_method = None

        if doi:
            paper = self.get_paper_by_doi(doi)
            search_method = "doi"

        if not paper and arxiv_id:
            paper = self.get_paper_by_arxiv(arxiv_id)
            search_method = "arxiv"

        if not paper and title:
            paper = self.search_by_title_single(title)
            search_method = "title"

        if not paper:
            return {
                "success": False,
                "error": "Paper not found",
                "searchedBy": search_method
            }

        formatted = format_paper_response(paper)
        return {
            "success": True,
            "paper": formatted,
            "searchedBy": search_method
        }

    def batch_search_papers(self, references: List[Dict]) -> List[Dict]:
        """
        Batch search for multiple papers.
        references: List of dicts with keys 'title', 'doi', 'arxivId'
        """
        results = []
        for ref in references[:10]:  # Limit to 10
            title = ref.get("title", "").strip()
            doi = ref.get("doi", "").strip()
            arxiv_id = ref.get("arxivId", "").strip()

            paper = None
            if doi:
                paper = self.get_paper_by_doi(doi)
            elif arxiv_id:
                paper = self.get_paper_by_arxiv(arxiv_id)
            elif title:
                paper = self.search_by_title_single(title)

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
