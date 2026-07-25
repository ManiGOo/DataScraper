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
        """High-precision fallback scorer when LLM API key is absent."""
        keywords = crawl_data.get("detected_keywords", [])
        subsector = lead_data.get("industry_subsector", "Life Science")
        
        score = 60 # Base score for Life Science SMBs
        
        if "ISO 13485" in keywords:
            score += 20
        if "21 CFR Part 11" in keywords:
            score += 15
        if "FDA Compliance" in keywords:
            score += 10
        if "CAPA / Audit" in keywords:
            score += 10
            
        score = min(score, 98)
        
        drivers = keywords if keywords else ["Regulatory Compliance", "Quality Audit Readiness"]
        summary = f"{lead_data.get('name')} is a {subsector} organization requiring eQMS automation for {', '.join(drivers[:2])}."

        return {
            "qms_fit_score": score,
            "compliance_drivers": drivers,
            "summary": summary
        }

    async def qualify_lead(self, lead_data: Dict[str, Any], crawl_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates scraped company data using LLM to assign QMS fit score and compliance drivers."""
        if not self.groq_api_key:
            return self._rule_based_fallback_scoring(lead_data, crawl_data)

        prompt = f"""
You are an expert Medical Device & BioTech Quality Management System (eQMS) Sales Analyst.
Evaluate this company prospect for selling eQMS software (ISO 13485 / 21 CFR Part 11 / FDA compliance).

Company Name: {lead_data.get('name')}
Sub-sector: {lead_data.get('industry_subsector')}
Region: {lead_data.get('region')}
Detected Compliance Signals: {', '.join(crawl_data.get('detected_keywords', []))}
Scraped Web Text: {crawl_data.get('scraped_text', '')[:1500]}

Assign a QMS Fit Score between 1 and 100 based on regulatory requirements.
Return JSON ONLY in this format:
{{
  "qms_fit_score": 88,
  "compliance_drivers": ["ISO 13485", "21 CFR Part 11", "Audit Prep"],
  "summary": "Short 2-sentence executive summary of why they need QMS software."
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
                        "qms_fit_score": parsed.get("qms_fit_score", 75),
                        "compliance_drivers": parsed.get("compliance_drivers", ["ISO 13485"]),
                        "summary": parsed.get("summary", "Regulated life science company with active eQMS requirements.")
                    }
        except Exception as e:
            print(f"[AI Qualification] API Notice ({e}). Using fallback scorer.")

        return self._rule_based_fallback_scoring(lead_data, crawl_data)
