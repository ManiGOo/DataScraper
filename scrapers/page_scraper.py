import asyncio
import re
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class DeepWebsiteScraper:
    """Scrapes a company website for real emails, phones, and social links."""
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
        # Basic phone pattern
        self.phone_pattern = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}')

    async def scrape(self, domain: str) -> dict:
        results = {
            "emails": set(),
            "phones": set(),
            "socials": {}
        }
        
        base_url = f"https://www.{domain}"
        
        try:
            async with AsyncSession(impersonate="chrome110") as client:
                # We will check the homepage and the contact page
                urls_to_check = [base_url, f"{base_url}/contact", f"{base_url}/contact-us"]
                
                for url in urls_to_check:
                    try:
                        resp = await client.get(url, headers=self.headers, timeout=5.0, allow_redirects=True)
                        if resp.status_code == 200:
                            text = resp.text
                            soup = BeautifulSoup(text, 'html.parser')
                            
                            # 1. Extract Emails
                            found_emails = self.email_pattern.findall(text)
                            for email in found_emails:
                                email_clean = email.lower()
                                # Filter out garbage regex matches (like image files)
                                if not email_clean.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.js', '.css', '.svg')):
                                    results["emails"].add(email_clean)
                                    
                            # Extract mailto links explicitly
                            for a in soup.find_all('a', href=True):
                                href = a['href'].lower()
                                if href.startswith('mailto:'):
                                    em = href.replace('mailto:', '').split('?')[0].strip()
                                    if '@' in em:
                                        results["emails"].add(em)
                                        
                                # 2. Extract Socials
                                if 'linkedin.com/company' in href:
                                    results["socials"]["linkedin"] = a['href']
                                elif 'twitter.com' in href or 'x.com' in href:
                                    results["socials"]["twitter"] = a['href']
                                elif 'facebook.com' in href:
                                    results["socials"]["facebook"] = a['href']
                                elif 'instagram.com' in href:
                                    results["socials"]["instagram"] = a['href']
                                    
                                # Extract tel links explicitly
                                if href.startswith('tel:'):
                                    ph = href.replace('tel:', '').strip()
                                    results["phones"].add(ph)

                            # 3. Extract visible phones from text (basic)
                            # Using soup.get_text() to avoid matching HTML attributes
                            clean_text = soup.get_text(separator=' ')
                            found_phones = self.phone_pattern.findall(clean_text)
                            for p in found_phones:
                                p_clean = p.strip()
                                if len(p_clean) >= 8:
                                    results["phones"].add(p_clean)
                                    
                    except Exception as e:
                        pass # Ignore errors for individual pages (like 404 on /contact)
        except Exception as e:
            print(f"[DeepWebsiteScraper] Error scraping {domain}: {e}")
            
        # Prioritize info/contact/sales emails to the top if multiple are found
        emails_list = list(results["emails"])
        emails_list.sort(key=lambda e: (not any(x in e for x in ['info@', 'sales@', 'contact@']), e))
        
        phones_list = list(results["phones"])
        
        return {
            "emails": emails_list,
            "phones": phones_list,
            "socials": results["socials"]
        }
