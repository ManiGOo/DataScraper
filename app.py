import os
import json
import uuid
import threading
from typing import Dict, Any, List, Optional
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from groq import Groq

from scraper import GitHubScraper

# Load environment variables
load_dotenv()

app = FastAPI(title="GitHub Data Scraper API with Groq AI Agent")

# Ensure outputs directory exists
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# Mount static assets
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory task tracking
tasks_db: Dict[str, Dict[str, Any]] = {}

class ScrapeRequest(BaseModel):
    query: str
    max_results: int = 10

class ChatMessage(BaseModel):
    role: str
    content: str

class AiQueryRequest(BaseModel):
    prompt: str
    history: Optional[List[ChatMessage]] = []

def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in environment variables.")
    return Groq(api_key=api_key)

def run_scraper_task(task_id: str, query: str, max_results: int):
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
        
        # Save output files
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

        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["progress"] = 100
        tasks_db[task_id]["logs"].append("Scraping completed successfully.")

    except Exception as e:
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["error"] = str(e)
        tasks_db[task_id]["logs"].append(f"Error occurred: {str(e)}")

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>GitHub Data Scraper API is running.</h1>")

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
    
    # Append conversation history for memory
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
        # Fallback to llama-3.3-70b-versatile if gpt-oss model json mode differs
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
def start_scrape(req: ScrapeRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    task_id = str(uuid.uuid4())
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

    thread = threading.Thread(target=run_scraper_task, args=(task_id, req.query, req.max_results))
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
