import asyncio
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
import urllib.parse

async def test():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    query = urllib.parse.quote('"Pharmaceutical Formulations" manufacturer "india" "pvt ltd"')
    
    async with AsyncSession(impersonate="chrome110") as client:
        r = await client.get(f'https://search.yahoo.com/search?p={query}', headers=headers, timeout=10.0)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        results = soup.find_all('div', class_='compTitle')
        print(f"Found {len(results)} results")
        for div in results:
            a = div.find('a')
            if a:
                h = a.get('href')
                print(" -", h)

asyncio.run(test())
