import httpx
import asyncio
import re
from typing import List, Dict, Any

GLOBAL_REGION_MAPPING = {
    "North America": ["US", "CA"],
    "Europe": ["DE", "GB", "CH", "FR", "IE"],
    "Middle East": ["AE", "IL", "SA"],
    "Asia-Pacific": ["JP", "SG", "KR", "CN"],
    "South America": ["BR", "AR"]
}

class LeadDiscoveryEngine:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }

    async def _discover_fda_registered_facilities(self, region: str, sector: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Queries openFDA establishment registrations for global life science & API producers."""
        leads = []
        try:
            # Query FDA registration for global producers
            url = f"https://api.fda.gov/device/registrationlisting.json?limit={limit * 2}"
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
                        
                        if comp_name:
                            clean_domain = re.sub(r'[^a-zA-Z0-9]', '', comp_name.lower()) + ".com"
                            leads.append({
                                "name": comp_name.title(),
                                "domain": clean_domain,
                                "region": f"{city}, {country}".strip(", "),
                                "source": "FDA Global Producer Registry",
                                "industry_subsector": sector if sector else "Life Science / API Producer",
                                "employee_range": "50-500 employees",
                                "website_url": f"https://www.{clean_domain}"
                            })
                            if len(leads) >= limit:
                                break
        except Exception as e:
            print(f"[Discovery] FDA Global Registry Notice: {e}")
        return leads

    async def _discover_clinical_trials_sponsors(self, region: str, sector: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Queries ClinicalTrials.gov for active biopharma & life science developers."""
        leads = []
        try:
            url = f"https://clinicaltrials.gov/api/v2/studies?query.term={region}&filter.overallStatus=RECRUITING&pageSize={limit * 2}"
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
                                "source": "Global Clinical Sponsor Registry",
                                "industry_subsector": sector if sector else "Biotech & API Developer",
                                "employee_range": "100-500 employees",
                                "website_url": f"https://www.{clean_domain}"
                            })
                            if len(leads) >= limit:
                                break
        except Exception as e:
            print(f"[Discovery] ClinicalTrials API Notice: {e}")
        return leads

    async def _get_global_life_science_prospects(self, region: str, sector: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Curated high-paying global Life Science, API, MedTech, and Grain/Agri-Biotech producers."""
        global_prospects = [
            # North America
            {"name": "Verve Therapeutics", "domain": "vervetx.com", "region": "Massachusetts, USA", "industry_subsector": "Biotech & API Developer", "employee_range": "100-300", "website_url": "https://vervetx.com"},
            {"name": "Resonetics Medical", "domain": "resonetics.com", "region": "California, USA", "industry_subsector": "MedTech / Device Producer", "employee_range": "200-500", "website_url": "https://resonetics.com"},
            {"name": "Cibus Agtech", "domain": "cibus.com", "region": "California, USA", "industry_subsector": "Agri-Biotech & Grain Life Science", "employee_range": "50-200", "website_url": "https://cibus.com"},
            # Europe
            {"name": "Sartorius Stedim Biotech", "domain": "sartorius.com", "region": "Göttingen, Germany", "industry_subsector": "API & Bioprocess Equipment", "employee_range": "500-1000", "website_url": "https://sartorius.com"},
            {"name": "Lonza Pharma & Biotech", "domain": "lonza.com", "region": "Basel, Switzerland", "industry_subsector": "API & Pharma Producer", "employee_range": "500+", "website_url": "https://lonza.com"},
            {"name": "Oxford Biomedica", "domain": "oxb.com", "region": "Oxford, UK", "industry_subsector": "Gene Therapy / API Producer", "employee_range": "200-500", "website_url": "https://oxb.com"},
            # Middle East
            {"name": "Teva API Facilities", "domain": "tevaapi.com", "region": "Tel Aviv, Israel", "industry_subsector": "Active Pharmaceutical Ingredients (API)", "employee_range": "300-800", "website_url": "https://tevaapi.com"},
            {"name": "Julphar Gulf Pharma", "domain": "julphar.net", "region": "Ras Al Khaimah, UAE", "industry_subsector": "Pharmaceutical Producer", "employee_range": "400-900", "website_url": "https://julphar.net"},
            # Asia-Pacific
            {"name": "Chugai Pharmaceutical", "domain": "chugai-pharm.co.jp", "region": "Tokyo, Japan", "industry_subsector": "Pharma & API Developer", "employee_range": "500+", "website_url": "https://chugai-pharm.co.jp"},
            {"name": "Tessa Therapeutics", "domain": "tessatherapeutics.com", "region": "Singapore", "industry_subsector": "Cell Therapy Producer", "employee_range": "100-300", "website_url": "https://tessatherapeutics.com"},
            # South America
            {"name": "Eurofarma Labs", "domain": "eurofarma.com.br", "region": "São Paulo, Brazil", "industry_subsector": "API & Medical Producer", "employee_range": "500+", "website_url": "https://eurofarma.com.br"},
            {"name": "Biosidus SA", "domain": "biosidus.com.ar", "region": "Buenos Aires, Argentina", "industry_subsector": "Biosimilar API Producer", "employee_range": "150-400", "website_url": "https://biosidus.com.ar"}
        ]

        # Filter by region or sector keywords if possible
        filtered = [
            p for p in global_prospects 
            if region.lower() in p["region"].lower() 
            or any(part.lower() in p["region"].lower() for part in region.split())
            or sector.lower() in p["industry_subsector"].lower()
        ]
        return filtered[:limit] if filtered else global_prospects[:limit]

    async def discover_leads(self, target_region: str, target_sector: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Aggregates high-value global Life Science, API, and MedTech producer prospects."""
        fda_leads = await self._discover_fda_registered_facilities(target_region, target_sector, limit=max_results)
        ct_leads = await self._discover_clinical_trials_sponsors(target_region, target_sector, limit=max_results)
        curated_leads = await self._get_global_life_science_prospects(target_region, target_sector, limit=max_results)

        combined = fda_leads + ct_leads + curated_leads

        seen_domains = set()
        unique_leads = []
        for lead in combined:
            if lead["domain"] not in seen_domains:
                seen_domains.add(lead["domain"])
                unique_leads.append(lead)
                if len(unique_leads) >= max_results:
                    break

        return unique_leads
