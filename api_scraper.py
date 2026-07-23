import httpx
import datetime
import asyncio
import os
import time

import re

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
LINKEDIN_REGEX = re.compile(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?', re.IGNORECASE)
TWITTER_REGEX = re.compile(r'https?://(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+/?', re.IGNORECASE)
TELEGRAM_REGEX = re.compile(r'https?://t\.me/[a-zA-Z0-9_]+/?', re.IGNORECASE)

class GitHubAPIScraper:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token and self.token != "your_personal_access_token_here":
            self.headers["Authorization"] = f"token {self.token}"

    async def _handle_rate_limit(self, response):
        if "X-RateLimit-Remaining" in response.headers:
            remaining = int(response.headers["X-RateLimit-Remaining"])
            if remaining <= 0:
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                sleep_duration = max(0, reset_time - time.time()) + 1
                await asyncio.sleep(sleep_duration)
        elif response.status_code == 403 or response.status_code == 429:
            # Secondary rate limit or unauthorized
            await asyncio.sleep(60)

    async def _fetch_deep_profile_data(self, client, username, user_data, html_url):
        socials = []
        name = user_data.get("name")
        email = user_data.get("email")
        blog = user_data.get("blog")
        twitter_username = user_data.get("twitter_username")
        linkedin_url = None

        if blog:
            if "linkedin.com" in blog.lower():
                linkedin_url = blog
            else:
                socials.append(f"Website: {blog}")

        if twitter_username:
            socials.append(f"Twitter: https://twitter.com/{twitter_username}")

        # 1. Fetch Social Accounts API
        try:
            soc_resp = await client.get(f"https://api.github.com/users/{username}/social_accounts")
            await self._handle_rate_limit(soc_resp)
            if soc_resp.status_code == 200:
                soc_data = soc_resp.json()
                for soc in soc_data:
                    provider = soc.get("provider", "Social")
                    url = soc.get("url", "")
                    if "linkedin.com" in url.lower():
                        linkedin_url = url
                    else:
                        socials.append(f"{provider.capitalize()}: {url}")
        except Exception:
            pass

        # 2. Fetch Profile README.md
        try:
            readme_headers = dict(self.headers)
            readme_headers["Accept"] = "application/vnd.github.v3.raw"
            readme_resp = await client.get(f"https://api.github.com/repos/{username}/{username}/readme", headers=readme_headers)
            await self._handle_rate_limit(readme_resp)
            if readme_resp.status_code == 200:
                content = readme_resp.text
                
                # Extract email from README if missing in profile
                if not email:
                    found_emails = EMAIL_REGEX.findall(content)
                    valid_emails = [
                        e for e in found_emails 
                        if "noreply.github.com" not in e.lower() 
                        and not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg'))
                    ]
                    if valid_emails:
                        email = valid_emails[0]
                
                # Extract LinkedIn from README if missing
                if not linkedin_url:
                    found_linkedin = LINKEDIN_REGEX.findall(content)
                    if found_linkedin:
                        linkedin_url = found_linkedin[0]

                # Extract Twitter from README
                found_twitter = TWITTER_REGEX.findall(content)
                for tw in found_twitter:
                    tw_str = f"Twitter: {tw}"
                    if tw_str not in socials:
                        socials.append(tw_str)

                # Extract Telegram from README
                found_telegram = TELEGRAM_REGEX.findall(content)
                for tg in found_telegram:
                    tg_str = f"Telegram: {tg}"
                    if tg_str not in socials:
                        socials.append(tg_str)
        except Exception:
            pass

        social_links_str = " | ".join(socials) if socials else None

        return {
            "github_url": html_url,
            "name": name or "N/A",
            "email": email or "N/A",
            "linkedin_url": linkedin_url or "N/A",
            "social_links": social_links_str or "N/A",
            "repositories": str(user_data.get("public_repos", 0))
        }

    async def scrape(self, query, max_results, job_id, update_progress_callback):
        results = []
        total_fetched = 0
        
        # Initial date range for splitting
        start_date = datetime.date(2007, 10, 1)
        end_date = datetime.date.today()
        
        queue = [(start_date, end_date)]
        
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            while queue and total_fetched < max_results:
                current_start, current_end = queue.pop(0)
                
                date_filter = f"created:{current_start.isoformat()}..{current_end.isoformat()}"
                query_with_date = f"{query} {date_filter}"
                
                # Probe query to get total_count
                probe_url = f"https://api.github.com/search/users?q={query_with_date}&per_page=1"
                probe_resp = await client.get(probe_url)
                await self._handle_rate_limit(probe_resp)
                
                if probe_resp.status_code != 200:
                    if probe_resp.status_code in [403, 429]:
                        await asyncio.sleep(60)
                        queue.insert(0, (current_start, current_end))
                    continue
                    
                data = probe_resp.json()
                total_count = data.get("total_count", 0)
                
                # If > 1000 results, split the date range
                if total_count > 1000 and current_start < current_end:
                    delta = current_end - current_start
                    mid_days = delta.days // 2
                    if mid_days > 0:
                        mid_date = current_start + datetime.timedelta(days=mid_days)
                        queue.insert(0, (mid_date + datetime.timedelta(days=1), current_end))
                        queue.insert(0, (current_start, mid_date))
                        continue
                
                # Fetch pages
                page = 1
                while total_fetched < max_results:
                    page_url = f"https://api.github.com/search/users?q={query_with_date}&per_page=100&page={page}"
                    page_resp = await client.get(page_url)
                    await self._handle_rate_limit(page_resp)
                    
                    if page_resp.status_code != 200:
                        break
                        
                    page_data = page_resp.json()
                    items = page_data.get("items", [])
                    
                    if not items:
                        break
                        
                    for item in items:
                        if total_fetched >= max_results:
                            break
                            
                        username = item["login"]
                        user_url = f"https://api.github.com/users/{username}"
                        user_resp = await client.get(user_url)
                        await self._handle_rate_limit(user_resp)
                        
                        if user_resp.status_code == 200:
                            user_data = user_resp.json()
                            profile_info = await self._fetch_deep_profile_data(client, username, user_data, item["html_url"])
                            results.append(profile_info)
                            total_fetched += 1
                            
                            if update_progress_callback:
                                if asyncio.iscoroutinefunction(update_progress_callback):
                                    await update_progress_callback(job_id, total_fetched, max_results)
                                else:
                                    update_progress_callback(job_id, total_fetched, max_results)
                                    
                    page += 1
                    if page > 10:
                        break
                        
        return results
