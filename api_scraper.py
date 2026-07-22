import httpx
import asyncio
import os
import time

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

import datetime

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
                
                # If we get here, total_count <= 1000 (or it's a 1-day range that can't be split further)
                # Fetch all pages for this date range
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
                            results.append({
                                "github_url": item["html_url"],
                                "name": user_data.get("name"),
                                "email": user_data.get("email"),
                                "linkedin_url": user_data.get("blog") if "linkedin.com" in (user_data.get("blog") or "") else None,
                                "repositories": str(user_data.get("public_repos", 0))
                            })
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
