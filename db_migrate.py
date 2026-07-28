import os
import psycopg2
from dotenv import load_dotenv
import re

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
DB_SCHEMA = os.getenv("DB_SCHEMA", "ai_sdr")
raw_dsn = re.sub(r'^postgresql\+?[^:]*://', 'postgresql://', DATABASE_URL)

conn = psycopg2.connect(raw_dsn)
cur = conn.cursor()

try:
    cur.execute(f"ALTER TABLE {DB_SCHEMA}.company_leads ADD COLUMN is_sme BOOLEAN DEFAULT TRUE;")
    print("Added is_sme")
except Exception as e:
    print(e)
    conn.rollback()

try:
    cur.execute(f"ALTER TABLE {DB_SCHEMA}.company_leads ADD COLUMN estimated_revenue VARCHAR(100);")
    print("Added estimated_revenue")
except Exception as e:
    print(e)
    conn.rollback()

try:
    cur.execute(f"ALTER TABLE {DB_SCHEMA}.company_leads ADD COLUMN source_directory VARCHAR(255);")
    print("Added source_directory")
except Exception as e:
    print(e)
    conn.rollback()

conn.commit()
cur.close()
conn.close()
print("Migration completed.")
