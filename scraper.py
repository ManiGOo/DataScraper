import re
import os
import urllib.parse
from typing import List, Dict, Optional, Callable
from playwright.sync_api import sync_playwright, Page, BrowserContext

# Force Playwright to look for browsers locally
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

class GitHubScraper:
    def __init__(self, headless: bool = True, delay: float = 1.0):
        self.headless = headless
        self.delay = delay

    def scrape(
        self, 
        query: str, 
        max_results: int = 10,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> List[Dict[str, Optional[str]]]:
        results = []

        def report(pct: int, msg: str):
            print(f"[{pct}%] {msg}")
            if progress_callback:
                progress_callback(pct, msg)

        report(5, f"Initializing browser engine for query: '{query}'...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            encoded_query = urllib.parse.quote(query)
            search_url = f"https://github.com/search?q={encoded_query}&type=users"
            report(15, f"Navigating to GitHub Search interface...")
            page.goto(search_url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            report(25, "Extracting profile links from search results...")
            profile_urls = self._extract_profile_urls(page, max_results)
            report(30, f"Discovered {len(profile_urls)} profile(s) to process.")

            if not profile_urls:
                report(100, "No profile results found for query.")
                browser.close()
                return []

            step_pct = (90 - 30) / len(profile_urls)

            for index, profile_url in enumerate(profile_urls, 1):
                current_pct = int(30 + (index * step_pct))
                username = profile_url.rstrip('/').split('/')[-1]
                report(current_pct, f"[{index}/{len(profile_urls)}] Scraping profile: @{username}")
                profile_data = self._scrape_profile(context, profile_url)
                results.append(profile_data)

            report(95, "Finalizing extracted dataset...")
            browser.close()

        report(100, f"Scraping complete. Total records gathered: {len(results)}")
        return results

    def _extract_profile_urls(self, page: Page, max_results: int) -> List[str]:
        profile_urls = set()
        
        try:
            page.wait_for_selector('a[href]', timeout=5000)
        except Exception:
            pass

        hrefs = page.eval_on_selector_all('a', 'elements => elements.map(e => e.getAttribute("href"))')
        
        excluded_paths = {
            '', 'search', 'login', 'signup', 'features', 'enterprise', 
            'explore', 'marketplace', 'pricing', 'about', 'contact', 
            'discussions', 'security', 'customer-stories', 'readme',
            'orgs', 'settings', 'notifications', 'site', 'privacy', 'terms'
        }

        for href in hrefs:
            if not href:
                continue
            if href.startswith('/') and not href.startswith('//'):
                clean_href = href.split('?')[0].split('#')[0]
                parts = clean_href.strip('/').split('/')
                if len(parts) == 1 and parts[0]:
                    username = parts[0]
                    if username.lower() not in excluded_paths and not username.startswith('.'):
                        full_url = f"https://github.com/{username}"
                        profile_urls.add(full_url)
                        if len(profile_urls) >= max_results:
                            break

        return list(profile_urls)[:max_results]

    def _scrape_profile(self, context: BrowserContext, profile_url: str) -> Dict[str, Optional[str]]:
        page = context.new_page()
        profile_data = {
            "Name": None,
            "Email": "N/A",
            "LinkedIn URL": "N/A",
            "GitHub URL": profile_url,
            "Repositories": "N/A"
        }

        try:
            page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000)

            # 1. Extract Name
            name_el = page.query_selector('span.p-name, h1 span.aria-label, span.p-nickname')
            if name_el:
                name_text = name_el.inner_text().strip()
                if name_text:
                    profile_data["Name"] = name_text
            if not profile_data["Name"]:
                username = profile_url.rstrip('/').split('/')[-1]
                profile_data["Name"] = username

            # 2. Extract Email
            mailto_el = page.query_selector('a[href^="mailto:"]')
            if mailto_el:
                href = mailto_el.get_attribute('href') or ''
                email = href.replace('mailto:', '').strip()
                if email:
                    profile_data["Email"] = email

            page_text = page.content()
            if profile_data["Email"] == "N/A":
                found_emails = EMAIL_REGEX.findall(page_text)
                valid_emails = [e for e in found_emails if not e.endswith(('.png', '.jpg', '.svg', 'github.com', 'noreply'))]
                if valid_emails:
                    profile_data["Email"] = valid_emails[0]

            # 3. Extract LinkedIn URL
            linkedin_el = page.query_selector('a[href*="linkedin.com"]')
            if linkedin_el:
                linkedin_href = linkedin_el.get_attribute('href')
                if linkedin_href:
                    profile_data["LinkedIn URL"] = linkedin_href
            else:
                linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?', page_text)
                if linkedin_match:
                    profile_data["LinkedIn URL"] = linkedin_match.group(0)

            # 4. Extract Repositories Count
            repo_tab_el = page.query_selector('a[href$="?tab=repositories"] span.Counter, a[href$="?tab=repositories"] span')
            if repo_tab_el:
                repo_count_text = repo_tab_el.inner_text().strip()
                if repo_count_text:
                    profile_data["Repositories"] = repo_count_text
            else:
                counter_els = page.query_selector_all('span.Counter')
                if counter_els:
                    profile_data["Repositories"] = counter_els[0].inner_text().strip()

        except Exception as e:
            print(f"[-] Error scraping profile {profile_url}: {e}")
        finally:
            page.close()

        return profile_data
