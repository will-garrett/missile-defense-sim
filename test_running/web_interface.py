from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import asyncio
from typing import Dict, Any
import yaml
import json
from datetime import datetime
import os

app = FastAPI(title="Test Running Web Interface")

# Templates
templates = Jinja2Templates(directory="templates")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables
current_scenario = None
scenario_results = None
test_status = "idle"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
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
        "active_tests": active_tests,
        "current_scenario": current_scenario,
        "scenario_results": scenario_results,
        "test_status": test_status
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
    return {
        "current_scenario": current_scenario,
        "scenario_results": scenario_results,
        "test_status": test_status,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/scenarios/run")
async def run_scenario(request: Request):
    global current_scenario, scenario_results, test_status
    
    try:
        body = await request.json()
        scenario_name = body.get("scenario_name")
        
        if not scenario_name:
            raise HTTPException(status_code=400, detail="scenario_name is required")
        
        # Load scenario configuration
        scenario_file = f"scenarios/{scenario_name}.yml"
        if not os.path.exists(scenario_file):
            raise HTTPException(status_code=404, detail=f"Scenario {scenario_name} not found")
        
        with open(scenario_file, 'r') as f:
            scenario_config = yaml.safe_load(f)
        
        current_scenario = scenario_name
        test_status = "running"
        
        # Run the scenario
        results = await execute_scenario(scenario_config)
        
        scenario_results = results
        test_status = "completed"
        
        return {"status": "success", "results": results}
        
    except Exception as e:
        test_status = "error"
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scenarios/stop")
async def stop_scenario():
    global test_status
    
    try:
        # Send stop command to simulation service
        async with httpx.AsyncClient() as client:
            response = await client.post("http://simulation_service:8000/scenarios/stop")
            
        test_status = "stopped"
        return {"status": "success", "message": "Scenario stopped"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def execute_scenario(scenario_config):
    """Execute a scenario and return results"""
    results = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "success_rate": 0.0,
        "avg_response_time": 0.0,
        "min_response_time": float('inf'),
        "max_response_time": 0.0,
        "response_times": []
    }
    
    async with httpx.AsyncClient() as client:
        # Setup scenario
        setup_data = {
            "scenario_name": scenario_config.get("name", "test_scenario"),
            "installations": scenario_config.get("installations", [])
        }
        
        try:
            response = await client.post("http://simulation_service:8000/scenarios/setup", json=setup_data)
            response.raise_for_status()
            results["successful_requests"] += 1
        except Exception as e:
            results["failed_requests"] += 1
            print(f"Setup failed: {e}")
        
        results["total_requests"] += 1
        
        # Execute launches
        launches = scenario_config.get("launches", [])
        for launch in launches:
            try:
                start_time = datetime.now()
                response = await client.post("http://attack_service:9000/launch", json=launch)
                response.raise_for_status()
                
                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds()
                results["response_times"].append(response_time)
                results["min_response_time"] = min(results["min_response_time"], response_time)
                results["max_response_time"] = max(results["max_response_time"], response_time)
                
                results["successful_requests"] += 1
                
            except Exception as e:
                results["failed_requests"] += 1
                print(f"Launch failed: {e}")
            
            results["total_requests"] += 1
            
            # Add delay between launches
            await asyncio.sleep(scenario_config.get("launch_delay", 1))
        
        # Calculate final statistics
        if results["response_times"]:
            results["avg_response_time"] = sum(results["response_times"]) / len(results["response_times"])
        
        if results["total_requests"] > 0:
            results["success_rate"] = results["successful_requests"] / results["total_requests"]
        
        if results["min_response_time"] == float('inf'):
            results["min_response_time"] = 0.0
    
    return results

@app.get("/api/metrics/missile_positions")
async def get_missile_positions():
    """Get missile positions from Prometheus metrics"""
    try:
        # Query Prometheus for missile position metrics
        async with httpx.AsyncClient() as client:
            response = await client.get("http://prometheus:9090/api/v1/query", params={
                "query": "missile_position"
            })
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("result", [])
            else:
                return []
    except Exception as e:
        print(f"Error fetching missile positions: {e}")
        return []

@app.get("/api/metrics/defense_positions")
async def get_defense_positions():
    """Get defense positions from Prometheus metrics"""
    try:
        # Query Prometheus for defense position metrics
        async with httpx.AsyncClient() as client:
            response = await client.get("http://prometheus:9090/api/v1/query", params={
                "query": "defense_position"
            })
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("result", [])
            else:
                return []
    except Exception as e:
        print(f"Error fetching defense positions: {e}")
        return []

@app.get("/api/metrics/radar_positions")
async def get_radar_positions():
    """Get radar positions from Prometheus metrics"""
    try:
        # Query Prometheus for radar position metrics
        async with httpx.AsyncClient() as client:
            response = await client.get("http://prometheus:9090/api/v1/query", params={
                "query": "radar_position"
            })
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("result", [])
            else:
                return []
    except Exception as e:
        print(f"Error fetching radar positions: {e}")
        return []

@app.get("/api/metrics/events")
async def get_events():
    """Get events from Prometheus metrics"""
    try:
        # Query Prometheus for event metrics
        async with httpx.AsyncClient() as client:
            response = await client.get("http://prometheus:9090/api/v1/query", params={
                "query": "event_location"
            })
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("result", [])
            else:
                return []
    except Exception as e:
        print(f"Error fetching events: {e}")
        return []

@app.post("/api/run/{scenario_name}")
async def run_scenario_api(scenario_name: str):
    """API endpoint to run a scenario"""
    global current_scenario, test_status
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"http://localhost:8000/run/{scenario_name}")
            
            if response.status_code == 200:
                current_scenario = scenario_name
                test_status = "running"
                return {"status": "success", "message": f"Scenario {scenario_name} started successfully"}
            else:
                return {"status": "error", "message": f"Failed to start scenario: {response.text}"}
                
    except Exception as e:
        return {"status": "error", "message": f"Error starting scenario: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 