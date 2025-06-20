import uuid
import time
import os
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import start_http_server, Counter
import asyncpg
import nats
from nats.aio.client import Client as NATS

DB_DSN = os.getenv("DB_DSN")
app = FastAPI(title="Missile Defense API", version="2.0.0")
start_http_server(8000)
LAUNCHES = Counter("missile_launches", "Total missiles launched")
PLATFORM_CREATIONS = Counter("platform_creations", "Total platform installations created")

# NATS client for communication with simulation service
nats_client: Optional[NATS] = None

class LaunchRequest(BaseModel):
    platform_nickname: str
    launch_callsign: str
    launch_lat: float
    launch_lon: float
    launch_alt: float = 0
    target_lat: float
    target_lon: float
    target_alt: float = 0
    missile_type: str = "attack"

class InstallationRequest(BaseModel):
    platform_nickname: str
    callsign: str
    lat: float
    lon: float
    altitude_m: float = 0
    is_mobile: bool = False
    ammo_count: int = 0

async def create_db_pool_with_retry(dsn, max_retries=30, delay=2):
    """Create database pool with retry logic for startup timing"""
    for attempt in range(max_retries):
        try:
            pool = await asyncpg.create_pool(dsn=dsn)
            print(f"Database connection established on attempt {attempt + 1}")
            return pool
        except Exception as e:
            print(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
            else:
                raise
    raise Exception("Failed to connect to database after all retries")

@app.on_event("startup")
async def startup():
    app.state.pool = await create_db_pool_with_retry(DB_DSN)
    
    # Connect to NATS
    global nats_client
    nats_client = NATS()
    await nats_client.connect("nats://nats:4222")
    print("Connected to NATS")

@app.on_event("shutdown")
async def shutdown():
    if nats_client:
        await nats_client.close()

@app.get("/")
async def root():
    return {"message": "Missile Defense API v2.0", "status": "operational"}

@app.get("/platforms")
async def get_platforms():
    """Get all available platform types"""
    async with app.state.pool.acquire() as con:
        platforms = await con.fetch("""
            SELECT id, nickname, category, description, max_speed_mps, 
                   max_range_m, max_altitude_m, blast_radius_m, detection_range_m,
                   sweep_rate_deg_per_sec, reload_time_sec, accuracy_percent
            FROM platform_type
            ORDER BY category, nickname
        """)
        return [dict(p) for p in platforms]

@app.get("/installations")
async def get_installations():
    """Get all installations"""
    async with app.state.pool.acquire() as con:
        installations = await con.fetch("""
            SELECT i.id, i.callsign, i.geom, i.altitude_m, i.is_mobile, 
                   i.current_speed_mps, i.heading_deg, i.status, i.ammo_count,
                   pt.nickname as platform_nickname, pt.category
            FROM installation i
            JOIN platform_type pt ON i.platform_type_id = pt.id
            ORDER BY pt.category, i.callsign
        """)
        return [dict(i) for i in installations]

@app.post("/installations")
async def create_installation(request: InstallationRequest):
    """Create a new installation"""
    async with app.state.pool.acquire() as con:
        # Get platform type ID
        platform_id = await con.fetchval(
            "SELECT id FROM platform_type WHERE nickname = $1",
            request.platform_nickname
        )
        
        if not platform_id:
            raise HTTPException(status_code=404, detail=f"Platform {request.platform_nickname} not found")
        
        # Check if callsign already exists
        existing = await con.fetchval(
            "SELECT id FROM installation WHERE callsign = $1",
            request.callsign
        )
        
        if existing:
            raise HTTPException(status_code=400, detail=f"Installation with callsign {request.callsign} already exists")
        
        # Create installation
        installation_id = await con.fetchval("""
            INSERT INTO installation (
                platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count
            ) VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326)::geography, $5, $6, $7)
            RETURNING id
        """, platform_id, request.callsign, request.lon, request.lat, 
             request.altitude_m, request.is_mobile, request.ammo_count)
        
        PLATFORM_CREATIONS.inc()
        
        return {
            "installation_id": installation_id,
            "callsign": request.callsign,
            "status": "created"
        }

@app.post("/launch")
async def launch_missile(request: LaunchRequest):
    """Launch a missile"""
    
    # Validate platform exists
    async with app.state.pool.acquire() as con:
        platform = await con.fetchrow(
            "SELECT id, category FROM platform_type WHERE nickname = $1",
            request.platform_nickname
        )
        
        if not platform:
            raise HTTPException(status_code=404, detail=f"Platform {request.platform_nickname} not found")
        
        # Validate installation exists
        installation = await con.fetchrow(
            "SELECT id FROM installation WHERE callsign = $1",
            request.launch_callsign
        )
        
        if not installation:
            raise HTTPException(status_code=404, detail=f"Installation {request.launch_callsign} not found")
        
        # Check if installation has ammo (for counter-defense systems)
        if platform['category'] == 'counter_defense':
            ammo = await con.fetchval(
                "SELECT ammo_count FROM installation WHERE callsign = $1",
                request.launch_callsign
            )
            
            if ammo <= 0:
                raise HTTPException(status_code=400, detail="Installation has no ammunition")
            
            # Decrement ammo
            await con.execute(
                "UPDATE installation SET ammo_count = ammo_count - 1 WHERE callsign = $1",
                request.launch_callsign
            )
    
    # Send launch request to simulation service via NATS
    launch_message = {
        "type": "missile_launch",
        "platform_nickname": request.platform_nickname,
        "launch_callsign": request.launch_callsign,
        "launch_lat": request.launch_lat,
        "launch_lon": request.launch_lon,
        "launch_alt": request.launch_alt,
        "target_lat": request.target_lat,
        "target_lon": request.target_lon,
        "target_alt": request.target_alt,
        "missile_type": request.missile_type,
        "timestamp": time.time()
    }
    
    await nats_client.publish("simulation.launch", str(launch_message).encode())
    LAUNCHES.inc()
    
    return {
        "status": "launch_requested",
        "platform": request.platform_nickname,
        "launch_installation": request.launch_callsign,
        "target": {"lat": request.target_lat, "lon": request.target_lon, "alt": request.target_alt}
    }

@app.get("/missiles/active")
async def get_active_missiles():
    """Get all active missiles"""
    async with app.state.pool.acquire() as con:
        missiles = await con.fetch("""
            SELECT am.id, am.callsign, am.missile_type, am.launch_ts, am.status,
                   am.current_geom, am.current_altitude_m,
                   am.velocity_x_mps, am.velocity_y_mps, am.velocity_z_mps,
                   am.fuel_remaining_kg, pt.nickname as platform_nickname
            FROM active_missile am
            JOIN platform_type pt ON am.platform_type_id = pt.id
            WHERE am.status = 'active'
            ORDER BY am.launch_ts DESC
        """)
        return [dict(m) for m in missiles]

@app.get("/detections/recent")
async def get_recent_detections(limit: int = 50):
    """Get recent detection events"""
    async with app.state.pool.acquire() as con:
        detections = await con.fetch("""
            SELECT de.id, de.detection_ts, de.detection_geom, de.detection_altitude_m,
                   de.signal_strength_db, de.confidence_percent,
                   i.callsign as radar_callsign, am.callsign as missile_callsign
            FROM detection_event de
            JOIN installation i ON de.detection_installation_id = i.id
            JOIN active_missile am ON de.detected_missile_id = am.id
            ORDER BY de.detection_ts DESC
            LIMIT $1
        """, limit)
        return [dict(d) for d in detections]

@app.get("/engagements/recent")
async def get_recent_engagements(limit: int = 50):
    """Get recent engagements"""
    async with app.state.pool.acquire() as con:
        engagements = await con.fetch("""
            SELECT e.id, e.engagement_ts, e.intercept_geom, e.intercept_altitude_m,
                   e.status, e.intercept_distance_m,
                   am1.callsign as target_callsign, am2.callsign as defense_callsign,
                   i.callsign as launch_installation
            FROM engagement e
            JOIN active_missile am1 ON e.target_missile_id = am1.id
            JOIN active_missile am2 ON e.defense_missile_id = am2.id
            JOIN installation i ON e.launch_installation_id = i.id
            ORDER BY e.engagement_ts DESC
            LIMIT $1
        """, limit)
        return [dict(e) for e in engagements]

@app.get("/detonations/recent")
async def get_recent_detonations(limit: int = 50):
    """Get recent detonation events"""
    async with app.state.pool.acquire() as con:
        detonations = await con.fetch("""
            SELECT de.id, de.detonation_ts, de.detonation_geom, de.detonation_altitude_m,
                   de.blast_radius_m, de.casualties_estimated, de.damage_assessment,
                   am.callsign as missile_callsign
            FROM detonation_event de
            JOIN active_missile am ON de.missile_id = am.id
            ORDER BY de.detonation_ts DESC
            LIMIT $1
        """, limit)
        return [dict(d) for d in detonations]

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        async with app.state.pool.acquire() as con:
            await con.fetchval("SELECT 1")
        
        if nats_client and nats_client.is_connected:
            return {"status": "healthy", "database": "connected", "nats": "connected"}
        else:
            return {"status": "degraded", "database": "connected", "nats": "disconnected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}