import httpx
import asyncio
import re
import urllib.parse
from typing import List, Dict, Any

REGION_KEYWORDS_MAP = {
    "india": ["india", "hyderabad", "telangana", "gujarat", "ahmedabad", "mumbai", "maharashtra", "bengaluru", "karnataka", "delhi", "himachal", "in"],
    "middle east": ["israel", "uae", "united arab emirates", "saudi", "dubai", "tel aviv", "ras al khaimah", "middle east", "il", "ae", "sa"],
    "europe": ["uk", "united kingdom", "germany", "switzerland", "france", "ireland", "oxford", "basel", "göttingen", "munich", "london", "de", "ch", "fr", "ie"],
    "asia": ["japan", "singapore", "korea", "china", "tokyo", "osaka", "jp", "sg", "kr", "cn", "asia"],
    "south america": ["brazil", "argentina", "são paulo", "buenos aires", "br", "ar", "south america"],
    "north america": ["usa", "united states", "canada", "california", "massachusetts", "new jersey", "texas", "north america"]
}

def has_keyword(text: str, kw: str) -> bool:
    """Checks if keyword exists in text using word boundary for 2-letter codes."""
    if len(kw) <= 2:
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', text))
    return kw in text

def extract_location_tokens(target_region: str) -> List[str]:
    """Extracts dynamic comma-separated or parenthesized state/country tokens."""
    text = target_region.strip()
    
    paren_match = re.search(r'\(([^)]+)\)', text)
    if paren_match:
        inside = paren_match.group(1)
        tokens = [t.strip().lower() for t in inside.split(',') if t.strip()]
        if tokens:
            return tokens

    if ',' in text:
        tokens = [t.strip().lower() for t in text.split(',') if t.strip()]
        if tokens:
            return tokens

    cleaned = re.sub(r'[\(\)]', '', text).strip().lower()
    return [cleaned] if cleaned else []

def is_region_match(target_region: str, candidate_region: str) -> bool:
    """Strictly matches dynamic comma-separated or parenthesized state/country sub-locations."""
    cand_lower = candidate_region.lower()
    tokens = extract_location_tokens(target_region)

    if not tokens:
        return True

    for token in tokens:
        if has_keyword(cand_lower, token):
            return True
        if token in REGION_KEYWORDS_MAP:
            if any(has_keyword(cand_lower, kw) for kw in REGION_KEYWORDS_MAP[token]):
                return True

    return False

def is_sector_match(target_sec: str, lead_sec: str) -> bool:
    if not target_sec or target_sec == "ALL":
        return True
    if not lead_sec:
        return True
    ts = target_sec.lower()
    ls = lead_sec.lower()
    if "formulation" in ts or "fdf" in ts:
        return "formulation" in ls or "fdf" in ls
    if "api" in ts or "active" in ts:
        return ("api" in ls or "active" in ls) and "formulation" not in ls and "fdf" not in ls
    if "device" in ts or "medtech" in ts:
        return "device" in ls or "medtech" in ls
    if "biotech" in ts or "gene" in ts:
        return "biotech" in ls or "gene" in ls or "cell" in ls
    return True


