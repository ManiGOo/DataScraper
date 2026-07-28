import asyncio
import re
import urllib.parse
from playwright.async_api import async_playwright

class MiddleEastMapsScraper:
    def __init__(self):
        pass

    async def discover(self, target_region: str, target_sector: str, max_results: int = 10, exclude_domains: set = None):
        if exclude_domains is None:
            exclude_domains = set()
            
        print(f"[Maps Scraper] Searching for SMEs in {target_region} for {target_sector}")
        
        # E.g., "pharmaceutical manufacturer in UAE"
        clean_region = target_region.lower().replace('(maps)', '').strip()
        # Adding "pvt ltd" to specifically target SME private limited companies in open search
        query = f'"{target_sector}" manufacturer supplier "{clean_region}" "pvt ltd"'
        
        leads = []
        try:
            from bs4 import BeautifulSoup
            from curl_cffi.requests import AsyncSession
            import httpx
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            
            # Use curl_cffi to spoof a real Chrome browser TLS fingerprint
            async with AsyncSession(impersonate="chrome110") as client:
                target_raw = max_results * 5
                seen_domains = set()
                ignored = {'yahoo.com', 'google.com', 'bing.com', 'youtube.com', 'facebook.com', 'linkedin.com', 'wikipedia.org', 'indiamart.com', 'justdial.com', 'tradeindia.com', 'exportersindia.com', 'britannica.com', 'mdpi.com', 'pharmchoices.com', 'builtinpune.in'}
                
                # B2B Pharma Verification Keywords (Loosened to improve yield on general web search)
                PHARMA_KEYWORDS = ['pharma manufacturer', 'api manufacturing', 'contract manufacturing', 'formulation', 'dosage forms', 'pharmaceutical', 'medicine', 'gmp']
                BANNED_KEYWORDS = ['domain for sale', 'buy this domain', 'sedo.com', 'hospital', 'clinic', 'book appointment', 'journal', 'directory', 'list of']

                async def verify_domain(domain, company_name):
                    try:
                        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, verify=False) as h_client:
                            resp = await h_client.get(f'https://www.{domain}', headers=headers)
                            if resp.status_code >= 500: return False
                            text = resp.text[:10000].lower()
                            
                            for ban in BANNED_KEYWORDS:
                                if ban in text: return False
                                
                            for pk in PHARMA_KEYWORDS:
                                if pk in text: return True
                            
                            # If no strong pharma keyword, check if the company name appears at least roughly
                            company_words = [w for w in company_name.lower().split() if len(w) > 3]
                            if len(company_words) > 0:
                                matches = sum(1 for w in company_words if w in text)
                                if matches >= len(company_words):
                                    return True
                            return False
                    except:
                        return False

                # Query variations to rotate through
                queries = [
                    f'"{target_sector}" manufacturer supplier "{clean_region}" "pvt ltd"',
                    f'"{target_sector}" factory "{clean_region}" "pvt ltd"',
                    f'"{target_sector}" manufacturing "{clean_region}" "pvt ltd"',
                    f'"{target_sector}" exporter "{clean_region}" "pvt ltd"',
                    f'"{target_sector}" company "{clean_region}" "private limited"'
                ]

                print(f"[Maps Scraper] Executing Yahoo query rotation to find {max_results} leads...")
                
                for query in queries:
                    if len(leads) >= max_results:
                        break
                        
                    q_enc = urllib.parse.quote(query)
                    r = await client.get(f'https://search.yahoo.com/search?p={q_enc}', headers=headers, timeout=10.0)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    
                    results = soup.find_all('div', class_='compTitle')
                    if not results:
                        continue
                        
                    for div in results:
                        if len(leads) >= max_results:
                            break
                            
                        a_tag = div.find('a')
                        if not a_tag or not a_tag.get('href'):
                            continue
                            
                        h = a_tag['href']
                        # Yahoo tracking link format: /RU=https%3a%2f%2fkashmikformulation.com%2f/RK=
                        if '/RU=' in h:
                            try:
                                h = h.split('/RU=')[1].split('/')[0]
                                h = urllib.parse.unquote(h)
                            except:
                                pass

                        parsed = urllib.parse.urlparse(h)
                        domain = parsed.netloc.lower().replace('www.', '')
                        
                        if domain and domain not in seen_domains and not any(ig in domain for ig in ignored) and not domain.endswith('.gov.in'):
                            seen_domains.add(domain)
                            
                            if domain in exclude_domains:
                                print(f"[Maps Scraper] Skipping {domain} - already in database.")
                                continue
                            name_guess = domain.split('.')[0].capitalize()
                            
                            # Verify the domain is actually a B2B SME
                            is_valid = await verify_domain(domain, name_guess)
                            if not is_valid:
                                print(f"[Maps Scraper] Rejected {domain} (Failed B2B Verification)")
                                continue
                            
                            print(f"[Maps Scraper] Verified SME domain: {domain}")
                            leads.append({
                                "name": name_guess,
                                "domain": domain,
                                "website_url": f"https://www.{domain}",
                                "source_directory": "Local Maps/Search Directory",
                                "is_sme": True,
                                "estimated_revenue": "< $10M (Estimated SME)"
                            })
                    
                    await asyncio.sleep(2) # Polite delay
                    
                print(f"[Debug] Maps scraper found {len(leads)} leads after filtering.")
        except Exception as e:
            print(f"Maps Scraper Error: {e}")
            
        return leads
