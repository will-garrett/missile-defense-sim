import os, json, time, asyncio, asyncpg
from prometheus_client import start_http_server, Counter, Histogram
from nats.aio.client import Client as NATS
import zmq.asyncio

DB_DSN = os.getenv("DB_DSN")
WINDOW=2.0
start_http_server(8000)
ORDERS = Counter("intercepts_ordered","Intercept commands")
LAG = Histogram("correlation_latency_seconds","2-radar correlation latency")

ctx = zmq.asyncio.Context()
bpub = ctx.socket(zmq.PUB)
bpub.bind("tcp://0.0.0.0:5558")   # to battery_sim

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
    
    print("Command center started, monitoring radar detections...")
    
    detections = {}
    
    async def cb(msg):
        try:
            d = json.loads(msg.data)
            m = d["missile_id"]
            t = d["ts"]
            
            detections.setdefault(m, []).append(t)
            detections[m] = [x for x in detections[m] if t - x < WINDOW]
            
            if len(detections[m]) >= 2:
                print(f"Correlating detections for missile {m}")
                
                # pick nearest battery with ammo
                row = await pool.fetchrow("""
                  WITH p AS (SELECT ST_SetSRID(ST_MakePoint($1,$2),4326)::geography g)
                  SELECT b.call_sign, b.ammo_count,
                         ST_Distance(b.geom,p.g) dist, bt.max_range_m
                  FROM battery b JOIN battery_type bt ON bt.id=b.type_id, p
                  WHERE b.ammo_count>0 AND ST_DWithin(b.geom,p.g,bt.max_range_m)
                  ORDER BY dist LIMIT 1""", d["lon"], d["lat"])
                
                if row:
                    await pool.execute("UPDATE battery SET ammo_count=ammo_count-1 WHERE call_sign=$1", row["call_sign"])
                    ORDERS.inc()
                    LAG.observe(time.time() - detections[m][0])
                    
                    intercept_cmd = {
                        "battery_call_sign": row["call_sign"],
                        "missile_id": m,
                        "fire_ts": time.time()
                    }
                    
                    await bpub.send_json(intercept_cmd)
                    print(f"Ordered intercept of missile {m} by battery {row['call_sign']}")
                else:
                    print(f"No available battery for missile {m}")
                
                detections[m] = []
                
        except Exception as e:
            print(f"Error processing radar detection: {e}")
    
    await nats.subscribe("radar.detection", cb=cb)
    
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())