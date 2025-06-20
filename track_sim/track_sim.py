import zmq.asyncio, time, json, math, os, asyncpg, asyncio
from prometheus_client import start_http_server, Counter

DB_DSN = os.getenv("DB_DSN")
TICK = 0.1
SPEED = 1700          # m/s

start_http_server(8000)
TICKS = Counter("track_updates","Track updates broadcast")

ctx = zmq.asyncio.Context()
sub = ctx.socket(zmq.SUB); sub.bind("tcp://0.0.0.0:5556"); sub.setsockopt_string(zmq.SUBSCRIBE,"")
pub = ctx.socket(zmq.PUB); pub.bind("tcp://0.0.0.0:5557")   # outgoing refined track

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

async def sim():
    pool = await create_db_pool_with_retry(DB_DSN)
    positions = {}               # id -> (lat,lon,alt)
    print("Track simulation started, waiting for missile launches...")
    
    while True:
        try:
            # Use async recv with timeout
            if await sub.poll(timeout=100):  # 100ms timeout
                msg = await sub.recv_json()
                positions[msg["id"]] = (msg["lat"], msg["lon"], msg["alt_m"])
                print(f"Received missile track: {msg['id']}")
            
            # very coarse physics: drop alt, keep lat/lon
            for mid,(lat,lon,alt) in list(positions.items()):
                alt -= SPEED * TICK
                if alt <= 0:
                    positions.pop(mid)
                    print(f"Missile {mid} reached ground")
                    continue
                await pub.send_json({"id":mid,"ts":time.time(),"lat":lat,"lon":lon,"alt_m":alt})
                TICKS.inc()
            
            await asyncio.sleep(TICK)
        except Exception as e:
            print(f"Error in track simulation: {e}")
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    import signal, sys
    loop = asyncio.get_event_loop()
    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, sys.exit, 0)
    loop.run_until_complete(sim())