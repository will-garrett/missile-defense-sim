from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import httpx
import asyncio
import yaml
import json
import time
from datetime import datetime
import logging
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Test Running Service", version="1.0.0")

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

class ScenarioConfig(BaseModel):
    name: str
    description: str
    duration_seconds: int
    ramp_up_seconds: int
    max_concurrent_users: int
    tasks: List[Dict[str, Any]]

class TestRun(BaseModel):
    scenario_name: str
    status: str = "pending"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    results: Dict[str, Any] = {}

class TestRunner:
    def __init__(self):
        self.active_tests: Dict[str, TestRun] = {}
        self.scenarios: Dict[str, ScenarioConfig] = {}
        self.load_scenarios()
    
    def load_scenarios(self):
        """Load scenario configurations from YAML files"""
        try:
            with open("scenarios.yml", "r") as f:
                scenarios_data = yaml.safe_load(f)
                for scenario in scenarios_data.get("scenarios", []):
                    self.scenarios[scenario["name"]] = ScenarioConfig(**scenario)
            logger.info(f"Loaded {len(self.scenarios)} scenarios")
        except FileNotFoundError:
            logger.warning("scenarios.yml not found, using default scenarios")
            self.create_default_scenarios()
        except Exception as e:
            logger.error(f"Error loading scenarios: {e}")
            self.create_default_scenarios()
    
    def create_default_scenarios(self):
        """Create default scenarios if YAML file is not available"""
        default_scenarios = {
            "simple_defense": ScenarioConfig(
                name="simple_defense",
                description="Simple missile defense scenario with basic installations",
                duration_seconds=300,
                ramp_up_seconds=30,
                max_concurrent_users=10,
                tasks=[
                    {
                        "name": "setup_simulation",
                        "weight": 1,
                        "endpoint": "POST /scenarios/setup",
                        "data": {
                            "scenario_name": "simple_defense",
                            "installations": [
                                {
                                    "platform_type_nickname": "AN/TPY-2",
                                    "callsign": "RADAR_HAWAII_01",
                                    "lat": 21.31,
                                    "lon": -157.86,
                                    "altitude_m": 100,
                                    "is_mobile": False,
                                    "ammo_count": 0
                                },
                                {
                                    "platform_type_nickname": "Aegis BMD SM-3",
                                    "callsign": "DEF_AEGIS_01",
                                    "lat": 21.33,
                                    "lon": -157.88,
                                    "altitude_m": 0,
                                    "is_mobile": True,
                                    "ammo_count": 32
                                }
                            ]
                        }
                    },
                    {
                        "name": "launch_missile",
                        "weight": 3,
                        "endpoint": "POST /launch",
                        "params": {
                            "platform_type": "UGM-133 Trident II",
                            "lat": 25.0,
                            "lon": -155.0,
                            "target_lat": 21.31,
                            "target_lon": -157.86,
                            "altitude_m": -200
                        }
                    },
                    {
                        "name": "check_status",
                        "weight": 2,
                        "endpoint": "GET /installations"
                    }
                ]
            ),
            "intensive_attack": ScenarioConfig(
                name="intensive_attack",
                description="High-intensity attack scenario",
                duration_seconds=600,
                ramp_up_seconds=60,
                max_concurrent_users=20,
                tasks=[
                    {
                        "name": "launch_missile",
                        "weight": 5,
                        "endpoint": "POST /launch",
                        "params": {
                            "platform_type": "UGM-133 Trident II",
                            "lat": 25.0,
                            "lon": -155.0,
                            "target_lat": 21.31,
                            "target_lon": -157.86,
                            "altitude_m": -200
                        }
                    },
                    {
                        "name": "launch_cruise_missile",
                        "weight": 3,
                        "endpoint": "POST /launch",
                        "params": {
                            "platform_type": "CJ-10",
                            "lat": 20.0,
                            "lon": -160.0,
                            "target_lat": 21.31,
                            "target_lon": -157.86,
                            "altitude_m": 15000
                        }
                    }
                ]
            )
        }
        self.scenarios.update(default_scenarios)

