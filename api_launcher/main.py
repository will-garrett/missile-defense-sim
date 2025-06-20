import uuid, time, os, asyncio
from fastapi import FastAPI
from prometheus_client import start_http_server, Counter
import asyncpg, zmq.asyncio, json

DB_DSN = os.getenv("DB_DSN")
app = FastAPI()
start_http_server(8000)          # /metrics
LAUNCHES = Counter("missile_launches","Total missiles launched")

ctx = zmq.asyncio.Context()
pub = ctx.socket(zmq.PUB)
pub.bind("tcp://0.0.0.0:5556")   # tracks channel to track_sim

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
async def db_pool():
    app.state.pool = await create_db_pool_with_retry(DB_DSN)

@app.post("/launch")
async def launch(lat: float, lon: float,
                 targetLat: float, targetLon: float,
                 missileType: str = "SCUD-C"):
    mid = f"M{uuid.uuid4().hex[:6]}"
    LAUNCHES.inc()

    async with app.state.pool.acquire() as con:
        mt_id = await con.fetchval("SELECT id FROM missile_type WHERE name=$1", missileType)
        await con.execute("""
            INSERT INTO missile_flight
              (id,type_id,launch_ts,launch_geom,target_geom,vx,vy,vz)
            VALUES ($1,$2,now(),
                    ST_SetSRID(ST_MakePoint($3,$4),4326)::geography,
                    ST_SetSRID(ST_MakePoint($5,$6),4326)::geography,
                    0,0,0)""",
            mid, mt_id, lon, lat, targetLon, targetLat)

    await pub.send_json({
        "id": mid, "ts": time.time(),
        "lat": lat, "lon": lon, "alt_m": 25000,
        "vx": 0, "vy": 0, "vz": -50
    })
    return {"missile_id": mid, "status": "launched"}