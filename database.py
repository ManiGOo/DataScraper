import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./app.db"

# Create SQLAlchemy Engine (sqlite thread-safe args if sqlite)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    queries = relationship("UserQuery", back_populates="owner", cascade="all, delete-orphan")
    campaigns = relationship("SdrCampaign", back_populates="owner", cascade="all, delete-orphan")

class UserQuery(Base):
    __tablename__ = "user_queries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query = Column(Text, nullable=False)
    max_results = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="queries")

class SdrCampaign(Base):
    __tablename__ = "sdr_campaigns"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    target_region = Column(String(255), nullable=False)
    target_sector = Column(String(255), nullable=False) # MedTech, Biotech, Pharma, General Life Science
    status = Column(String(50), default="PENDING")
    progress = Column(Integer, default=0)
    total_expected = Column(Integer, default=10)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="campaigns")
    company_leads = relationship("CompanyLead", back_populates="campaign", cascade="all, delete-orphan")

class CompanyLead(Base):
    __tablename__ = "company_leads"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String(36), ForeignKey("sdr_campaigns.id", ondelete="CASCADE"), nullable=True)
    domain = Column(String(255), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    region = Column(String(255), nullable=True)
    industry_subsector = Column(String(100), nullable=True)
    employee_range = Column(String(100), nullable=True)
    qms_fit_score = Column(Integer, default=0) # 1 to 100
    compliance_drivers = Column(Text, nullable=True) # e.g., JSON list ["ISO 13485", "21 CFR Part 11"]
    summary = Column(Text, nullable=True)
    website_url = Column(Text, nullable=True)
    source = Column(String(100), default="Regulatory Scanner")
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("SdrCampaign", back_populates="company_leads")
    contacts = relationship("QualifiedContact", back_populates="company", cascade="all, delete-orphan")

class QualifiedContact(Base):
    __tablename__ = "qualified_contacts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_leads.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    linkedin_url = Column(Text, nullable=True)
    verification_status = Column(String(50), default="UNVERIFIED") # VERIFIED, CATCH_ALL, UNVERIFIED
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("CompanyLead", back_populates="contacts")
    sequences = relationship("OutreachSequence", back_populates="contact", cascade="all, delete-orphan")

class OutreachSequence(Base):
    __tablename__ = "outreach_sequences"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("qualified_contacts.id", ondelete="CASCADE"), nullable=False)
    step_number = Column(Integer, default=1) # 1, 2, 3
    subject = Column(String(255), nullable=False)
    body_text = Column(Text, nullable=False)
    personalized_hook = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    contact = relationship("QualifiedContact", back_populates="sequences")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
