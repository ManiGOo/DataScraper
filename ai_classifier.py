import os
import json
import httpx
import asyncio
from typing import Dict, Any, List

class AIProspectClassifier:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def _rule_based_fallback_scoring(self, lead_data: Dict[str, Any], crawl_data: Dict[str, Any]) -> Dict[str, Any]:
        """High-precision fallback scorer tailored for Life Science & API Producers."""
        keywords = crawl_data.get("detected_keywords", [])
        subsector = lead_data.get("industry_subsector", "Life Science / API Producer")
        
        score = 70 # High base score for Life Science & API producers
        
        if "ISO 13485" in keywords or "API & Pharma" in subsector:
            score += 15
        if "21 CFR Part 11" in keywords or "FDA Compliance" in keywords:
            score += 10
        if "CAPA / Audit" in keywords:
            score += 5
            
        score = min(score, 98)
        
        drivers = keywords if keywords else ["FDA / EMA QMS Compliance", "API Batch Control & ISO 13485"]
        summary = f"{lead_data.get('name')} is a premium {subsector} organization requiring eQMS automation for {', '.join(drivers[:2])}."

        return {
            "qms_fit_score": score,
            "compliance_drivers": drivers,
            "summary": summary
        }

    async def qualify_lead(self, lead_data: Dict[str, Any], crawl_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates scraped company data using LLM specifically for Life Science & API producers."""
        if not self.groq_api_key:
            return self._rule_based_fallback_scoring(lead_data, crawl_data)

        prompt = f"""
You are an expert Quality Management System (eQMS) Sales Analyst specializing in Life Science Producers, Active Pharmaceutical Ingredient (API) Manufacturers, Medical Devices, and Agri-Biotech developers.
Evaluate this company prospect for selling eQMS software (ISO 13485 / FDA 21 CFR Part 11 / EMA GxP compliance).

Company Name: {lead_data.get('name')}
Sub-sector: {lead_data.get('industry_subsector')}
Region: {lead_data.get('region')}
Detected Compliance Signals: {', '.join(crawl_data.get('detected_keywords', []))}
Scraped Web Text: {crawl_data.get('scraped_text', '')[:1500]}

Assign a QMS Fit Score between 1 and 100 based on their regulatory production requirements.
Return JSON ONLY in this format:
{{
  "qms_fit_score": 92,
  "compliance_drivers": ["FDA 21 CFR Part 11", "ISO 13485", "API Batch Audit Trail"],
  "summary": "Short 2-sentence executive summary of why this Life Science / API producer requires eQMS software."
}}
"""

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.groq_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"}
                    }
                )
                if resp.status_code == 200:
                    res_data = resp.json()
                    content = res_data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return {
                        "qms_fit_score": parsed.get("qms_fit_score", 85),
                        "compliance_drivers": parsed.get("compliance_drivers", ["FDA 21 CFR Part 11", "ISO 13485"]),
                        "summary": parsed.get("summary", "High-value Life Science / API producer requiring eQMS audit readiness.")
                    }
        except Exception as e:
            print(f"[AI Qualification] API Notice ({e}). Using fallback scorer.")

        return self._rule_based_fallback_scoring(lead_data, crawl_data)
