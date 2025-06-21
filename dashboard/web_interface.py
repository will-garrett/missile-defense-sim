from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
import asyncpg
import asyncio
from typing import Dict, Any, List
import json
from datetime import datetime
import os
from urllib.parse import unquote

class Action(BaseModel):
    type: str
    details: Dict[str, Any]
    time_from_start_seconds: int

class ScenarioUpdate(BaseModel):
    actions: List[Action]

app = FastAPI(title="Dashboard Service API")

# Database connection pool
db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    db_dsn = os.getenv("DB_DSN", "postgresql://missiles:missiles@localhost/missilesim")
    db_pool = await asyncpg.create_pool(dsn=db_dsn)

@app.on_event("shutdown")
async def shutdown():
    await db_pool.close()

@app.get("/api/scenarios")
async def get_scenarios():
    """API endpoint to get all actions grouped by scenario."""
    async with db_pool.acquire() as connection:
        rows = await connection.fetch("""
            SELECT scenario_name, time_from_start_seconds, action
            FROM scenarios 
            ORDER BY scenario_name, time_from_start_seconds
        """)
        
        scenarios = {}
        for row in rows:
            name = row['scenario_name']
            if name not in scenarios:
                scenarios[name] = []
            
            action_data = json.loads(row['action'])
            # The action column is a JSON string with a single key (the action type)
            action_type = list(action_data.keys())[0]
            action_details = action_data[action_type]

            scenarios[name].append({
                "type": action_type,
                "details": action_details,
                "time_from_start_seconds": row['time_from_start_seconds'],
            })
            
    return {"scenarios": scenarios}

@app.get("/api/scenarios/{scenario_name}")
async def get_scenario_by_name(scenario_name: str):
    """API endpoint to get a single scenario by name."""
    decoded_name = unquote(scenario_name)
    async with db_pool.acquire() as connection:
        rows = await connection.fetch("""
            SELECT time_from_start_seconds, action
            FROM scenarios 
            WHERE scenario_name = $1
            ORDER BY time_from_start_seconds
        """, decoded_name)
        
        if not rows:
            raise HTTPException(status_code=404, detail="Scenario not found")

        actions = []
        for row in rows:
            action_data = json.loads(row['action'])
            action_type = list(action_data.keys())[0]
            action_details = action_data[action_type]

            actions.append({
                "type": action_type,
                "details": action_details,
                "time_from_start_seconds": row['time_from_start_seconds'],
            })
            
    return {"actions": actions}

@app.get("/api/platform-types")
async def get_platform_types(category: str = None):
    """API endpoint to get all platform types, with optional filtering by category."""
    async with db_pool.acquire() as connection:
        if category:
            query = "SELECT nickname, category FROM platform_type WHERE category = $1 ORDER BY nickname"
            rows = await connection.fetch(query, category)
        else:
            query = "SELECT nickname, category FROM platform_type ORDER BY nickname"
            rows = await connection.fetch(query)

        platform_types = [dict(row) for row in rows]
    return {"platform_types": platform_types}

@app.get("/api/status")
async def get_status():
    """API endpoint to get test status"""
    return {
        "timestamp": datetime.now().isoformat()
    }

@app.put("/api/scenarios/{scenario_name}")
async def update_scenario(scenario_name: str, scenario_update: ScenarioUpdate):
    """API endpoint to update or create a scenario."""
    async with db_pool.acquire() as connection:
        async with connection.transaction():
            # Delete all existing actions for this scenario
            await connection.execute(
                "DELETE FROM scenarios WHERE scenario_name = $1",
                scenario_name
            )

            # Insert all the new actions
            for action_item in scenario_update.actions:
                # The 'action' column in the DB stores a JSON object
                # where the key is the action type.
                action_data = {action_item.type: action_item.details}
                await connection.execute(
                    """
                    INSERT INTO scenarios (scenario_name, time_from_start_seconds, action)
                    VALUES ($1, $2, $3)
                    """,
                    scenario_name,
                    action_item.time_from_start_seconds,
                    json.dumps(action_data),
                )
    return {"status": "success", "scenario_name": scenario_name}

@app.delete("/api/scenarios/{scenario_name}")
async def delete_scenario(scenario_name: str):
    """API endpoint to delete a scenario"""
    async with db_pool.acquire() as connection:
        await connection.execute(
            "DELETE FROM scenarios WHERE scenario_name = $1",
            scenario_name
        )
    return {"status": "success", "scenario_name": scenario_name}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 