import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pharmabkp:aivoadma25@216.48.184.249:5432/pharma")
DB_SCHEMA = "ai_sdr"

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print(f"Connected to database. Executing cleanup on schema '{DB_SCHEMA}'...")
    
    # Using text() for raw SQL to avoid model dependencies and ensure fast execution
    queries = [
        # Delete old campaigns (cascades to company_leads, qualified_contacts, etc. if FK is correct)
        f"DELETE FROM {DB_SCHEMA}.sdr_campaigns WHERE created_at < NOW() - INTERVAL '24 hours';",
        
        # Delete old leads directly (just in case they have no campaign or cascade failed)
        f"DELETE FROM {DB_SCHEMA}.company_leads WHERE created_at < NOW() - INTERVAL '24 hours';",
        
        # Delete old user queries
        f"DELETE FROM {DB_SCHEMA}.user_queries WHERE created_at < NOW() - INTERVAL '24 hours';"
    ]
    
    for q in queries:
        try:
            result = conn.execute(text(q))
            print(f"Executed: {q} -> Rows affected: {result.rowcount}")
        except Exception as e:
            print(f"Error executing {q}: {e}")
            
    conn.commit()
    print("Cleanup completed successfully.")
