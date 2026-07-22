import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to local sqlite if DATABASE_URL is not set
    DATABASE_URL = "sqlite:///./app.db"

# Create SQLAlchemy Engine
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
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
    scraped_data = relationship("ScrapedResult", back_populates="owner", cascade="all, delete-orphan")

class UserQuery(Base):
    __tablename__ = "user_queries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query = Column(Text, nullable=False)
    max_results = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="queries")

class ScrapedResult(Base):
    __tablename__ = "scraped_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query = Column(Text, nullable=False)
    github_url = Column(Text, nullable=False)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    linkedin_url = Column(Text, nullable=True)
    repositories = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="scraped_data")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
