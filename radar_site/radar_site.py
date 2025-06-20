import zmq.asyncio, json, os, math, time, asyncio, asyncpg
from prometheus_client import start_http_server, Counter
from nats.aio.client import Client as NATS

CALL_SIGN = os.getenv("CALL_SIGN","RAD_X")
DB_DSN = os.getenv("DB_DSN")

start_http_server(8000)
DETECTIONS = Counter("radar_detections","Detections",["radar"])

ctx = zmq.asyncio.Context()
sock = ctx.socket(zmq.SUB)
sock.connect("tcp://track_sim:5557")
sock.setsockopt_string(zmq.SUBSCRIBE,"")

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

async def main():
    pool = await create_db_pool_with_retry(DB_DSN)
    nats = NATS()
    await nats.connect("nats://nats:4222")
    
    rng = await pool.fetchval("""
        SELECT rt.max_range_m FROM radar_site rs
        JOIN radar_type rt ON rt.id = rs.type_id
        WHERE rs.call_sign=$1""", CALL_SIGN)
    
    print(f"Radar {CALL_SIGN} started with range {rng}m")

    while True:
        try:
            # Use async recv with timeout
            if await sock.poll(timeout=100):  # 100ms timeout
                msg_data = await sock.recv()
                msg = json.loads(msg_data.decode())
                lat, lon = msg["lat"], msg["lon"]
                
                # Calculate distance in metres using great-circle distance
                dist = await pool.fetchval("""
                    SELECT ST_Distance(
                        geom, ST_SetSRID(ST_MakePoint($1,$2),4326)::geography
                    ) FROM radar_site WHERE call_sign=$3""", lon, lat, CALL_SIGN)
                
                if dist < rng:
                    DETECTIONS.labels(radar=CALL_SIGN).inc()
                    detection_msg = {
                        "radar_id": CALL_SIGN,
                        "missile_id": msg["id"],
                        "ts": time.time(),
                        "snr": 30,
                        "lat": lat,
                        "lon": lon
                    }
                    await nats.publish("radar.detection", json.dumps(detection_msg).encode())
                    print(f"Radar {CALL_SIGN} detected missile {msg['id']} at distance {dist:.0f}m")
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"Error in radar {CALL_SIGN}: {e}")
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())