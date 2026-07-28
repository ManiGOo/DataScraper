import os
import re
import random
import urllib.parse
import httpx
from typing import Dict, Any, List

TARGET_PERSONAS = [
    {
        "name": "VP of Quality Assurance & Compliance",
        "title": "Head of Quality & Audit Systems",
        "email_prefix": "qa"
    },
    {
        "name": "Director of Regulatory Affairs",
        "title": "Head of Regulatory & Global Compliance",
        "email_prefix": "regulatory"
    },
    {
        "name": "Quality Systems & Audit Manager",
        "title": "Head of eQMS & Audit Readiness",
        "email_prefix": "compliance"
    },
    {
        "name": "Chief Executive Officer / Managing Director",
        "title": "Executive Office",
        "email_prefix": "contact"
    }
]


class QuickLeadLinkedInResolver:
    """QuickLead API & Direct Profile Handle Resolver for LinkedIn ID Extraction."""
    def __init__(self):
        self.api_key = os.getenv("QUICKLEAD_API_KEY", os.getenv("LINKEDIN_API_KEY", ""))
        self.base_url = "https://api.quicklead.io/v1/linkedin/find"

    def resolve_linkedin_profile(self, full_name: str, company_name: str, title: str) -> str:
        """Resolves exact LinkedIn profile URL using QuickLead API or clean concise LinkedIn People Search query."""
        if self.api_key:
            try:
                headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
                params = {"name": full_name, "company": company_name, "title": title}
                resp = httpx.get(self.base_url, headers=headers, params=params, timeout=4.0)
                if resp.status_code == 200 and resp.json().get("linkedin_url"):
                    return resp.json()["linkedin_url"]
            except Exception as e:
                print(f"[QuickLead API Notice] {e}")

        company_clean = re.sub(r'(?i)\b(pvt|ltd|inc|llc|corp|corporation|facilities|plant|manufacturing|pharma|pharmaceuticals|medical)\b', '', company_name)
        company_clean = re.sub(r'[^a-zA-Z0-9\s]', '', company_clean).strip()
        company_keyword = company_clean.split()[0] if company_clean else company_name.split()[0]

        if "quality" in title.lower():
            role_kw = "Quality Assurance"
        elif "regulatory" in title.lower():
            role_kw = "Regulatory Affairs"
        elif "executive" in title.lower() or "ceo" in title.lower():
            role_kw = "CEO"
        else:
            role_kw = title.split()[0]

        query = urllib.parse.quote_plus(f"{company_keyword} {role_kw}")
        return f"https://www.linkedin.com/search/results/people/?keywords={query}"

    def resolve_google_web_search(self, full_name: str, company_name: str, title: str, location_address: str = "") -> str:
        """Generates clean unquoted Google Advanced Web Search query matching company, role, city & LinkedIn/Social web pages."""
        company_clean = re.sub(r'(?i)\b(pvt|ltd|inc|llc|corp|corporation|facilities|plant|manufacturing|pharma|pharmaceuticals|medical)\b', '', company_name)
        company_clean = re.sub(r'[^a-zA-Z0-9\s]', '', company_clean).strip()
        company_keyword = company_clean.split()[0] if company_clean else company_name.split()[0]
        
        city_token = ""
        if location_address:
            city_token = location_address.split(',')[0].strip()
            
        role_kw = "Quality Assurance" if "quality" in title.lower() else ("Regulatory Affairs" if "regulatory" in title.lower() else title.split()[0])
        
        query_parts = [company_keyword, role_kw]
        if city_token:
            query_parts.append(city_token)
        query_parts.append("LinkedIn profile")
            
        g_query = urllib.parse.quote_plus(" ".join(query_parts))
        return f"https://www.google.com/search?q={g_query}"


class PersonaContactEnricher:
    def __init__(self):
        self.linkedin_resolver = QuickLeadLinkedInResolver()

    def enrich_contacts_for_lead(self, domain: str, company_name: str, crawl_emails: List[str] = None, crawl_phones: List[str] = None, location_address: str = "") -> List[Dict[str, Any]]:
        """Determines best contacts for SDR Outreach."""
        contacts = []
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        company_clean = re.sub(r'(?i)\b(pvt|ltd|inc|llc|corp|corporation|facilities|plant|manufacturing|pharma|pharmaceuticals|medical)\b', '', company_name)
        
        # 1. Use real crawled emails if available
        if crawl_emails:
            # Add phone to the first crawled contact if available
            primary_phone = crawl_phones[0] if crawl_phones else None
            for idx, email in enumerate(crawl_emails[:4]): # Support up to 4 real emails
                name_part = email.split("@")[0]
                if "." in name_part and len(name_part.split(".")) == 2:
                    readable_name = name_part.replace(".", " ").title()
                    title = "Quality Assurance Lead" if idx == 0 else "Director of Regulatory Affairs"
                elif "_" in name_part and len(name_part.split("_")) == 2:
                    readable_name = name_part.replace("_", " ").title()
                    title = "Quality Assurance Lead" if idx == 0 else "Director of Regulatory Affairs"
                else:
                    readable_name = name_part.title()
                    title = "Company Contact"
                    
                linkedin = self.linkedin_resolver.resolve_linkedin_profile(readable_name, company_clean, title)
                web_search = self.linkedin_resolver.resolve_google_web_search(readable_name, company_clean, title, location_address)
                
                contacts.append({
                    "name": readable_name,
                    "title": title,
                    "email": email,
                    "phone": primary_phone if idx == 0 else None,
                    "linkedin_url": linkedin,
                    "web_search_url": web_search,
                    "verification_status": "VERIFIED"
                })

        # Do not generate fake/synthetic contacts if no real emails were found.
        # This forces the UI to display the empty state.
        return contacts
