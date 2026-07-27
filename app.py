import os
import uuid
import json
import asyncio
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import (
    init_db, get_db, SessionLocal, User, UserQuery, 
    SdrCampaign, CompanyLead, QualifiedContact, OutreachSequence
)
from discovery import LeadDiscoveryEngine
from crawler import DomainCrawler
from ai_classifier import AIProspectClassifier
from enrichment import PersonaContactEnricher
from outreach_generator import OutreachCopyGenerator

# Ensure DB initialized
init_db()

# Instantiate modules
discovery_engine = LeadDiscoveryEngine()
domain_crawler = DomainCrawler()
ai_classifier = AIProspectClassifier()
contact_enricher = PersonaContactEnricher()
copy_generator = OutreachCopyGenerator()

async def background_sdr_worker():
    """Indefinite background worker processing AI SDR Lead Scraper Campaigns."""
    while True:
        try:
            with SessionLocal() as db:
                campaign = db.query(SdrCampaign).filter(SdrCampaign.status == "PENDING").first()
                if campaign:
                    campaign.status = "RUNNING"
                    db.commit()
                    campaign_id = campaign.id
                    
                    # Fetch all previously saved lead domains across ALL campaigns in the DB to enforce cross-run uniqueness
                    existing_domains = {lead.domain for lead in db.query(CompanyLead.domain).all()}
                    
                    try:
                        # 1. Discover Leads across Selected Regulatory Registries (excluding previously fetched domains)
                        sel_sources = json.loads(campaign.selected_sources) if campaign.selected_sources else ["ALL"]
                        raw_leads = await discovery_engine.discover_leads(
                            target_region=campaign.target_region,
                            target_sector=campaign.target_sector,
                            max_results=campaign.total_expected,
                            selected_sources=sel_sources,
                            exclude_domains=existing_domains
                        )
                        
                        campaign.total_expected = len(raw_leads) if raw_leads else 0
                        db.commit()

                        if not raw_leads:
                            campaign.status = "COMPLETED"
                            campaign.error_message = "All available unique prospects for this target region & sector have already been extracted in prior runs. Add state names or select additional regulatory registries to discover new data."
                            db.commit()
                            continue
                        
                        processed_count = 0
                        processed_domains = set()
                        for lead_item in raw_leads:
                            if lead_item["domain"] in processed_domains:
                                continue
                            processed_domains.add(lead_item["domain"])
                            # 2. Crawl Company Domain for QMS keywords
                            crawl_data = await domain_crawler.crawl_domain(
                                domain=lead_item["domain"],
                                base_url=lead_item.get("website_url")
                            )
                            
                            # 3. AI Qualification & QMS Fit Scoring
                            ai_qual = await ai_classifier.qualify_lead(lead_item, crawl_data)
                            
                            # Save Company Lead
                            company_lead = CompanyLead(
                                campaign_id=campaign_id,
                                domain=lead_item["domain"],
                                name=lead_item["name"],
                                region=lead_item.get("region", campaign.target_region),
                                industry_subsector=lead_item.get("industry_subsector", campaign.target_sector),
                                employee_range=lead_item.get("employee_range", "50-200"),
                                qms_fit_score=ai_qual["qms_fit_score"],
                                compliance_drivers=json.dumps(ai_qual["compliance_drivers"]),
                                summary=ai_qual["summary"],
                                website_url=lead_item.get("website_url"),
                                source=lead_item.get("source", "Regulatory Scanner")
                            )
                            db.add(company_lead)
                            db.flush() # get company_lead.id
                            
                            # 4. Enrich Decision Maker Contacts
                            enriched_contacts = contact_enricher.enrich_contacts_for_lead(
                                domain=lead_item["domain"],
                                company_name=lead_item["name"],
                                crawl_emails=crawl_data.get("emails_found")
                            )
                            
                            for c_data in enriched_contacts:
                                contact_obj = QualifiedContact(
                                    company_id=company_lead.id,
                                    name=c_data["name"],
                                    title=c_data["title"],
                                    email=c_data["email"],
                                    linkedin_url=c_data["linkedin_url"],
                                    verification_status=c_data["verification_status"]
                                )
                                db.add(contact_obj)
                                db.flush() # get contact_obj.id
                                
                                # 5. Generate AI SDR Cold Outreach Copy
                                company_dict = {
                                    "name": company_lead.name,
                                    "industry_subsector": company_lead.industry_subsector,
                                    "region": company_lead.region,
                                    "compliance_drivers": ai_qual["compliance_drivers"]
                                }
                                sequences = await copy_generator.generate_sequences(c_data, company_dict)
                                
                                for seq in sequences:
                                    outreach = OutreachSequence(
                                        contact_id=contact_obj.id,
                                        step_number=seq.get("step_number", 1),
                                        subject=seq.get("subject", "QMS Software Inquiry"),
                                        body_text=seq.get("body_text", ""),
                                        personalized_hook=seq.get("personalized_hook", "")
                                    )
                                    db.add(outreach)
                            
                            processed_count += 1
                            campaign.progress = processed_count
                            db.commit()
                            
                        campaign.status = "COMPLETED"
                        db.commit()
                    except Exception as e:
                        print(f"Campaign execution error: {e}")
                        campaign.status = "FAILED"
                        campaign.error_message = str(e)
                        db.commit()
        except Exception as e:
            print(f"Background SDR worker loop notice: {e}")
            
        await asyncio.sleep(3)

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(background_sdr_worker())
    yield
    worker_task.cancel()

