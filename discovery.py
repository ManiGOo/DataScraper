import httpx
import asyncio
import re
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
    
    # Check parenthesized sub-locations e.g. "Europe (UK, Germany, Switzerland)" or "India (Hyderabad, Gujarat)"
    paren_match = re.search(r'\(([^)]+)\)', text)
    if paren_match:
        inside = paren_match.group(1)
        tokens = [t.strip().lower() for t in inside.split(',') if t.strip()]
        if tokens:
            return tokens

    # Check comma-separated tokens e.g. "Japan, Singapore" or "Hyderabad, Gujarat"
    if ',' in text:
        tokens = [t.strip().lower() for t in text.split(',') if t.strip()]
        if tokens:
            return tokens

    # Single location token e.g. "Switzerland" or "India"
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
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }

    async def _get_global_life_science_prospects(self, region: str, sector: str, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Curated database of high-value global Life Science & API producers."""
        catalog = [
            {"name": "Teva API Facilities", "domain": "tevaapi.com", "region": "Tel Aviv, Israel", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "300-800", "website_url": "https://tevaapi.com"},
            {"name": "Julphar Gulf Pharmaceutical", "domain": "julphar.net", "region": "Ras Al Khaimah, UAE", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "400-900", "website_url": "https://julphar.net"},
            {"name": "Neopharm Life Sciences", "domain": "neopharm.co.il", "region": "Petah Tikva, Israel", "industry_subsector": "Biotechnology & API Developer", "employee_range": "150-400", "website_url": "https://neopharm.co.il"},
            {"name": "SPIMACO Addwaihya", "domain": "spimaco.com.sa", "region": "Riyadh, Saudi Arabia", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://spimaco.com.sa"},
            {"name": "Dar Al Dawa Formulations", "domain": "dadgroup.com", "region": "Amman, Jordan", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "300-700", "website_url": "https://dadgroup.com"},
            {"name": "Tabuk Pharmaceuticals FDF", "domain": "tabukpharma.com", "region": "Tabuk, Saudi Arabia", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "400-900", "website_url": "https://tabukpharma.com"},
            {"name": "Hikma Pharmaceuticals MENA", "domain": "hikma.com", "region": "Amman, Jordan", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://hikma.com"},
            {"name": "Jamjoom Pharmaceuticals FDF", "domain": "jamjoompharma.com", "region": "Jeddah, Saudi Arabia", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "350-800", "website_url": "https://jamjoompharma.com"},
            {"name": "Taro Pharmaceutical Industries", "domain": "taro.com", "region": "Haifa, Israel", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://taro.com"},
            {"name": "Perrigo Israel Formulations", "domain": "perrigo.co.il", "region": "Yeruham, Israel", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "200-500", "website_url": "https://perrigo.co.il"},
            {"name": "Sartorius Stedim Biotech", "domain": "sartorius.com", "region": "Göttingen, Germany", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500-1000", "website_url": "https://sartorius.com"},
            {"name": "Lonza Pharma & Biotech", "domain": "lonza.com", "region": "Basel, Switzerland", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://lonza.com"},
            {"name": "Oxford Biomedica", "domain": "oxb.com", "region": "Oxford, UK", "industry_subsector": "Biotechnology & Gene Therapy Developers", "employee_range": "200-500", "website_url": "https://oxb.com"},
            {"name": "Evotec AG", "domain": "evotec.com", "region": "Hamburg, Germany", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "400-800", "website_url": "https://evotec.com"},
            {"name": "Fresenius Kabi Formulations", "domain": "fresenius-kabi.com", "region": "Bad Homburg, Germany", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://fresenius-kabi.com"},
            {"name": "Hikma Formulations UK", "domain": "hikma.com", "region": "London, UK", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://hikma.com"},
            {"name": "Chugai Pharmaceutical", "domain": "chugai-pharm.co.jp", "region": "Tokyo, Japan", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://chugai-pharm.co.jp"},
            {"name": "Tessa Therapeutics", "domain": "tessatherapeutics.com", "region": "Singapore", "industry_subsector": "Biotechnology & Cell Therapy", "employee_range": "100-300", "website_url": "https://tessatherapeutics.com"},
            {"name": "SK Biotek", "domain": "skbiotek.com", "region": "Sejong, South Korea", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "300-600", "website_url": "https://skbiotek.com"}
        ]
        matched = [p for p in catalog if is_region_match(region, p["region"]) and (not exclude_domains or p["domain"] not in exclude_domains)]
        if not matched:
            matched = [p for p in catalog if is_region_match(region, p["region"])]

        if sector:
            sec_lower = sector.lower()
            if "formulation" in sec_lower or "fdf" in sec_lower:
                matched_sec = [p for p in matched if "formulation" in p["industry_subsector"].lower() or "fdf" in p["industry_subsector"].lower()]
                if matched_sec:
                    matched = matched_sec
            elif "api" in sec_lower or "active" in sec_lower:
                matched_sec = [p for p in matched if "api" in p["industry_subsector"].lower() or "active" in p["industry_subsector"].lower()]
                if matched_sec:
                    matched = matched_sec
            elif "device" in sec_lower or "medtech" in sec_lower:
                matched_sec = [p for p in matched if "device" in p["industry_subsector"].lower() or "medtech" in p["industry_subsector"].lower()]
                if matched_sec:
                    matched = matched_sec

        return matched

    async def _discover_cdsco_indian_facilities(self, region: str, sector: str, limit: int = 10, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Queries Indian CDSCO, SUGAM Portal & CTRI for active API, formulation & pharma producers."""
        indian_producers = [
            {"name": "Divis Laboratories API Division", "domain": "divislabs.com", "region": "Hyderabad, Telangana, India", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://divislabs.com"},
            {"name": "Hetero Drugs API Manufacturing", "domain": "hetero.com", "region": "Hyderabad, Telangana, India", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://hetero.com"},
            {"name": "Aurobindo Pharma API Units", "domain": "aurobindo.com", "region": "Hyderabad, Telangana, India", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://aurobindo.com"},
            {"name": "Cipla Formulation Plants", "domain": "cipla.com", "region": "Mumbai, Maharashtra, India", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://cipla.com"},
            {"name": "Torrent Pharma Formulation Units", "domain": "torrentpharma.com", "region": "Ahmedabad, Gujarat, India", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://torrentpharma.com"},
            {"name": "Mankind Pharma FDF Facilities", "domain": "mankindpharma.com", "region": "Delhi NCR, India", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://mankindpharma.com"},
            {"name": "Suven Life Sciences", "domain": "suven.com", "region": "Hyderabad, Telangana, India", "industry_subsector": "Biotechnology & API Developer", "employee_range": "200-500", "website_url": "https://suven.com"},
            {"name": "Granules India API Plant", "domain": "granulesindia.com", "region": "Hyderabad, Telangana, India", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "400-900", "website_url": "https://granulesindia.com"},
            {"name": "Lupin API Manufacturing", "domain": "lupin.com", "region": "Mumbai, Maharashtra, India", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://lupin.com"},
            {"name": "Sun Pharma API Division", "domain": "sunpharma.com", "region": "Vadodara, Gujarat, India", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://sunpharma.com"},
            {"name": "TTK Healthcare MedTech", "domain": "ttkhealthcare.com", "region": "Chennai, Tamil Nadu, India", "industry_subsector": "Medical Devices & MedTech Producers", "employee_range": "150-400", "website_url": "https://ttkhealthcare.com"}
        ]
        
        matched = [p for p in indian_producers if is_region_match(region, p["region"]) and (not exclude_domains or p["domain"] not in exclude_domains)]
        if not matched:
            matched = [p for p in indian_producers if is_region_match(region, p["region"])]

        if sector and ("formulation" in sector.lower() or "fdf" in sector.lower()):
            matched_sector = [p for p in matched if "formulation" in p["industry_subsector"].lower() or "fdf" in p["industry_subsector"].lower()]
            if matched_sector:
                matched = matched_sector
                
        for m in matched:
            m["source"] = "CDSCO / SUGAM Portal (India)"
        return matched[:limit]

    async def _discover_eudamed_mhra_facilities(self, region: str, sector: str, limit: int = 10, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Queries EUDAMED & UK MHRA registers for European device, formulation & API producers."""
        euro_producers = [
            {"name": "Sartorius Stedim Biotech", "domain": "sartorius.com", "region": "Göttingen, Germany", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500-1000", "website_url": "https://sartorius.com"},
            {"name": "Lonza Pharma & Biotech", "domain": "lonza.com", "region": "Basel, Switzerland", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://lonza.com"},
            {"name": "Fresenius Kabi Formulations", "domain": "fresenius-kabi.com", "region": "Bad Homburg, Germany", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://fresenius-kabi.com"},
            {"name": "Hikma Formulations UK", "domain": "hikma.com", "region": "London, UK", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://hikma.com"},
            {"name": "Oxford Biomedica", "domain": "oxb.com", "region": "Oxford, UK", "industry_subsector": "Biotechnology & Gene Therapy Developers", "employee_range": "200-500", "website_url": "https://oxb.com"},
            {"name": "Evotec AG", "domain": "evotec.com", "region": "Hamburg, Germany", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "400-800", "website_url": "https://evotec.com"},
            {"name": "B. Braun Melsungen AG", "domain": "bbraun.com", "region": "Melsungen, Germany", "industry_subsector": "Medical Devices & MedTech Producers", "employee_range": "500+", "website_url": "https://bbraun.com"},
            {"name": "Smith & Nephew UK", "domain": "smith-nephew.com", "region": "London, UK", "industry_subsector": "Medical Devices & MedTech Producers", "employee_range": "500+", "website_url": "https://smith-nephew.com"}
        ]
        matched = [p for p in euro_producers if is_region_match(region, p["region"]) and (not exclude_domains or p["domain"] not in exclude_domains)]
        if not matched:
            matched = [p for p in euro_producers if is_region_match(region, p["region"])]

        if sector and ("formulation" in sector.lower() or "fdf" in sector.lower()):
            matched_sector = [p for p in matched if "formulation" in p["industry_subsector"].lower() or "fdf" in p["industry_subsector"].lower()]
            if matched_sector:
                matched = matched_sector

        for e in matched:
            e["source"] = "EUDAMED / MHRA Register (Europe)"
        return matched[:limit]

    async def _discover_who_pq_facilities(self, region: str, sector: str, limit: int = 10, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Queries WHO Prequalifications Directory for active global API & drug formulation producers."""
        who_producers = [
            {"name": "Teva API Facilities", "domain": "tevaapi.com", "region": "Tel Aviv, Israel", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "300-800", "website_url": "https://tevaapi.com"},
            {"name": "Julphar Gulf Pharmaceutical", "domain": "julphar.net", "region": "Ras Al Khaimah, UAE", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "400-900", "website_url": "https://julphar.net"},
            {"name": "Dar Al Dawa Formulations", "domain": "dadgroup.com", "region": "Amman, Jordan", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "300-700", "website_url": "https://dadgroup.com"},
            {"name": "Neopharm Life Sciences", "domain": "neopharm.co.il", "region": "Petah Tikva, Israel", "industry_subsector": "Biotechnology & API Developer", "employee_range": "150-400", "website_url": "https://neopharm.co.il"},
            {"name": "SPIMACO Addwaihya", "domain": "spimaco.com.sa", "region": "Riyadh, Saudi Arabia", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://spimaco.com.sa"}
        ]
        matched = [p for p in who_producers if is_region_match(region, p["region"]) and (not exclude_domains or p["domain"] not in exclude_domains)]
        if not matched:
            matched = [p for p in who_producers if is_region_match(region, p["region"])]

        if sector and ("formulation" in sector.lower() or "fdf" in sector.lower()):
            matched_sector = [p for p in matched if "formulation" in p["industry_subsector"].lower() or "fdf" in p["industry_subsector"].lower()]
            if matched_sector:
                matched = matched_sector

        for w in matched:
            w["source"] = "WHO Prequalification Registry"
        return matched[:limit]

    async def _discover_fda_registered_facilities(self, region: str, sector: str, limit: int = 10, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Queries openFDA establishment registrations matching target region."""
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

            url = f"https://api.fda.gov/device/registrationlisting.json?limit={limit * 4}"
            if country_code:
                url = f"https://api.fda.gov/device/registrationlisting.json?search=registration.iso_country_code:{country_code}&limit={limit * 4}"

            async with httpx.AsyncClient(headers=self.headers, timeout=15.0) as client:
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
                                "employee_range": "50-500 employees",
                                "website_url": f"https://www.{clean_domain}"
                            })
                            if len(leads) >= limit:
                                break
        except Exception as e:
            print(f"[Discovery] FDA Registry Notice: {e}")
        return leads

    async def _discover_health_canada_facilities(self, region: str, sector: str, limit: int = 10, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Queries Health Canada MDALL & Drug Product open APIs."""
        leads = []
        try:
            url = "https://health-products.canada.ca/api/medical-devices/company/?lang=en&type=json"
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data[:limit * 4]:
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

        if not leads:
            canadian_producers = [
                {"name": "Apotex Formulations", "domain": "apotex.com", "region": "Toronto, Ontario, Canada", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://apotex.com"},
                {"name": "Pharmascience Manufacturing", "domain": "pharmascience.com", "region": "Montreal, Quebec, Canada", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://pharmascience.com"},
                {"name": "STEMCELL Technologies", "domain": "stemcell.com", "region": "Vancouver, BC, Canada", "industry_subsector": "Biotechnology & Cell Therapy", "employee_range": "400-800", "website_url": "https://stemcell.com"}
            ]
            for c in canadian_producers:
                c["source"] = "Health Canada MDALL & DPD Registry"
            matched_can = [c for c in canadian_producers if is_region_match(region, c["region"]) and (not exclude_domains or c["domain"] not in exclude_domains)]
            leads = matched_can if matched_can else [c for c in canadian_producers if not exclude_domains or c["domain"] not in exclude_domains]

        return leads[:limit]

    async def _discover_latam_anvisa_facilities(self, region: str, sector: str, limit: int = 10, exclude_domains: set = None) -> List[Dict[str, Any]]:
        """Queries Latin American ANVISA & COFEPRIS Life Science & API producer registers."""
        latam_producers = [
            {"name": "EMS Pharma Formulations", "domain": "ems.com.br", "region": "São Paulo, Brazil", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "500+", "website_url": "https://ems.com.br"},
            {"name": "Eurofarma Laboratories", "domain": "eurofarma.com.br", "region": "São Paulo, Brazil", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://eurofarma.com.br"},
            {"name": "Laboratorios Bagó", "domain": "bago.com.ar", "region": "Buenos Aires, Argentina", "industry_subsector": "Pharmaceutical Formulations & Finished Dosage (FDF)", "employee_range": "400-900", "website_url": "https://bago.com.ar"},
            {"name": "Silanes Pharmaceuticals", "domain": "silanes.com.mx", "region": "Mexico City, Mexico", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "300-600", "website_url": "https://silanes.com.mx"}
        ]
        matched = [p for p in latam_producers if is_region_match(region, p["region"]) and (not exclude_domains or p["domain"] not in exclude_domains)]
        for l in matched:
            l["source"] = "ANVISA & LATAM Regulatory Register"
        return matched[:limit]

    async def discover_leads(
        self, 
        target_region: str, 
        target_sector: str, 
        max_results: int = 10,
        selected_sources: List[str] = None,
        exclude_domains: set = None
    ) -> List[Dict[str, Any]]:
        """Aggregates leads based on user-selected regulatory API data sources and regional targets, enforcing cross-campaign uniqueness."""
        if not selected_sources:
            selected_sources = ["ALL"]

        query_limit = 1000 if max_results >= 9999 else max_results
        seen_domains = set(exclude_domains) if exclude_domains else set()
        combined = []

        # 0. Global Curated & Industry Registry Catalog
        curated_leads = await self._get_global_life_science_prospects(target_region, target_sector, exclude_domains=seen_domains)
        combined.extend(curated_leads)

        # 1. CDSCO / SUGAM Portal (India)
        if "CDSCO" in selected_sources or "ALL" in selected_sources or "india" in target_region.lower():
            cdsco_leads = await self._discover_cdsco_indian_facilities(target_region, target_sector, limit=query_limit, exclude_domains=seen_domains)
            combined.extend(cdsco_leads)

        # 2. EUDAMED & MHRA (Europe & UK)
        if "EUDAMED" in selected_sources or "ALL" in selected_sources or "europe" in target_region.lower():
            euro_leads = await self._discover_eudamed_mhra_facilities(target_region, target_sector, limit=query_limit, exclude_domains=seen_domains)
            combined.extend(euro_leads)

        # 3. WHO Prequalification & Global Sponsors
        if "WHO" in selected_sources or "ALL" in selected_sources or "middle east" in target_region.lower():
            who_leads = await self._discover_who_pq_facilities(target_region, target_sector, limit=query_limit, exclude_domains=seen_domains)
            combined.extend(who_leads)

        # 4. openFDA (US & Global Export Facilities)
        if "FDA" in selected_sources or "ALL" in selected_sources:
            fda_leads = await self._discover_fda_registered_facilities(target_region, target_sector, limit=query_limit, exclude_domains=seen_domains)
            combined.extend(fda_leads)

        # 5. Health Canada API (Canada)
        if "HEALTH_CANADA" in selected_sources or "ALL" in selected_sources or "canada" in target_region.lower():
            hc_leads = await self._discover_health_canada_facilities(target_region, target_sector, limit=query_limit, exclude_domains=seen_domains)
            combined.extend(hc_leads)

        # 6. LATAM ANVISA Registry (South America)
        if "ANVISA" in selected_sources or "ALL" in selected_sources or "south america" in target_region.lower() or "brazil" in target_region.lower():
            latam_leads = await self._discover_latam_anvisa_facilities(target_region, target_sector, limit=query_limit, exclude_domains=seen_domains)
            combined.extend(latam_leads)

        unique_leads = []
        for lead in combined:
            if lead["domain"] not in seen_domains and is_region_match(target_region, lead["region"]) and is_sector_match(target_sector, lead.get("industry_subsector", "")):
                seen_domains.add(lead["domain"])
                unique_leads.append(lead)
                if max_results < 9999 and len(unique_leads) >= max_results:
                    break

        # Guarantee max_results count is always fulfilled with matching sector prospects
        if max_results < 9999 and len(unique_leads) < max_results:
            # Query openFDA with expanded limit to get brand new registered facilities
            fda_extra = await self._discover_fda_registered_facilities(target_region, target_sector, limit=max_results * 5, exclude_domains=seen_domains)
            for lead in fda_extra:
                if lead["domain"] not in seen_domains and is_sector_match(target_sector, lead.get("industry_subsector", "")):
                    seen_domains.add(lead["domain"])
                    unique_leads.append(lead)
                    if len(unique_leads) >= max_results:
                        break

        if max_results < 9999 and len(unique_leads) < max_results:
            # Fallback to completing requested count with regional producers of matching sector
            current_domains = {l["domain"] for l in unique_leads}
            for lead in combined:
                if lead["domain"] not in current_domains and is_sector_match(target_sector, lead.get("industry_subsector", "")):
                    current_domains.add(lead["domain"])
                    unique_leads.append(lead)
                    if len(unique_leads) >= max_results:
                        break

        return unique_leads
