import os
import re
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import psycopg2

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pharmabkp:aivoadma25@216.48.184.249:5432/pharma")
DB_SCHEMA = os.getenv("DB_SCHEMA", "ai_sdr")

# Standardize database driver URI for SQLAlchemy
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

is_postgres = DATABASE_URL.startswith("postgresql")

# Ensure PostgreSQL schema exists before creating tables
if is_postgres:
    try:
        raw_dsn = re.sub(r'^postgresql\+?[^:]*://', 'postgresql://', DATABASE_URL)
        conn = psycopg2.connect(raw_dsn)
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA};")
        conn.commit()
        cur.close()
        conn.close()
        print(f"[Database] Verified/Created schema '{DB_SCHEMA}' in PostgreSQL.")
    except Exception as e:
        print(f"[Database Schema Notice] {e}")

# Configure SQLAlchemy Engine
connect_args = {}
if is_postgres:
    connect_args["options"] = f"-c search_path={DB_SCHEMA},public"
else:
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData(schema=DB_SCHEMA) if is_postgres else None
Base = declarative_base(metadata=metadata)

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
    user_id = Column(Integer, ForeignKey(f"{DB_SCHEMA}.users.id" if is_postgres else "users.id", ondelete="CASCADE"), nullable=False)
    query = Column(Text, nullable=False)
    max_results = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="queries")

class SdrCampaign(Base):
    __tablename__ = "sdr_campaigns"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{DB_SCHEMA}.users.id" if is_postgres else "users.id", ondelete="CASCADE"), nullable=True)
    target_region = Column(String(255), nullable=False)
    target_sector = Column(String(255), nullable=False)
    status = Column(String(50), default="PENDING")
    progress = Column(Integer, default=0)
    total_expected = Column(Integer, default=10)
    selected_sources = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="campaigns")
    company_leads = relationship("CompanyLead", back_populates="campaign", cascade="all, delete-orphan")

class CompanyLead(Base):
    __tablename__ = "company_leads"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String(36), ForeignKey(f"{DB_SCHEMA}.sdr_campaigns.id" if is_postgres else "sdr_campaigns.id", ondelete="CASCADE"), nullable=True)
    domain = Column(String(255), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    region = Column(String(255), nullable=True)
    industry_subsector = Column(String(100), nullable=True)
    employee_range = Column(String(100), nullable=True)
    qms_fit_score = Column(Integer, default=0)
    compliance_drivers = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    website_url = Column(Text, nullable=True)
    source = Column(String(100), default="Regulatory Scanner")
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("SdrCampaign", back_populates="company_leads")
    contacts = relationship("QualifiedContact", back_populates="company", cascade="all, delete-orphan")

class QualifiedContact(Base):
    __tablename__ = "qualified_contacts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{DB_SCHEMA}.company_leads.id" if is_postgres else "company_leads.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    linkedin_url = Column(Text, nullable=True)
    verification_status = Column(String(50), default="UNVERIFIED")
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("CompanyLead", back_populates="contacts")
    sequences = relationship("OutreachSequence", back_populates="contact", cascade="all, delete-orphan")

class OutreachSequence(Base):
    __tablename__ = "outreach_sequences"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey(f"{DB_SCHEMA}.qualified_contacts.id" if is_postgres else "qualified_contacts.id", ondelete="CASCADE"), nullable=False)
    step_number = Column(Integer, default=1)
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