test_runner = TestRunner()

# Web Interface Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/scenarios", response_class=HTMLResponse)
async def scenarios_page(request: Request):
    """Scenarios management page"""
    return templates.TemplateResponse("scenarios.html", {
        "request": request, 
        "scenarios": list(test_runner.scenarios.values())
    })

@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """Status monitoring page"""
    return templates.TemplateResponse("status.html", {
        "request": request,
        "active_tests": list(test_runner.active_tests.values())
    })

# API Routes
@app.get("/api")
async def root():
    return {"message": "Test Running Service", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "active_tests": len(test_runner.active_tests)}

@app.get("/api/scenarios")
async def list_scenarios():
    """List all available scenarios"""
    return {
        "scenarios": [
            {
                "name": scenario.name,
                "description": scenario.description,
                "duration_seconds": scenario.duration_seconds,
                "max_concurrent_users": scenario.max_concurrent_users
            }
            for scenario in test_runner.scenarios.values()
        ]
    }

@app.get("/api/scenarios/{scenario_name}")
async def get_scenario(scenario_name: str):
    """Get details of a specific scenario"""
    if scenario_name not in test_runner.scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    scenario = test_runner.scenarios[scenario_name]
    return {
        "name": scenario.name,
        "description": scenario.description,
        "duration_seconds": scenario.duration_seconds,
        "ramp_up_seconds": scenario.ramp_up_seconds,
        "max_concurrent_users": scenario.max_concurrent_users,
        "tasks": scenario.tasks
    }

@app.post("/api/run/{scenario_name}")
async def run_scenario(scenario_name: str, background_tasks: BackgroundTasks):
    """Start running a scenario"""
    if scenario_name not in test_runner.scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Check if scenario is already running (not completed)
    if scenario_name in test_runner.active_tests:
        existing_test = test_runner.active_tests[scenario_name]
        if existing_test.status in ["starting", "running", "stopping"]:
            raise HTTPException(status_code=400, detail="Scenario already running")
        # If completed, remove the old test run to allow re-running
        del test_runner.active_tests[scenario_name]
    
    test_run = TestRun(scenario_name=scenario_name, status="starting")
    test_runner.active_tests[scenario_name] = test_run
    
    # Start the scenario in the background
    background_tasks.add_task(run_scenario_background, scenario_name)
    
    return {
        "message": f"Scenario {scenario_name} started",
        "test_id": scenario_name,
        "status": "starting"
    }

@app.get("/api/status/{scenario_name}")
async def get_test_status(scenario_name: str):
    """Get the status of a running test"""
    if scenario_name not in test_runner.active_tests:
        raise HTTPException(status_code=404, detail="Test not found")
    
    test_run = test_runner.active_tests[scenario_name]
    return {
        "scenario_name": test_run.scenario_name,
        "status": test_run.status,
        "start_time": test_run.start_time,
        "end_time": test_run.end_time,
        "results": test_run.results
    }

@app.get("/api/status")
async def get_all_test_status():
    """Get status of all tests"""
    return {
        "active_tests": [
            {
                "scenario_name": test_run.scenario_name,
                "status": test_run.status,
                "start_time": test_run.start_time,
                "end_time": test_run.end_time
            }
            for test_run in test_runner.active_tests.values()
        ]
    }

@app.delete("/api/stop/{scenario_name}")
async def stop_scenario(scenario_name: str):
    """Stop a running scenario and clean up all simulation data"""
    if scenario_name not in test_runner.active_tests:
        raise HTTPException(status_code=404, detail="Test not found")
    
    test_run = test_runner.active_tests[scenario_name]
    test_run.status = "stopping"
    
    # Clean up simulation state
    await cleanup_simulation_state()
    
    # Remove the test from active tests
    del test_runner.active_tests[scenario_name]
    
    return {"message": f"Scenario {scenario_name} stopped and cleaned up"}