app = FastAPI(title="AI SDR & eQMS B2B Lead Generator System", lifespan=lifespan)

# Static files setup
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Schemas
class StartCampaignRequest(BaseModel):
    target_region: str = "Massachusetts, USA"
    target_sector: str = "Medical Devices / MedTech"
    max_results: int = 5
    selected_sources: Optional[List[str]] = ["ALL"]

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>AI SDR eQMS Lead Generator API is running!</h1>"

@app.post("/api/sdr/campaigns/start")
@app.post("/api/sdr/start-campaign")
def start_campaign(req: StartCampaignRequest, db: Session = Depends(get_db)):
    campaign_id = str(uuid.uuid4())
    sources = req.selected_sources if req.selected_sources else ["ALL"]
    campaign = SdrCampaign(
        id=campaign_id,
        target_region=req.target_region,
        target_sector=req.target_sector,
        status="PENDING",
        progress=0,
        total_expected=req.max_results,
        selected_sources=json.dumps(sources)
    )
    db.add(campaign)
    db.commit()
    return {"campaign_id": campaign_id, "status": "PENDING"}

@app.get("/api/sdr/campaign/{campaign_id}")
@app.get("/api/sdr/campaigns/status/{campaign_id}")
def get_campaign_status(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(SdrCampaign).filter(SdrCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
        
    leads = db.query(CompanyLead).filter(CompanyLead.campaign_id == campaign_id).order_by(CompanyLead.qms_fit_score.desc()).all()
    
    lead_results = []
    for lead in leads:
        contacts_data = []
        for contact in lead.contacts:
            seqs_data = [
                {
                    "step_number": s.step_number,
                    "subject": s.subject,
                    "body_text": s.body_text,
                    "personalized_hook": s.personalized_hook
                } for s in contact.sequences
            ]
            company_clean = re.sub(r'(?i)\b(pvt|ltd|inc|llc|corp|corporation|facilities|plant|manufacturing|pharma|pharmaceuticals|medical)\b', '', lead.name)
            company_clean = re.sub(r'[^a-zA-Z0-9\s]', '', company_clean).strip()
            company_kw = company_clean.split()[0] if company_clean else lead.name.split()[0]
            role_kw = "Quality Assurance" if "quality" in contact.title.lower() else ("Regulatory Affairs" if "regulatory" in contact.title.lower() else contact.title.split()[0])
            g_query = urllib.parse.quote_plus(f'site:linkedin.com/in/ "{company_kw}" "{role_kw}"')
            web_search_url = f"https://www.google.com/search?q={g_query}"

            contacts_data.append({
                "id": contact.id,
                "name": contact.name,
                "title": contact.title,
                "email": contact.email,
                "linkedin_url": contact.linkedin_url,
                "web_search_url": web_search_url,
                "verification_status": contact.verification_status,
                "sequences": seqs_data
            })
            
        lead_results.append({
            "id": lead.id,
            "name": lead.name,
            "domain": lead.domain,
            "region": lead.region,
            "industry_subsector": lead.industry_subsector,
            "employee_range": lead.employee_range,
            "qms_fit_score": lead.qms_fit_score,
            "compliance_drivers": json.loads(lead.compliance_drivers) if lead.compliance_drivers else [],
            "summary": lead.summary,
            "website_url": lead.website_url,
            "source": lead.source,
            "contacts": contacts_data
        })

    return {
        "campaign_id": campaign.id,
        "target_region": campaign.target_region,
        "target_sector": campaign.target_sector,
        "status": campaign.status,
        "progress": campaign.progress,
        "total_expected": campaign.total_expected,
        "error_message": campaign.error_message,
        "leads": lead_results
    }

@app.get("/api/sdr/export/{campaign_id}/{file_format}")
def export_leads(campaign_id: str, file_format: str, db: Session = Depends(get_db)):
    campaign = db.query(SdrCampaign).filter(SdrCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
        
    leads = db.query(CompanyLead).filter(CompanyLead.campaign_id == campaign_id).all()
    if not leads:
        raise HTTPException(status_code=404, detail="No leads found for export.")

    rows = []
    seen_domains = set()
    for lead in leads:
        if lead.domain in seen_domains:
            continue
        seen_domains.add(lead.domain)

        drivers = ", ".join(json.loads(lead.compliance_drivers)) if lead.compliance_drivers else ""
        contacts = lead.contacts or []
        c1 = contacts[0] if len(contacts) > 0 else None
        c2 = contacts[1] if len(contacts) > 1 else None

        step1 = next((s for s in c1.sequences if s.step_number == 1), None) if (c1 and c1.sequences) else None

        rows.append({
            "Company Name": lead.name,
            "Domain": lead.domain,
            "Region": lead.region,
            "Sub-sector": lead.industry_subsector,
            "QMS Fit Score": lead.qms_fit_score,
            "Compliance Drivers": drivers,
            "Primary Contact": c1.name if c1 else "",
            "Primary Title": c1.title if c1 else "",
            "Primary Work Email": c1.email if c1 else "",
            "Primary LinkedIn": c1.linkedin_url if c1 else "",
            "Secondary Contact": c2.name if c2 else "",
            "Secondary Title": c2.title if c2 else "",
            "Secondary Work Email": c2.email if c2 else "",
            "Secondary LinkedIn": c2.linkedin_url if c2 else "",
            "Email Subject": step1.subject if step1 else "",
            "Personalized Hook": step1.personalized_hook if step1 else "",
            "Lead Source": lead.source
        })

    df = pd.DataFrame(rows)
    fmt = file_format.lower()
    
    if fmt == "csv":
        filepath = os.path.join(OUTPUTS_DIR, f"qms_leads_{campaign_id[:8]}.csv")
        df.to_csv(filepath, index=False)
        return FileResponse(filepath, media_type="text/csv", filename=f"life_science_qms_leads_{campaign_id[:8]}.csv")
    elif fmt in ["excel", "xlsx"]:
        filepath = os.path.join(OUTPUTS_DIR, f"qms_leads_{campaign_id[:8]}.xlsx")
        df.to_excel(filepath, index=False)
        return FileResponse(filepath, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"life_science_qms_leads_{campaign_id[:8]}.xlsx")
    
    raise HTTPException(status_code=400, detail="Invalid format. Use csv or excel.")

@app.get("/records", response_class=HTMLResponse)
def read_records_page():
    records_file = os.path.join(STATIC_DIR, "records.html")
    if os.path.exists(records_file):
        with open(records_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Records Library HTML not found</h1>"

@app.get("/api/sdr/records")
def get_all_stored_records(
    region: Optional[str] = None,
    sector: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    from sqlalchemy import or_
    query = db.query(CompanyLead)
    
    if region and region != "ALL":
        reg_lower = region.lower()
        tokens = [region]
        if "middle east" in reg_lower:
            tokens.extend(["israel", "uae", "saudi", "jordan", "dubai", "tel aviv", "ras al khaimah", "amman", "riyadh", "petah tikva"])
        elif "europe" in reg_lower:
            tokens.extend(["germany", "uk", "switzerland", "france", "italy", "london", "basel", "göttingen", "hamburg", "melsungen", "oxford"])
        elif "india" in reg_lower:
            tokens.extend(["india", "hyderabad", "gujarat", "mumbai", "delhi", "noida", "chennai", "vadodara", "telangana", "maharashtra"])
        elif "north america" in reg_lower or "usa" in reg_lower or "canada" in reg_lower:
            tokens.extend(["usa", "canada", "ontario", "quebec", "vancouver", "toronto", "montreal", "massachusetts", "boston"])
        elif "south america" in reg_lower or "brazil" in reg_lower:
            tokens.extend(["brazil", "argentina", "mexico", "são paulo", "buenos aires", "mexico city"])
        elif "asia-pacific" in reg_lower or "japan" in reg_lower:
            tokens.extend(["japan", "singapore", "south korea", "tokyo", "sejong"])

        query = query.filter(or_(*[CompanyLead.region.ilike(f"%{t}%") for t in tokens]))

    if sector and sector != "ALL":
        query = query.filter(CompanyLead.industry_subsector.ilike(f"%{sector}%"))
    if source and source != "ALL":
        query = query.filter(CompanyLead.source.ilike(f"%{source}%"))
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (CompanyLead.name.ilike(search_term)) |
            (CompanyLead.domain.ilike(search_term)) |
            (CompanyLead.region.ilike(search_term)) |
            (CompanyLead.summary.ilike(search_term))
        )
        
    leads = query.order_by(CompanyLead.created_at.desc()).all()
    
    lead_results = []
    seen_domains = set()
    for lead in leads:
        if lead.domain in seen_domains:
            continue
        seen_domains.add(lead.domain)
        
        contacts_data = []
        for contact in lead.contacts:
            seqs_data = [
                {
                    "step_number": s.step_number,
                    "subject": s.subject,
                    "body_text": s.body_text,
                    "personalized_hook": s.personalized_hook
                } for s in contact.sequences
            ]
            contacts_data.append({
                "id": contact.id,
                "name": contact.name,
                "title": contact.title,
                "email": contact.email,
                "linkedin_url": contact.linkedin_url,
                "verification_status": contact.verification_status,
                "sequences": seqs_data
            })
            
        lead_results.append({
            "id": lead.id,
            "campaign_id": lead.campaign_id,
            "name": lead.name,
            "domain": lead.domain,
            "region": lead.region,
            "industry_subsector": lead.industry_subsector,
            "employee_range": lead.employee_range,
            "qms_fit_score": lead.qms_fit_score,
            "compliance_drivers": json.loads(lead.compliance_drivers) if lead.compliance_drivers else [],
            "summary": lead.summary,
            "website_url": lead.website_url,
            "source": lead.source,
            "contacts": contacts_data,
            "created_at": lead.created_at.isoformat() if lead.created_at else ""
        })

    return {
        "total_count": len(lead_results),
        "leads": lead_results
    }

@app.get("/api/sdr/records/export/{file_format}")
def export_all_stored_records(
    file_format: str,
    region: Optional[str] = None,
    sector: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(CompanyLead)
    if region and region != "ALL":
        query = query.filter(CompanyLead.region.ilike(f"%{region}%"))
    if sector and sector != "ALL":
        query = query.filter(CompanyLead.industry_subsector.ilike(f"%{sector}%"))
        
    leads = query.order_by(CompanyLead.created_at.desc()).all()
    if not leads:
        raise HTTPException(status_code=404, detail="No stored records found for export.")

    rows = []
    seen_domains = set()
    for lead in leads:
        if lead.domain in seen_domains:
            continue
        seen_domains.add(lead.domain)

        drivers = ", ".join(json.loads(lead.compliance_drivers)) if lead.compliance_drivers else ""
        contacts = lead.contacts or []
        c1 = contacts[0] if len(contacts) > 0 else None
        c2 = contacts[1] if len(contacts) > 1 else None

        step1 = next((s for s in c1.sequences if s.step_number == 1), None) if (c1 and c1.sequences) else None

        rows.append({
            "Company Name": lead.name,
            "Domain": lead.domain,
            "Region": lead.region,
            "Sub-sector": lead.industry_subsector,
            "QMS Fit Score": lead.qms_fit_score,
            "Compliance Drivers": drivers,
            "Primary Contact": c1.name if c1 else "",
            "Primary Title": c1.title if c1 else "",
            "Primary Work Email": c1.email if c1 else "",
            "Primary LinkedIn": c1.linkedin_url if c1 else "",
            "Secondary Contact": c2.name if c2 else "",
            "Secondary Title": c2.title if c2 else "",
            "Secondary Work Email": c2.email if c2 else "",
            "Secondary LinkedIn": c2.linkedin_url if c2 else "",
            "Email Subject": step1.subject if step1 else "",
            "Personalized Hook": step1.personalized_hook if step1 else "",
            "Lead Source": lead.source,
            "Saved Date": lead.created_at.strftime("%Y-%m-%d") if lead.created_at else ""
        })

    df = pd.DataFrame(rows)
    fmt = file_format.lower()
    
    if fmt == "csv":
        filepath = os.path.join(OUTPUTS_DIR, "all_stored_life_science_records.csv")
        df.to_csv(filepath, index=False)
        return FileResponse(filepath, media_type="text/csv", filename="all_stored_life_science_records.csv")
    elif fmt in ["excel", "xlsx"]:
        filepath = os.path.join(OUTPUTS_DIR, "all_stored_life_science_records.xlsx")
        df.to_excel(filepath, index=False)
        return FileResponse(filepath, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="all_stored_life_science_records.xlsx")
    
    raise HTTPException(status_code=400, detail="Invalid format. Use csv or excel.")
