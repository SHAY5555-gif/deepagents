"""
Simple API Server for Parallel Agents
======================================

API server פשוט שמאפשר גישה לסוכנים המקבילים דרך web interface
עובד עם Python 3.10+
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from typing import Optional
import uvicorn

# ייבוא הסוכנים שלנו
from parallel_music_research_agent import create_parallel_music_agent, MusicResearchState

app = FastAPI(title="Parallel Agents API", version="1.0.0")

# הוסף CORS כדי לאפשר גישה מדפדפן
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    """בקשת מחקר"""
    task: str
    num_songs: Optional[int] = 30


class ResearchResponse(BaseModel):
    """תגובת מחקר"""
    success: bool
    task: str
    num_results: int
    num_errors: int
    execution_time: float
    report: str


# סוכן גלובלי (ייטען פעם אחת)
_agent = None


async def get_agent():
    """קבלת הסוכן (lazy loading)"""
    global _agent
    if _agent is None:
        _agent = create_parallel_music_agent()
    return _agent


@app.get("/", response_class=HTMLResponse)
async def home():
    """דף בית עם ממשק פשוט"""
    html = """
    <!DOCTYPE html>
    <html dir="rtl" lang="he">
    <head>
        <meta charset="utf-8">
        <title>Parallel Agents API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .form-group {
                margin: 20px 0;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #555;
            }
            input, textarea, button {
                width: 100%;
                padding: 12px;
                font-size: 16px;
                border: 1px solid #ddd;
                border-radius: 5px;
                box-sizing: border-box;
            }
            button {
                background: #4CAF50;
                color: white;
                border: none;
                cursor: pointer;
                font-weight: bold;
                margin-top: 10px;
            }
            button:hover {
                background: #45a049;
            }
            button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            #result {
                margin-top: 30px;
                padding: 20px;
                background: #f9f9f9;
                border-radius: 5px;
                white-space: pre-wrap;
                font-family: monospace;
                display: none;
            }
            .loading {
                text-align: center;
                color: #666;
                display: none;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #3498db;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            .stat-card {
                background: #e3f2fd;
                padding: 15px;
                border-radius: 5px;
                text-align: center;
            }
            .stat-value {
                font-size: 24px;
                font-weight: bold;
                color: #1976d2;
            }
            .stat-label {
                color: #666;
                font-size: 14px;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎼 מערכת תזמור סוכנים במקביל</h1>

            <div class="form-group">
                <label for="task">משימה:</label>
                <textarea id="task" rows="3" placeholder="לדוגמה: חפש מידע על 30 השירים הפופולריים של 2024">חפש מידע על 30 שירים פופולריים</textarea>
            </div>

            <div class="form-group">
                <label for="num_songs">מספר שירים (סוכנים במקביל):</label>
                <input type="number" id="num_songs" value="30" min="1" max="100">
            </div>

            <button onclick="runResearch()" id="runBtn">הרץ מחקר במקביל</button>

            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>מריץ סוכנים במקביל... אנא המתן</p>
            </div>

            <div id="stats"></div>
            <div id="result"></div>
        </div>

        <script>
            async function runResearch() {
                const task = document.getElementById('task').value;
                const num_songs = parseInt(document.getElementById('num_songs').value);
                const runBtn = document.getElementById('runBtn');
                const loading = document.getElementById('loading');
                const result = document.getElementById('result');
                const stats = document.getElementById('stats');

                // הסתר תוצאות קודמות
                result.style.display = 'none';
                stats.innerHTML = '';

                // הצג loading
                loading.style.display = 'block';
                runBtn.disabled = true;

                const startTime = Date.now();

                try {
                    const response = await fetch('/api/research', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            task: task,
                            num_songs: num_songs
                        })
                    });

                    if (!response.ok) {
                        throw new Error('שגיאה בשרת');
                    }

                    const data = await response.json();
                    const endTime = Date.now();
                    const clientTime = (endTime - startTime) / 1000;

                    // הצג סטטיסטיקות
                    stats.innerHTML = `
                        <div class="stats">
                            <div class="stat-card">
                                <div class="stat-value">${data.num_results}</div>
                                <div class="stat-label">תוצאות מוצלחות</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${data.num_errors}</div>
                                <div class="stat-label">שגיאות</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${data.execution_time.toFixed(2)}s</div>
                                <div class="stat-label">זמן ריצה בשרת</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${clientTime.toFixed(2)}s</div>
                                <div class="stat-label">זמן כולל</div>
                            </div>
                        </div>
                    `;

                    // הצג דוח
                    result.textContent = data.report;
                    result.style.display = 'block';

                } catch (error) {
                    result.textContent = 'שגיאה: ' + error.message;
                    result.style.display = 'block';
                } finally {
                    loading.style.display = 'none';
                    runBtn.disabled = false;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/api/research", response_model=ResearchResponse)
async def run_research(request: ResearchRequest):
    """
    מריץ מחקר במקביל

    Example:
        POST /api/research
        {
            "task": "Research 30 popular songs",
            "num_songs": 30
        }
    """
    import time

    try:
        # קבל את הסוכן
        agent = await get_agent()

        # הכן state
        # עדכן את מספר השירים בהתאם לבקשה
        songs = [
            {"id": i, "title": f"Song {i}", "artist": f"Artist {i}"}
            for i in range(1, request.num_songs + 1)
        ]

        start_time = time.time()

        # הרץ את הסוכן
        result = await agent.ainvoke({
            "original_task": request.task,
            "songs_to_research": songs,
            "research_results": [],
            "errors": [],
            "final_report": ""
        })

        execution_time = time.time() - start_time

        return ResearchResponse(
            success=True,
            task=request.task,
            num_results=len(result.get("research_results", [])),
            num_errors=len(result.get("errors", [])),
            execution_time=execution_time,
            report=result.get("final_report", "")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """בדיקת תקינות"""
    return {"status": "ok", "message": "Parallel Agents API is running"}


@app.get("/api/info")
async def get_info():
    """מידע על ה-API"""
    return {
        "title": "Parallel Agents API",
        "version": "1.0.0",
        "description": "API for running parallel research agents using LangGraph",
        "endpoints": {
            "/": "Web interface",
            "/api/research": "Run parallel research (POST)",
            "/api/health": "Health check",
            "/api/info": "API information",
            "/docs": "OpenAPI documentation"
        }
    }


if __name__ == "__main__":
    print("=" * 70)
    print("Starting Parallel Agents API Server")
    print("=" * 70)
    print("\nServer will be available at:")
    print("  - Web Interface: http://localhost:8000")
    print("  - API Docs: http://localhost:8000/docs")
    print("  - Health Check: http://localhost:8000/api/health")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 70)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
