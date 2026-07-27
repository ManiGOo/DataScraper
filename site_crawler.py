import httpx
import re
import asyncio
from typing import Dict, Any, List, Set
import urllib.parse
from urllib.parse import urljoin

class CompanyWebsiteCrawler:
    """Async Deep Website Crawler extracting Social Links (LinkedIn, X, Instagram, Facebook, YouTube), Contact Emails & Phone Numbers."""
    
    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def crawl_site(self, domain: str, company_name: str = "") -> Dict[str, Any]:
        """Crawls homepage and subpages (/contact, /about, /leadership, /team) to extract social links, emails & phones."""
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        base_url = f"https://{clean_domain}"

        result = {
            "domain": clean_domain,
            "social_links": {
                "linkedin": None,
                "x_twitter": None,
                "instagram": None,
                "facebook": None,
                "youtube": None
            },
            "emails_found": [],
            "phones_found": [],
            "leadership_links": []
        }

        pages_to_crawl = [
            base_url,
            urljoin(base_url, "/contact"),
            urljoin(base_url, "/contact-us"),
            urljoin(base_url, "/about"),
            urljoin(base_url, "/about-us"),
            urljoin(base_url, "/leadership"),
            urljoin(base_url, "/team")
        ]

        seen_emails: Set[str] = set()
        seen_phones: Set[str] = set()
        seen_leadership: Set[str] = set()

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True, verify=False) as client:
                tasks = [self._fetch_page(client, url) for url in pages_to_crawl]
                pages_html = await asyncio.gather(*tasks)
        except Exception as e:
            print(f"[Site Crawler Error] {e}")
            pages_html = []

        for html in pages_html:
            if not html:
                continue

            # 1. Extract LinkedIn Company or Profile Page
            li_match = re.search(r'https?://(?:www\.)?linkedin\.com/(?:company|in|school)/[a-zA-Z0-9_.-]+', html, re.I)
            if li_match and not result["social_links"]["linkedin"]:
                result["social_links"]["linkedin"] = li_match.group(0)

            # 2. Extract X / Twitter
            tw_match = re.search(r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+', html, re.I)
            if tw_match and not result["social_links"]["x_twitter"]:
                url_found = tw_match.group(0)
                if "intent" not in url_found and "share" not in url_found and "widgets" not in url_found:
                    result["social_links"]["x_twitter"] = url_found

            # 3. Extract Instagram
            ig_match = re.search(r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.-]+', html, re.I)
            if ig_match and not result["social_links"]["instagram"]:
                result["social_links"]["instagram"] = ig_match.group(0)

            # 4. Extract Facebook
            fb_match = re.search(r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9_.-]+', html, re.I)
            if fb_match and not result["social_links"]["facebook"]:
                url_found = fb_match.group(0)
                if "sharer" not in url_found and "plugins" not in url_found:
                    result["social_links"]["facebook"] = url_found

            # 5. Extract YouTube
            yt_match = re.search(r'https?://(?:www\.)?youtube\.com/(?:channel|c|user|@)[a-zA-Z0-9_.-]+', html, re.I)
            if yt_match and not result["social_links"]["youtube"]:
                result["social_links"]["youtube"] = yt_match.group(0)

            # 6. Extract Emails
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
            for email in emails:
                e_clean = email.lower().strip()
                if not any(e_clean.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
                    seen_emails.add(e_clean)

            # 7. Extract Phone Numbers
            phones = re.findall(r'(?:\+\d{1,3}[\s-]?)?\(?\d{2,5}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}', html)
            for phone in phones:
                p_clean = phone.strip()
                digits = re.sub(r'\D', '', p_clean)
                if 8 <= len(digits) <= 15:
                    seen_phones.add(p_clean)

            # 8. Extract Leadership Links
            leader_links = re.findall(r'href=["\']([^"\']*(?:leadership|management|team|executive|board|director)[^"\']*)["\']', html, re.I)
            for l_link in leader_links:
                full_l = urljoin(base_url, l_link)
                seen_leadership.add(full_l)

        result["emails_found"] = list(seen_emails)[:5]
        result["phones_found"] = list(seen_phones)[:3]
        result["leadership_links"] = list(seen_leadership)[:3]

        # Smart Fallback Generator if missing from direct site HTML
        company_kw = clean_domain.split('.')[0].capitalize()
        if company_name:
            company_clean = re.sub(r'(?i)\b(pvt|ltd|inc|llc|corp|corporation|facilities|plant|manufacturing|pharma|pharmaceuticals|medical)\b', '', company_name)
            company_clean = re.sub(r'[^a-zA-Z0-9\s]', '', company_clean).strip()
            if company_clean:
                company_kw = company_clean

        q_kw = urllib.parse.quote_plus(company_kw)
        if not result["social_links"]["linkedin"]:
            result["social_links"]["linkedin"] = f"https://www.linkedin.com/search/results/companies/?keywords={q_kw}"
        if not result["social_links"]["x_twitter"]:
            result["social_links"]["x_twitter"] = f"https://x.com/search?q={q_kw}"
        if not result["social_links"]["instagram"]:
            result["social_links"]["instagram"] = f"https://www.google.com/search?q=site:instagram.com+{q_kw}"
        if not result["social_links"]["facebook"]:
            result["social_links"]["facebook"] = f"https://www.facebook.com/search/top?q={q_kw}"
        if not result["social_links"]["youtube"]:
            result["social_links"]["youtube"] = f"https://www.youtube.com/results?search_query={q_kw}"

        return result

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return ""
