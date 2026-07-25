import httpx
import asyncio
import re
from bs4 import BeautifulSoup
from typing import Dict, Any, List

KEYWORD_PATTERNS = {
    "ISO 13485": re.compile(r'iso\s*13485', re.IGNORECASE),
    "21 CFR Part 11": re.compile(r'21\s*cfr\s*part\s*11', re.IGNORECASE),
    "FDA Compliance": re.compile(r'fda\s*(?:cleared|approved|registered|compliance)', re.IGNORECASE),
    "ISO 9001": re.compile(r'iso\s*9001', re.IGNORECASE),
    "CAPA / Audit": re.compile(r'capa|corrective\s*action|audit\s*readiness', re.IGNORECASE),
    "eQMS / Quality": re.compile(r'eqms|quality\s*management|document\tag|quality\s*system', re.IGNORECASE),
    "CE Mark / MDR": re.compile(r'ce\s*mark|eu\s*mdr|medical\s*device\s*regulation', re.IGNORECASE)
}

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

class DomainCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def _fetch_url(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return ""

    def _extract_text_and_emails(self, html_content: str) -> (str, List[str]):
        if not html_content:
            return "", []
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
            
        text = soup.get_text(separator=" ")
        clean_text = " ".join(text.split())
        
        emails = EMAIL_REGEX.findall(clean_text)
        valid_emails = [
            e for e in set(emails) 
            if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js'))
            and "example.com" not in e.lower()
        ]
        
        return clean_text[:4000], valid_emails

    async def crawl_domain(self, domain: str, base_url: str = None) -> Dict[str, Any]:
        """Crawls key target pages of a domain to gather QMS & regulatory compliance context."""
        if not base_url:
            base_url = f"https://www.{domain}"
            
        target_paths = ["", "/about", "/about-us", "/quality", "/compliance", "/products", "/careers"]
        combined_text = []
        all_emails = set()
        detected_keywords = []

        async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
            tasks = [self._fetch_url(client, f"{base_url.rstrip('/')}{path}") for path in target_paths]
            pages_content = await asyncio.gather(*tasks)

        for content in pages_content:
            if content:
                text, emails = self._extract_text_and_emails(content)
                if text:
                    combined_text.append(text)
                all_emails.update(emails)

        full_text = " ".join(combined_text)

        # Keyword signal detection
        for tag, pattern in KEYWORD_PATTERNS.items():
            if pattern.search(full_text):
                detected_keywords.append(tag)

        return {
            "domain": domain,
            "scraped_text": full_text[:5000],
            "detected_keywords": detected_keywords,
            "emails_found": list(all_emails)[:5]
        }
