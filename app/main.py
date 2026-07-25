
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.auth import require_auth
from app.settings import get_settings
from app.queries import dashboard_state
from app.db import connection

app=FastAPI(title="Living Economic Map", version="3.50")
templates=Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
def health():
    try:
        with connection() as conn:
            conn.cursor().execute("SELECT 1")
        db="ok"
    except Exception as exc:
        return JSONResponse({"status":"degraded","database":str(exc)},status_code=503)
    return {"status":"ok","database":db,"environment":get_settings().app_env}

@app.get("/",response_class=HTMLResponse)
def dashboard(request:Request,user=Depends(require_auth)):
    return templates.TemplateResponse("dashboard.html",{"request":request,"state":dashboard_state(),"settings":get_settings(),"user":user})

@app.get("/api/state")
def api_state(user=Depends(require_auth)):
    return dashboard_state()
