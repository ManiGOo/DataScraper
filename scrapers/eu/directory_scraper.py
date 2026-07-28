import asyncio
import re
import urllib.parse
from playwright.async_api import async_playwright

class EUDirectoryScraper:
    def __init__(self):
        pass

    async def discover(self, target_region: str, target_sector: str, max_results: int = 10, exclude_domains: set = None):
        print(f"[EU Scraper] Searching for SMEs in {target_region} for {target_sector}")
        
        # EU SME specific search
        query = urllib.parse.quote_plus(f'{target_sector} SME manufacturer {target_region}')
        
        leads = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            page = await context.new_page()
            
            # Apply stealth plugin
            try:
                from playwright_stealth import stealth_async
                await stealth_async(page)
            except ImportError:
                pass
            
            try:
                await page.goto(f'https://www.bing.com/search?q={query}&mkt=en-US', timeout=15000)
                await asyncio.sleep(2)
                
                content = await page.content()
                hrefs = re.findall(r'href=\"(https?://[^\"]+)\"', content)
                
                ignored = {'google.com', 'bing.com', 'youtube.com', 'facebook.com', 'linkedin.com', 'wikipedia.org', 'europa.eu'}
                
                seen_domains = set()
                
                for h in hrefs:
                    if len(leads) >= max_results:
                        break
                        
                    parsed = urllib.parse.urlparse(h)
                    domain = parsed.netloc.lower().replace('www.', '')
                    
                    if domain and domain not in seen_domains and not any(ig in domain for ig in ignored):
                        name_guess = domain.split('.')[0].capitalize()
                        
                        seen_domains.add(domain)
                        leads.append({
                            "name": name_guess,
                            "domain": domain,
                            "website_url": f"https://www.{domain}",
                            "source_directory": "EU SME Directory Search",
                            "is_sme": True,
                            "estimated_revenue": "< €50M (Estimated SME)"
                        })
            except Exception as e:
                print(f"EU Scraper Error: {e}")
                
            await browser.close()
            
        return leads
