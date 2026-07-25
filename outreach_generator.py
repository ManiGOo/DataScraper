import os
import json
import httpx
from typing import Dict, Any, List

class OutreachCopyGenerator:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def _rule_based_sequences(self, contact: Dict[str, Any], company: Dict[str, Any]) -> List[Dict[str, Any]]:
        comp_name = company.get("name", "your team")
        subsector = company.get("industry_subsector", "life science")
        first_name = contact.get("name", "").split()[0] if contact.get("name") else "there"
        title = contact.get("title", "Quality Leader")

        return [
            {
                "step_number": 1,
                "subject": f"Automating eQMS compliance for {comp_name}?",
                "personalized_hook": f"Noticed {comp_name}'s work in {subsector} out of {company.get('region', 'your region')}.",
                "body_text": f"Hi {first_name},\n\nNoticed {comp_name}'s recent work in {subsector}. As {title}, scaling quality workflows while maintaining ISO 13485 and FDA 21 CFR Part 11 readiness can consume 30%+ of your QA team's week in manual paperwork.\n\nOur modern eQMS software automates document control, CAPA tracking, and audit trails so your team stays audit-ready 24/7 without spreadsheet overhead.\n\nOpen to a brief 10-minute preview this Thursday?\n\nBest,\nAI SDR Team"
            },
            {
                "step_number": 2,
                "subject": f"Re: Streamlining ISO 13485 audits at {comp_name}",
                "personalized_hook": "Reducing audit prep time by 70% for MedTech & Biotech teams.",
                "body_text": f"Hi {first_name},\n\nQuick follow up—MedTech teams using our eQMS platform reduced audit preparation cycles by over 70% while achieving zero-finding FDA & ISO recertification audits.\n\nWould it make sense to share a 3-minute video overview of how we handle automated electronic signatures and change controls?\n\nBest,\nAI SDR Team"
            },
            {
                "step_number": 3,
                "subject": f"Final thought for {first_name} @ {comp_name}",
                "personalized_hook": "Zero-friction eQMS evaluation.",
                "body_text": f"Hi {first_name},\n\nI know you are likely focused on upcoming product milestones at {comp_name}. If upgrading your QMS infrastructure isn't a priority this quarter, no worries at all.\n\nIf it ever is, you can grab a self-guided walkthrough of our eQMS software anytime.\n\nBest,\nAI SDR Team"
            }
        ]

    async def generate_sequences(self, contact: Dict[str, Any], company: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generates a personalized 3-step sales email sequence tailored to the target persona and company background."""
        if not self.groq_api_key:
            return self._rule_based_sequences(contact, company)

        prompt = f"""
You are an elite AI Sales Development Representative (SDR) selling modern eQMS (Quality Management System) software.
Write a personalized 3-step cold email sequence targeting this buyer:

Recipient Name: {contact.get('name')}
Title: {contact.get('title')}
Company: {company.get('name')}
Industry Subsector: {company.get('industry_subsector')}
Region: {company.get('region')}
Key Compliance Driver: {company.get('compliance_drivers')}

Return JSON ONLY formatted like:
{{
  "sequences": [
    {{
      "step_number": 1,
      "subject": "Email subject 1",
      "personalized_hook": "Short custom hook sentence",
      "body_text": "Full email body 1"
    }},
    {{
      "step_number": 2,
      "subject": "Email subject 2",
      "personalized_hook": "Short custom hook sentence",
      "body_text": "Full email body 2"
    }},
    {{
      "step_number": 3,
      "subject": "Email subject 3",
      "personalized_hook": "Short custom hook sentence",
      "body_text": "Full email body 3"
    }}
  ]
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
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"}
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return parsed.get("sequences", self._rule_based_sequences(contact, company))
        except Exception as e:
            print(f"[Outreach Generator] API Notice ({e}). Using rule fallback.")

        return self._rule_based_sequences(contact, company)