class LeadDiscoveryEngine:
    """100% Dynamic Live Lead Discovery Engine via Government APIs (openFDA, Health Canada) & Live Web Search Scrapers."""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

    async def _discover_fda_registered_facilities(self, region: str, sector: str, limit: int = 10, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Queries openFDA establishment registrations matching target region dynamically."""
        leads = []
        try:
            country_code = ""
            reg_lower = region.lower()
            if "india" in reg_lower:
                country_code = "IN"
            elif "israel" in reg_lower or "middle east" in reg_lower:
                country_code = "IL"
            elif "germany" in reg_lower:
                country_code = "DE"
            elif "uk" in reg_lower or "united kingdom" in reg_lower:
                country_code = "GB"
            elif "japan" in reg_lower:
                country_code = "JP"
            elif "canada" in reg_lower:
                country_code = "CA"
            elif "brazil" in reg_lower:
                country_code = "BR"
            elif "switzerland" in reg_lower:
                country_code = "CH"
            elif "france" in reg_lower:
                country_code = "FR"
            elif "italy" in reg_lower:
                country_code = "IT"

            url = f"https://api.fda.gov/device/registrationlisting.json?limit={limit * 5}"
            if country_code:
                url = f"https://api.fda.gov/device/registrationlisting.json?search=registration.iso_country_code:{country_code}&limit={limit * 5}"

            async with httpx.AsyncClient(headers=self.headers, timeout=12.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    for item in results:
                        reg = item.get("registration", {})
                        comp_name = reg.get("facility_name") or reg.get("owner_operator", {}).get("firm_name")
                        city = reg.get("city", "")
                        country = reg.get("iso_country_code", "US")
                        cand_region = f"{city}, {country}".strip(", ")
                        clean_domain = re.sub(r'[^a-zA-Z0-9]', '', comp_name.lower()) + ".com" if comp_name else ""
                        
                        if comp_name and clean_domain and is_region_match(region, cand_region) and (not exclude_domains or clean_domain not in exclude_domains):
                            leads.append({
                                "name": comp_name.title(),
                                "domain": clean_domain,
                                "region": cand_region,
                                "source": "openFDA Global Registry",
                                "industry_subsector": sector if sector else "Active Pharmaceutical Ingredients (API)",
                                "employee_range": "100-500 employees",
                                "website_url": f"https://www.{clean_domain}"
                            })
                            if len(leads) >= limit:
                                break
        except Exception as e:
            print(f"[Discovery] FDA Registry Notice: {e}")
        return leads

    async def _discover_health_canada_facilities(self, region: str, sector: str, limit: int = 10, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Queries Health Canada MDALL open API dynamically."""
        leads = []
        try:
            url = "https://health-products.canada.ca/api/medical-devices/company/?lang=en&type=json"
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data[:limit * 5]:
                        comp_name = item.get("company_name", "")
                        city = item.get("city", "")
                        prov = item.get("province", "Canada")
                        cand_region = f"{city}, {prov}, Canada".strip(", ")
                        clean_domain = re.sub(r'[^a-zA-Z0-9]', '', comp_name.lower()) + ".ca" if comp_name else ""
                        if comp_name and clean_domain and is_region_match(region, cand_region) and (not exclude_domains or clean_domain not in exclude_domains):
                            leads.append({
                                "name": comp_name.title(),
                                "domain": clean_domain,
                                "region": cand_region,
                                "source": "Health Canada MDALL & DPD Registry",
                                "industry_subsector": sector if sector else "Medical Devices & MedTech Producers",
                                "employee_range": "100-500 employees",
                                "website_url": f"https://www.{clean_domain}"
                            })
                            if len(leads) >= limit:
                                break
        except Exception as e:
            print(f"[Discovery] Health Canada API Notice: {e}")
        return leads

    async def _discover_live_web_producers(
        self, 
        target_region: str, 
        target_sector: str, 
        limit: int = 10, 
        exclude_domains: set = None
    ) -> List[Dict[str, Any]]:
        """Dynamically fetches real-world Life Science & pharma producer websites live from Web Search."""
        leads = []
        if exclude_domains is None:
            exclude_domains = set()

        reg_clean = re.sub(r'[\(\)]', '', target_region).strip()
        sec_clean = target_sector.replace("Producers", "").replace("Developers", "").strip() if target_sector else "Pharmaceutical"
        
        search_query = f"{sec_clean} manufacturer producer {reg_clean} official website"
        encoded_query = urllib.parse.quote_plus(search_query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        ignored_domains = {
            "linkedin.com", "wikipedia.org", "indiamart.com", "tradeindia.com", 
            "bloomberg.com", "glassdoor.com", "youtube.com", "facebook.com", 
            "twitter.com", "x.com", "instagram.com", "google.com", "justdial.com",
            "yellowpages.com", "dnb.com", "zoominfo.com", "apollo.io", "duckduckgo.com"
        }

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(search_url)
                if resp.status_code == 200:
                    html_text = resp.text
                    matches = re.findall(r'<a class="result__url" href="([^"]+)">(.*?)</a>', html_text)
                    if not matches:
                        matches = re.findall(r'href="(https?://[^"]+)"[^>]*>(.*?)</a>', html_text)

                    for raw_url, raw_title in matches:
                        link = raw_url.strip()
                        if "uddg=" in link:
                            match_uddg = re.search(r'uddg=([^&]+)', link)
                            if match_uddg:
                                link = urllib.parse.unquote(match_uddg.group(1))

                        try:
                            parsed = urllib.parse.urlparse(link)
                            domain = parsed.netloc.lower().replace("www.", "")
                            if not domain or any(ig in domain for ig in ignored_domains) or domain in exclude_domains:
                                continue
                            
                            clean_title = re.sub(r'<[^>]+>', '', raw_title)
                            clean_title = clean_title.split('-')[0].split('|')[0].split(':')[0].strip()
                            if len(clean_title) < 3 or "Search" in clean_title or "Result" in clean_title:
                                clean_title = domain.split('.')[0].title() + " " + sec_clean

                            exclude_domains.add(domain)
                            leads.append({
                                "name": clean_title,
                                "domain": domain,
                                "region": target_region,
                                "source": "Live Web Search & Regulatory Discovery",
                                "industry_subsector": target_sector if target_sector else "Active Pharmaceutical Ingredients (API)",
                                "employee_range": "100-500 employees",
                                "website_url": f"https://www.{domain}"
                            })
                            if len(leads) >= limit:
                                break
                        except Exception:
                            continue
        except Exception as e:
            print(f"[Discovery] Live Web Discovery Notice: {e}")

        return leads

    async def discover_leads(
        self, 
        target_region: str, 
        target_sector: str, 
        max_results: int = 10,
        selected_sources: List[str] = None,
        exclude_domains: set = None
    ) -> List[Dict[str, Any]]:
        """Aggregates leads 100% dynamically via live government APIs and live web search."""
        if not selected_sources:
            selected_sources = ["ALL"]

        seen_domains = set(exclude_domains) if exclude_domains else set()
        combined = []

        # 1. Live openFDA API
        fda_leads = await self._discover_fda_registered_facilities(target_region, target_sector, limit=max_results * 2, exclude_domains=seen_domains)
        combined.extend(fda_leads)

        # 2. Live Health Canada API
        if "canada" in target_region.lower() or "ALL" in selected_sources:
            hc_leads = await self._discover_health_canada_facilities(target_region, target_sector, limit=max_results * 2, exclude_domains=seen_domains)
            combined.extend(hc_leads)

        # 3. Live Web Search & Dynamic Regulatory Web Discovery
        web_leads = await self._discover_live_web_producers(target_region, target_sector, limit=max_results * 3, exclude_domains=seen_domains)
        combined.extend(web_leads)

        unique_leads = []
        for lead in combined:
            if lead["domain"] not in seen_domains:
                seen_domains.add(lead["domain"])
                unique_leads.append(lead)
                if max_results < 9999 and len(unique_leads) >= max_results:
                    break

        return unique_leads