async def cleanup_simulation_state():
    """Clean up all simulation state across all services"""
    logger.info("Starting simulation cleanup...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Clean up simulation service
        try:
            logger.info("Cleaning up simulation service...")
            response = await client.post("http://simulation_service:8000/cleanup")
            if response.status_code == 200:
                logger.info(f"Simulation service cleanup: {response.json()}")
            else:
                logger.warning(f"Simulation service cleanup failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to cleanup simulation service: {e}")
        
        # Clean up attack service installations
        try:
            logger.info("Cleaning up attack service installations...")
            response = await client.get("http://attack_service:9000/installations")
            if response.status_code == 200:
                installations = response.json()
                for inst in installations:
                    callsign = inst.get("callsign")
                    if callsign:
                        await client.delete(f"http://attack_service:9000/installations/{callsign}")
                        logger.info(f"Deleted installation {callsign} from attack service")
        except Exception as e:
            logger.warning(f"Failed to cleanup attack service: {e}")
        
        # Send abort command to simulation service
        try:
            logger.info("Sending abort command to simulation service...")
            response = await client.post("http://simulation_service:8000/abort")
            if response.status_code == 200:
                logger.info(f"Simulation service abort: {response.json()}")
            else:
                logger.warning(f"Simulation service abort failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to abort simulation service: {e}")
    
    logger.info("Simulation cleanup completed")

async def setup_installations_on_services(installations: List[Dict[str, Any]]):
    """Create installations on both simulation_service and attack_service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for inst in installations:
            # Prepare payload for both services
            sim_payload = inst.copy()
            atk_payload = {
                "platform_nickname": inst.get("platform_type_nickname", ""),
                "callsign": inst.get("callsign", ""),
                "lat": inst.get("lat", 0),
                "lon": inst.get("lon", 0),
                "altitude_m": inst.get("altitude_m", 0),
                "is_mobile": inst.get("is_mobile", False),
                "ammo_count": inst.get("ammo_count", 0)
            }
            # Create on simulation_service
            try:
                await client.post("http://simulation_service:8000/installations", json=sim_payload)
            except Exception as e:
                logger.warning(f"Failed to create installation on simulation_service: {e}")
            # Create on attack_service
            try:
                await client.post("http://attack_service:9000/installations", json=atk_payload)
            except Exception as e:
                logger.warning(f"Failed to create installation on attack_service: {e}")

async def delete_installation_on_services(callsign: str):
    """Delete installation by callsign from both services."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await client.delete(f"http://simulation_service:8000/installations/{callsign}")
        except Exception as e:
            logger.warning(f"Failed to delete installation on simulation_service: {e}")
        try:
            await client.delete(f"http://attack_service:9000/installations/{callsign}")
        except Exception as e:
            logger.warning(f"Failed to delete installation on attack_service: {e}")

async def reset_all_installations_on_services():
    """Delete all installations from both services."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get all installations from both services
        for svc, url in [
            ("simulation_service", "http://simulation_service:8000/installations"),
            ("attack_service", "http://attack_service:9000/installations")
        ]:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    installs = resp.json()
                    for inst in installs:
                        callsign = inst.get("callsign")
                        if callsign:
                            await client.delete(f"{url}/{callsign}")
            except Exception as e:
                logger.warning(f"Failed to reset installations on {svc}: {e}")

@app.post("/api/reset")
async def reset_all_installations():
    """Remove all installations from both simulation_service and attack_service."""
    await reset_all_installations_on_services()
    return {"message": "All installations removed from both services."}

@app.delete("/api/remove/{callsign}")
async def remove_installation(callsign: str):
    """Remove a specific installation by callsign from both services."""
    await delete_installation_on_services(callsign)
    return {"message": f"Installation {callsign} removed from both services."}

async def wait_for_installations_in_attack_service(installations, timeout=10):
    """Poll attack_service until all installations are present or timeout."""
    callsigns = {inst['callsign'] for inst in installations}
    url = "http://attack_service:9000/installations"
    start = time.time()
    async with httpx.AsyncClient(timeout=10.0) as client:
        while time.time() - start < timeout:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json() if hasattr(resp, 'json') else resp.json
                found = {inst['callsign'] for inst in data}
                if callsigns.issubset(found):
                    logger.info(f"All installations present in attack_service: {callsigns}")
                    return True
                else:
                    logger.info(f"Waiting for installations in attack_service. Needed: {callsigns}, Found: {found}")
            except Exception as e:
                logger.warning(f"Error polling attack_service/installations: {e}")
            await asyncio.sleep(0.5)
    logger.error(f"Timeout waiting for installations in attack_service: {callsigns}")
    return False

async def run_scenario_background(scenario_name: str):
    """Run a scenario in the background"""
    scenario = test_runner.scenarios[scenario_name]
    test_run = test_runner.active_tests[scenario_name]
    test_run.status = "running"
    test_run.start_time = datetime.now()
    logger.info(f"Starting scenario: {scenario_name}")
    # Setup phase: create installations on both services if present
    for task in scenario.tasks:
        if task["endpoint"].startswith("POST ") and ("setup" in task["endpoint"] or "defense" in task["name"]):
            data = task.get("data", {})
            installations = data.get("installations", [])
            if installations:
                await setup_installations_on_services(installations)
                # Wait for attack_service to register all installations
                await wait_for_installations_in_attack_service(installations)
            # Also call the original setup endpoint (for simulation_service)
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    await client.post(f"http://simulation_service:8000{task['endpoint'][5:]}", json=data)
                except Exception as e:
                    logger.warning(f"Setup POST failed: {e}")

    # Initialize counters
    total_requests = 0
    successful_requests = 0
    failed_requests = 0
    response_times = []
    
    # Calculate task distribution
    total_weight = sum(task["weight"] for task in scenario.tasks)
    task_probabilities = [task["weight"] / total_weight for task in scenario.tasks]
    
    # Ramp up period
    ramp_up_delay = scenario.ramp_up_seconds / scenario.max_concurrent_users
    
    # Main execution loop
    start_time = time.time()
    end_time = start_time + scenario.duration_seconds
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while time.time() < end_time and test_run.status == "running":
            # Select task based on weights
            import random
            selected_task = random.choices(scenario.tasks, weights=task_probabilities)[0]
            
            try:
                # Execute the task
                task_start = time.time()
                
                if selected_task["endpoint"].startswith("GET"):
                    url = f"http://simulation_service:8000{selected_task['endpoint'][4:]}"
                    response = await client.get(url)
                elif selected_task["endpoint"].startswith("POST"):
                    if "launch" in selected_task["endpoint"]:
                        url = f"http://attack_service:9000{selected_task['endpoint'][5:]}"
                        logger.info(f"Sending LAUNCH request to {url} with data: {selected_task.get('data', {})}")
                        response = await client.post(url, json=selected_task.get("data", {}))
                    else:
                        url = f"http://simulation_service:8000{selected_task['endpoint'][5:]}"
                        logger.info(f"Sending POST to {url} with data: {selected_task.get('data', {})}")
                        response = await client.post(url, json=selected_task.get("data", {}))
                else:
                    logger.warning(f"Unsupported endpoint: {selected_task['endpoint']}")
                    continue
                
                task_end = time.time()
                response_time = task_end - task_start
                response_times.append(response_time)
                
                total_requests += 1
                if response.status_code < 400:
                    successful_requests += 1
                else:
                    failed_requests += 1
                    logger.warning(f"Request failed: {response.status_code} - {response.text}")
                
                # Update results
                test_run.results = {
                    "total_requests": total_requests,
                    "successful_requests": successful_requests,
                    "failed_requests": failed_requests,
                    "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
                    "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
                    "min_response_time": min(response_times) if response_times else 0,
                    "max_response_time": max(response_times) if response_times else 0
                }
                
                # Wait between requests (simulate user think time)
                await asyncio.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"Error executing task {selected_task['name']}: {e}")
                failed_requests += 1
                total_requests += 1
    
    # Mark test as completed
    test_run.status = "completed"
    test_run.end_time = datetime.now()
    
    logger.info(f"Completed scenario: {scenario_name}")
    logger.info(f"Results: {test_run.results}")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 