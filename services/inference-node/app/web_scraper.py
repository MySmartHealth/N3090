"""
Web Scraping for Knowledge Base Ingestion
Scrapes websites, extracts content, and adds to RAG knowledge base.
"""
import asyncio
import aiohttp
import hashlib
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
from loguru import logger

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("BeautifulSoup not installed: pip install beautifulsoup4")

try:
    import PyPDF2
    from io import BytesIO
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 not installed: pip install PyPDF2")


class WebScraper:
    """
    Web scraper for knowledge base ingestion.
    Supports HTML pages, PDFs, and markdown content.
    """
    
    def __init__(self, max_depth: int = 2, max_pages: int = 100):
        """
        Initialize web scraper.
        
        Args:
            max_depth: Maximum crawl depth
            max_pages: Maximum pages to scrape per session
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.visited_urls = set()
        self.scraped_content = []
    
    async def scrape_url(
        self,
        url: str,
        specialty: str = "general",
        doc_type: str = "reference",
        follow_links: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scrape a single URL or recursively scrape linked pages.
        
        Args:
            url: URL to scrape
            specialty: Medical specialty tag
            doc_type: Document type (reference, guideline, research)
            follow_links: Whether to follow links on the page
            
        Returns:
            List of scraped documents
        """
        if not BS4_AVAILABLE:
            raise RuntimeError("BeautifulSoup required: pip install beautifulsoup4")
        
        self.visited_urls.clear()
        self.scraped_content.clear()
        
        await self._scrape_recursive(url, specialty, doc_type, follow_links, depth=0)
        
        logger.info(f"Scraped {len(self.scraped_content)} documents from {url}")
        return self.scraped_content
    
    async def _scrape_recursive(
        self,
        url: str,
        specialty: str,
        doc_type: str,
        follow_links: bool,
        depth: int
    ):
        """Recursive scraping with depth control."""
        if depth > self.max_depth or len(self.scraped_content) >= self.max_pages:
            return
        
        if url in self.visited_urls:
            return
        
        self.visited_urls.add(url)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch {url}: {response.status}")
                        return
                    
                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    if 'application/pdf' in content_type:
                        content = await response.read()
                        doc = await self._extract_pdf_content(content, url, specialty, doc_type)
                        if doc:
                            self.scraped_content.append(doc)
                    
                    elif 'text/html' in content_type or 'text/plain' in content_type:
                        html = await response.text()
                        doc = await self._extract_html_content(html, url, specialty, doc_type)
                        if doc:
                            self.scraped_content.append(doc)
                        
                        # Follow links if enabled
                        if follow_links and depth < self.max_depth:
                            links = self._extract_links(html, url)
                            for link in links[:10]:  # Limit links per page
                                await self._scrape_recursive(
                                    link, specialty, doc_type, follow_links, depth + 1
                                )
                    
                    else:
                        logger.warning(f"Unsupported content type: {content_type}")
        
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
    
    async def _extract_html_content(
        self,
        html: str,
        url: str,
        specialty: str,
        doc_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract text content from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract title
        title = soup.title.string if soup.title else urlparse(url).path
        
        # Extract main content
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if not main_content:
            return None
        
        text = main_content.get_text(separator='\n', strip=True)
        
        # Clean up text
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        content = '\n'.join(lines)
        
        if len(content) < 100:  # Skip very short pages
            return None
        
        # Create document
        return {
            "content": content,
            "title": title,
            "source_url": url,
            "specialty": specialty,
            "doc_type": doc_type,
            "content_hash": hashlib.md5(content.encode()).hexdigest(),
            "scraped_at": datetime.utcnow().isoformat(),
            "metadata": {
                "scraper": "WebScraper",
                "content_length": len(content),
                "url": url
            }
        }
    
    async def _extract_pdf_content(
        self,
        pdf_bytes: bytes,
        url: str,
        specialty: str,
        doc_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract text from PDF."""
        if not PDF_AVAILABLE:
            logger.warning("PyPDF2 not available, skipping PDF")
            return None
        
        try:
            pdf_file = BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text from all pages
            text_parts = []
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())
            
            content = '\n\n'.join(text_parts)
            
            if len(content) < 100:
                return None
            
            # Get title from metadata or URL
            title = pdf_reader.metadata.get('/Title', urlparse(url).path) if pdf_reader.metadata else urlparse(url).path
            
            return {
                "content": content,
                "title": str(title),
                "source_url": url,
                "specialty": specialty,
                "doc_type": doc_type,
                "content_hash": hashlib.md5(content.encode()).hexdigest(),
                "scraped_at": datetime.utcnow().isoformat(),
                "metadata": {
                    "scraper": "WebScraper",
                    "content_length": len(content),
                    "url": url,
                    "pages": len(pdf_reader.pages)
                }
            }
        
        except Exception as e:
            logger.error(f"Error extracting PDF {url}: {e}")
            return None
    
    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract and normalize links from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for anchor in soup.find_all('a', href=True):
            href = anchor['href']
            
            # Skip anchors, mailto, javascript
            if href.startswith('#') or href.startswith('mailto:') or href.startswith('javascript:'):
                continue
            
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            
            # Only follow links on the same domain
            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                links.append(absolute_url)
        
        return links
    
    async def scrape_multiple_urls(
        self,
        urls: List[str],
        specialty: str = "general",
        doc_type: str = "reference",
        follow_links: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs in parallel.
        
        Args:
            urls: List of URLs to scrape
            specialty: Medical specialty tag
            doc_type: Document type
            follow_links: Whether to follow links
            
        Returns:
            Combined list of scraped documents
        """
        all_docs = []
        
        tasks = [
            self.scrape_url(url, specialty, doc_type, follow_links)
            for url in urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scraping failed: {result}")
            else:
                all_docs.extend(result)
        
        logger.info(f"Scraped {len(all_docs)} total documents from {len(urls)} URLs")
        return all_docs


class MedicalWebScraper(WebScraper):
    """
    Specialized scraper for medical websites.
    Includes domain-specific content extraction and filtering.
    """
    
    TRUSTED_MEDICAL_DOMAINS = [
        'nih.gov',
        'cdc.gov',
        'who.int',
        'pubmed.ncbi.nlm.nih.gov',
        'mayoclinic.org',
        'webmd.com',
        'medlineplus.gov',
        'uptodate.com',
        'nejm.org',
        'bmj.com',
        'thelancet.com',
    ]
    
    def is_trusted_domain(self, url: str) -> bool:
        """Check if URL is from a trusted medical domain."""
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in self.TRUSTED_MEDICAL_DOMAINS)
    
    async def scrape_medical_guidelines(
        self,
        disease: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Scrape medical guidelines for a specific disease.
        
        Args:
            disease: Disease or condition name
            max_results: Maximum number of results
            
        Returns:
            List of guideline documents
        """
        # Construct search URLs for trusted sources
        nih_url = f"https://www.ncbi.nlm.nih.gov/books/?term={disease}+guidelines"
        cdc_url = f"https://www.cdc.gov/search/?query={disease}"
        
        # This is a simplified example - in production, use proper API access
        logger.info(f"Would scrape guidelines for: {disease}")
        logger.info(f"NIH: {nih_url}")
        logger.info(f"CDC: {cdc_url}")
        
        return []


# Singleton instance
web_scraper = WebScraper()
medical_scraper = MedicalWebScraper()
