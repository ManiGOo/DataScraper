import os
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'
import json
import uuid
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Header
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from groq import Groq
from sqlalchemy.orm import Session

from scraper import GitHubScraper
from database import init_db, get_db, SessionLocal, User, UserQuery, ScrapedResult

# Load environment variables
load_dotenv()

# Initialize Database tables
init_db()

app = FastAPI(title="GitHub Data Scraper API with Auth & Database")

# Auth & Security setup
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_2026")
JWT_ALGORITHM = "HS256"
security = HTTPBearer(auto_error=False)

# Directories setup
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory task tracking
tasks_db: Dict[str, Dict[str, Any]] = {}

# Pydantic Schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ScrapeRequest(BaseModel):
    query: str
    max_results: int = 10

class ChatMessage(BaseModel):
    role: str
    content: str

class AiQueryRequest(BaseModel):
    prompt: str
    history: Optional[List[ChatMessage]] = []

# Auth Helper Functions using PBKDF2 sha256
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + pwd_hash.hex()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt_hex, hash_hex = hashed_password.split(':')
        salt = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, 100000)
        return pwd_hash.hex() == hash_hex
    except Exception:
        return False

def create_access_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not credentials:
        return None
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    user = get_current_user_optional(credentials, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user

def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in environment variables.")
    return Groq(api_key=api_key)

def run_scraper_task(task_id: str, query: str, max_results: int, user_id: Optional[int] = None):
    tasks_db[task_id]["status"] = "running"
    tasks_db[task_id]["progress"] = 5
    tasks_db[task_id]["logs"].append(f"Task started for query: '{query}'")

    def progress_cb(pct: int, msg: str):
        tasks_db[task_id]["progress"] = pct
        tasks_db[task_id]["logs"].append(msg)

    try:
        scraper = GitHubScraper(headless=True)
        results = scraper.scrape(query, max_results=max_results, progress_callback=progress_cb)

        tasks_db[task_id]["results"] = results
        
        # Save output files locally
        if results:
            df = pd.DataFrame(results)
            desired_columns = ["Name", "Email", "LinkedIn URL", "GitHub URL", "Repositories"]
            df = df.reindex(columns=desired_columns)

            csv_path = os.path.join(OUTPUTS_DIR, f"{task_id}.csv")
            excel_path = os.path.join(OUTPUTS_DIR, f"{task_id}.xlsx")

            df.to_csv(csv_path, index=False)
            df.to_excel(excel_path, index=False, engine='openpyxl')

            tasks_db[task_id]["csv_file"] = csv_path
            tasks_db[task_id]["excel_file"] = excel_path

        # Save to Database if user_id is provided
        if user_id:
            db = SessionLocal()
            try:
                # 1. Save query history
                new_query_record = UserQuery(user_id=user_id, query=query, max_results=max_results)
                db.add(new_query_record)

                # Maintain max 20 query records per user
                user_queries_count = db.query(UserQuery).filter(UserQuery.user_id == user_id).count()
                if user_queries_count > 20:
                    oldest_queries = (
                        db.query(UserQuery)
                        .filter(UserQuery.user_id == user_id)
                        .order_by(UserQuery.created_at.asc())
                        .limit(user_queries_count - 20)
                        .all()
                    )
                    for oq in oldest_queries:
                        db.delete(oq)

                # 2. Save extracted profiles to database
                for r in results:
                    db_result = ScrapedResult(
                        user_id=user_id,
                        query=query,
                        github_url=r.get("GitHub URL", ""),
                        name=r.get("Name"),
                        email=r.get("Email"),
                        linkedin_url=r.get("LinkedIn URL"),
                        repositories=str(r.get("Repositories", "0"))
                    )
                    db.add(db_result)

                db.commit()
            except Exception as db_err:
                print(f"[-] Database save error: {db_err}")
                db.rollback()
            finally:
                db.close()

        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["progress"] = 100
        tasks_db[task_id]["logs"].append("Scraping completed successfully.")

    except Exception as e:
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["error"] = str(e)
        tasks_db[task_id]["logs"].append(f"Error occurred: {str(e)}")

# Routes

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>GitHub Data Scraper API is running.</h1>")

@app.get("/login", response_class=HTMLResponse)
def read_login():
    login_file = os.path.join(STATIC_DIR, "login.html")
    if os.path.exists(login_file):
        with open(login_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Login Page</h1>")

@app.get("/signup", response_class=HTMLResponse)
def read_signup():
    signup_file = os.path.join(STATIC_DIR, "signup.html")
    if os.path.exists(signup_file):
        with open(signup_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Signup Page</h1>")

@app.get("/history", response_class=HTMLResponse)
def read_history():
    history_file = os.path.join(STATIC_DIR, "history.html")
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>History Page</h1>")

@app.get("/saved-data", response_class=HTMLResponse)
def read_saved_data():
    saved_file = os.path.join(STATIC_DIR, "saved-data.html")
    if os.path.exists(saved_file):
        with open(saved_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Saved Data Page</h1>")

# Authentication Endpoints
@app.post("/api/auth/register")
def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == req.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists.")
    
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    new_user = User(email=req.email.lower(), hashed_password=hash_password(req.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(new_user.id, new_user.email)
    return {"token": token, "email": new_user.email}

@app.post("/api/auth/login")
def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user.id, user.email)
    return {"token": token, "email": user.email}

@app.get("/api/auth/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "created_at": user.created_at}

# User History & Saved Results Endpoints
@app.get("/api/user/history")
def get_user_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    queries = (
        db.query(UserQuery)
        .filter(UserQuery.user_id == user.id)
        .order_by(UserQuery.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": q.id,
            "query": q.query,
            "max_results": q.max_results,
            "created_at": q.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for q in queries
    ]

@app.get("/api/user/saved-results")
def get_saved_results(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    results = (
        db.query(ScrapedResult)
        .filter(ScrapedResult.user_id == user.id)
        .order_by(ScrapedResult.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "query": r.query,
            "name": r.name,
            "email": r.email,
            "linkedin_url": r.linkedin_url,
            "github_url": r.github_url,
            "repositories": r.repositories,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for r in results
    ]

# AI & Scraper Endpoints
@app.post("/api/generate-query")
def generate_ai_query(req: AiQueryRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    client = get_groq_client()
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    system_prompt = (
        "You are an expert AI Assistant and GitHub Search Syntax Architect. Your goal is to analyze the user's request, "
        "explain your technical reasoning, and generate exactly 3 distinct, valid GitHub user search query options.\n\n"
        "STRICT GITHUB SYNTAX RULES (NO HALLUCINATIONS):\n"
        "1. Always include `type:user` in every query string.\n"
        "2. Location parameter must be formatted as `location:<city_or_country>` (e.g. location:India, location:London, location:\"San Francisco\"). NEVER omit the colon.\n"
        "3. Language parameter must be formatted as `language:<programming_language>` (e.g. language:Python, language:TypeScript). NEVER omit the colon.\n"
        "4. Repositories parameter must be `repos:><number>` (e.g. repos:>10). NEVER omit the colon.\n"
        "5. Keyword qualifiers: Place keywords like `student`, `fullstack`, `developer` directly or with `in:bio` (e.g., `student location:India language:Python repos:>10 type:user`).\n"
        "6. If the user asks to modify or refine a previous query from history, adjust the parameters accordingly while preserving intact constraints.\n\n"
        "REQUIRED OUTPUT FORMAT:\n"
        "Return STRICT JSON ONLY matching this exact structure (no markdown formatting outside JSON):\n"
        "{\n"
        '  "reasoning": "Detailed technical explanation of how you parsed user intent and constructed the query options.",\n'
        '  "queries": [\n'
        '    {\n'
        '      "title": "Strict Query (Exact Match)",\n'
        '      "description": "Combines all exact parameters specified in the request.",\n'
        '      "query": "student location:India language:Python repos:>10 type:user"\n'
        '    },\n'
        '    {\n'
        '      "title": "Broad Query (High Velocity)",\n'
        '      "description": "Widens search range for broader candidate discovery.",\n'
        '      "query": "location:India language:Python repos:>10 type:user"\n'
        '    },\n'
        '    {\n'
        '      "title": "Bio-Targeted Query (Keyword Focused)",\n'
        '      "description": "Searches bio text for specific student/role keywords.",\n'
        '      "query": "student in:bio location:India language:Python type:user"\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    if req.history:
        for msg in req.history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.prompt})

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=600,
            response_format={"type": "json_object"}
        )
        content_str = completion.choices[0].message.content.strip()
        data = json.loads(content_str)
        return {
            "reasoning": data.get("reasoning", "Parsed request successfully."),
            "queries": data.get("queries", []),
            "model_used": model
        }
    except Exception as e:
        try:
            fallback_model = "llama-3.3-70b-versatile"
            completion = client.chat.completions.create(
                model=fallback_model,
                messages=messages,
                temperature=0.2,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            content_str = completion.choices[0].message.content.strip()
            data = json.loads(content_str)
            return {
                "reasoning": data.get("reasoning", "Parsed request successfully."),
                "queries": data.get("queries", []),
                "model_used": fallback_model
            }
        except Exception as fallback_err:
            raise HTTPException(status_code=500, detail=f"AI Agent Error: {str(e)}")

@app.post("/api/scrape")
def start_scrape(
    req: ScrapeRequest, 
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    task_id = str(uuid.uuid4())
    user_id = current_user.id if current_user else None

    tasks_db[task_id] = {
        "task_id": task_id,
        "query": req.query,
        "max_results": req.max_results,
        "status": "pending",
        "progress": 0,
        "logs": [],
        "results": [],
        "csv_file": None,
        "excel_file": None,
        "error": None
    }

    thread = threading.Thread(
        target=run_scraper_task, 
        args=(task_id, req.query, req.max_results, user_id)
    )
    thread.daemon = True
    thread.start()

    return {"task_id": task_id, "status": "pending"}

@app.get("/api/status/{task_id}")
def get_status(task_id: str):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found.")
    return tasks_db[task_id]

@app.get("/api/download/{task_id}/{file_format}")
def download_file(task_id: str, file_format: str):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    task = tasks_db[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task is not yet completed.")

    file_format = file_format.lower()
    if file_format == "csv":
        filepath = task.get("csv_file")
        filename = f"github_users_{task_id[:8]}.csv"
        media_type = "text/csv"
    elif file_format in ["excel", "xlsx"]:
        filepath = task.get("excel_file")
        filename = f"github_users_{task_id[:8]}.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'excel'.")

    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Export file not found.")

    return FileResponse(filepath, filename=filename, media_type=media_type)
