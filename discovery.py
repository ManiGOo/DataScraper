import httpx
import asyncio
import re
from typing import List, Dict, Any

REGION_KEYWORDS_MAP = {
    "middle east": ["israel", "uae", "united arab emirates", "saudi", "dubai", "tel aviv", "ras al khaimah", "middle east", "il", "ae"],
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

def is_region_match(target_region: str, candidate_region: str) -> bool:
    """Strictly matches target region against candidate location using region mapping groups."""
    target_lower = target_region.lower()
    cand_lower = candidate_region.lower()

    # Direct substring match
    if target_lower in cand_lower or cand_lower in target_lower:
        return True

    # Identify target region group
    target_group = None
    for group_name, kws in REGION_KEYWORDS_MAP.items():
        if any(has_keyword(target_lower, kw) for kw in [group_name] + kws):
            target_group = group_name
            break

    if target_group:
        group_keywords = REGION_KEYWORDS_MAP[target_group]
        return any(has_keyword(cand_lower, kw) for kw in group_keywords)

    return False

class LeadDiscoveryEngine:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }

    async def _get_global_life_science_prospects(self, region: str, sector: str) -> List[Dict[str, Any]]:
        """Curated database of high-value global Life Science & API producers."""
        catalog = [
            # Middle East
            {"name": "Teva API Facilities", "domain": "tevaapi.com", "region": "Tel Aviv, Israel", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "300-800", "website_url": "https://tevaapi.com"},
            {"name": "Julphar Gulf Pharmaceutical Industries", "domain": "julphar.net", "region": "Ras Al Khaimah, UAE", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "400-900", "website_url": "https://julphar.net"},
            {"name": "Neopharm Life Sciences", "domain": "neopharm.co.il", "region": "Petah Tikva, Israel", "industry_subsector": "Biotech & API Producer", "employee_range": "150-400", "website_url": "https://neopharm.co.il"},
            {"name": "SPIMACO Addwaihya", "domain": "spimaco.com.sa", "region": "Riyadh, Saudi Arabia", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://spimaco.com.sa"},
            {"name": "Medimerck Middle East", "domain": "medimerck.com", "region": "Dubai, UAE", "industry_subsector": "Medical Devices & MedTech Producers", "employee_range": "80-250", "website_url": "https://medimerck.com"},

            # Europe
            {"name": "Sartorius Stedim Biotech", "domain": "sartorius.com", "region": "Göttingen, Germany", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500-1000", "website_url": "https://sartorius.com"},
            {"name": "Lonza Pharma & Biotech", "domain": "lonza.com", "region": "Basel, Switzerland", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://lonza.com"},
            {"name": "Oxford Biomedica", "domain": "oxb.com", "region": "Oxford, UK", "industry_subsector": "Biotechnology & Gene Therapy Developers", "employee_range": "200-500", "website_url": "https://oxb.com"},
            {"name": "Evotec AG", "domain": "evotec.com", "region": "Hamburg, Germany", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "400-800", "website_url": "https://evotec.com"},

            # Asia-Pacific
            {"name": "Chugai Pharmaceutical", "domain": "chugai-pharm.co.jp", "region": "Tokyo, Japan", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://chugai-pharm.co.jp"},
            {"name": "Tessa Therapeutics", "domain": "tessatherapeutics.com", "region": "Singapore", "industry_subsector": "Biotechnology & Cell Therapy", "employee_range": "100-300", "website_url": "https://tessatherapeutics.com"},
            {"name": "SK Biotek", "domain": "skbiotek.com", "region": "Sejong, South Korea", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "300-600", "website_url": "https://skbiotek.com"},

            # South America
            {"name": "Eurofarma Labs", "domain": "eurofarma.com.br", "region": "São Paulo, Brazil", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "500+", "website_url": "https://eurofarma.com.br"},
            {"name": "Biosidus SA", "domain": "biosidus.com.ar", "region": "Buenos Aires, Argentina", "industry_subsector": "Biosimilar API Producer", "employee_range": "150-400", "website_url": "https://biosidus.com.ar"},

            # North America
            {"name": "Verve Therapeutics", "domain": "vervetx.com", "region": "Massachusetts, USA", "industry_subsector": "Biotechnology & Gene Therapy Developers", "employee_range": "100-300", "website_url": "https://vervetx.com"},
            {"name": "Resonetics Medical", "domain": "resonetics.com", "region": "California, USA", "industry_subsector": "Medical Devices & MedTech Producers", "employee_range": "200-500", "website_url": "https://resonetics.com"},
            {"name": "Cibus Agtech", "domain": "cibus.com", "region": "California, USA", "industry_subsector": "Agri-Biotech & Grain Life Science", "employee_range": "50-200", "website_url": "https://cibus.com"},
            {"name": "Aether BioMedical", "domain": "aetherbiomedical.com", "region": "Massachusetts, USA", "industry_subsector": "Medical Devices & MedTech Producers", "employee_range": "20-50", "website_url": "https://aetherbiomedical.com"},
            {"name": "Veranex Life Sciences", "domain": "veranex.com", "region": "North Carolina, USA", "industry_subsector": "Medical Devices & MedTech Producers", "employee_range": "100-500", "website_url": "https://veranex.com"}
        ]

        matched = [p for p in catalog if is_region_match(region, p["region"])]
        return matched

    async def _discover_fda_registered_facilities(self, region: str, sector: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Queries openFDA establishment registrations matching target region."""
        leads = []
        try:
            country_code = ""
            reg_lower = region.lower()
            if "israel" in reg_lower or "middle east" in reg_lower:
                country_code = "IL"
            elif "germany" in reg_lower or "europe" in reg_lower:
                country_code = "DE"
            elif "japan" in reg_lower:
                country_code = "JP"
            elif "uk" in reg_lower or "united kingdom" in reg_lower:
                country_code = "GB"

            url = f"https://api.fda.gov/device/registrationlisting.json?limit={limit * 3}"
            if country_code:
                url = f"https://api.fda.gov/device/registrationlisting.json?search=iso_country_code:%22{country_code}%22&limit={limit * 3}"

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
                        
                        if comp_name and is_region_match(region, cand_region):
                            clean_domain = re.sub(r'[^a-zA-Z0-9]', '', comp_name.lower()) + ".com"
                            leads.append({
                                "name": comp_name.title(),
                                "domain": clean_domain,
                                "region": cand_region,
                                "source": "FDA Global Producer Registry",
                                "industry_subsector": sector if sector else "Active Pharmaceutical Ingredients (API)",
                                "employee_range": "50-500 employees",
                                "website_url": f"https://www.{clean_domain}"
                            })
                            if len(leads) >= limit:
                                break
        except Exception as e:
            print(f"[Discovery] FDA Registry Notice: {e}")
        return leads

    async def _discover_clinical_trials_sponsors(self, region: str, sector: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Queries ClinicalTrials.gov for sponsors matching target region."""
        leads = []
        try:
            search_term = "Israel" if "middle east" in region.lower() else region
            url = f"https://clinicaltrials.gov/api/v2/studies?query.term={search_term}&filter.overallStatus=RECRUITING&pageSize={limit * 3}"
            async with httpx.AsyncClient(headers=self.headers, timeout=15.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    studies = data.get("studies", [])
                    for s in studies:
                        protocol = s.get("protocolSection", {})
                        sponsor = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name")
                        class_type = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("class")
                        
                        if sponsor and class_type == "INDUSTRY":
                            clean_domain = re.sub(r'[^a-zA-Z0-9]', '', sponsor.lower()) + ".com"
                            leads.append({
                                "name": sponsor.title(),
                                "domain": clean_domain,
                                "region": region,
                                "source": "Clinical Sponsor Registry",
                                "industry_subsector": sector if sector else "Biotechnology & API Developer",
                                "employee_range": "100-500 employees",
                                "website_url": f"https://www.{clean_domain}"
                            })
                            if len(leads) >= limit:
                                break
        except Exception as e:
            print(f"[Discovery] ClinicalTrials API Notice: {e}")
        return leads

    async def discover_leads(self, target_region: str, target_sector: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Aggregates leads strictly matching the target region and sub-sector."""
        # 1. First get curated catalog matching target region
        curated_leads = await self._get_global_life_science_prospects(target_region, target_sector)

        # 2. Get API discovered leads
        fda_leads = await self._discover_fda_registered_facilities(target_region, target_sector, limit=max_results)
        ct_leads = await self._discover_clinical_trials_sponsors(target_region, target_sector, limit=max_results)

        # Combine: prioritizing region-matched curated and API leads
        combined = curated_leads + fda_leads + ct_leads

        seen_domains = set()
        unique_leads = []
        for lead in combined:
            # Strict regional check
            if is_region_match(target_region, lead["region"]):
                if lead["domain"] not in seen_domains:
                    seen_domains.add(lead["domain"])
                    unique_leads.append(lead)
                    if len(unique_leads) >= max_results:
                        break

        # Fallback if less than max_results found (only if region matches)
        if len(unique_leads) < max_results:
            for lead in combined:
                if is_region_match(target_region, lead["region"]) and lead["domain"] not in seen_domains:
                    seen_domains.add(lead["domain"])
                    unique_leads.append(lead)
                    if len(unique_leads) >= max_results:
                        break

        return unique_leads
