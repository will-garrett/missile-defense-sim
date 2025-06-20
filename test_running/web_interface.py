from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
import asyncio
from typing import Dict, Any

app = FastAPI(title="Test Running Web Interface")

# Templates
templates = Jinja2Templates(directory="templates")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/scenarios", response_class=HTMLResponse)
async def scenarios_page(request: Request):
    """Scenarios management page"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/scenarios")
            scenarios = response.json()["scenarios"] if response.status_code == 200 else []
        except:
            scenarios = []
    
    return templates.TemplateResponse("scenarios.html", {
        "request": request, 
        "scenarios": scenarios
    })

@app.get("/run/{scenario_name}", response_class=HTMLResponse)
async def run_scenario_page(request: Request, scenario_name: str):
    """Run a specific scenario"""
    async with httpx.AsyncClient() as client:
        try:
            # Start the scenario
            response = await client.post(f"http://localhost:8000/run/{scenario_name}")
            if response.status_code == 200:
                result = response.json()
                message = f"Scenario {scenario_name} started successfully!"
                status = "success"
            else:
                message = f"Failed to start scenario: {response.text}"
                status = "error"
        except Exception as e:
            message = f"Error starting scenario: {str(e)}"
            status = "error"
    
    return templates.TemplateResponse("run_result.html", {
        "request": request,
        "scenario_name": scenario_name,
        "message": message,
        "status": status
    })

@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """Status monitoring page"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/status")
            active_tests = response.json()["active_tests"] if response.status_code == 200 else []
        except:
            active_tests = []
    
    return templates.TemplateResponse("status.html", {
        "request": request,
        "active_tests": active_tests
    })

@app.get("/api/scenarios")
async def get_scenarios():
    """API endpoint to get scenarios"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/scenarios")
            return response.json()
        except:
            return {"scenarios": []}

@app.get("/api/status")
async def get_status():
    """API endpoint to get test status"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/status")
            return response.json()
        except:
            return {"active_tests": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090) 