import os, json, time, asyncio, asyncpg
from prometheus_client import start_http_server, Counter
from nats.aio.client import Client as NATS
import zmq.asyncio

DB_DSN = os.getenv("DB_DSN")
CALL_SIGN = os.getenv("CALL_SIGN", "BAT_LA")
start_http_server(8000)
FIRES = Counter("battery_fires", "Missiles fired", ["battery"])

ctx = zmq.asyncio.Context()
bsub = ctx.socket(zmq.SUB)
bsub.connect("tcp://command_center:5558")
bsub.setsockopt_string(zmq.SUBSCRIBE, "")

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
    
    print(f"Battery {CALL_SIGN} ready for intercept commands")
    
    while True:
        try:
            # Use async recv with timeout
            if await bsub.poll(timeout=100):  # 100ms timeout
                msg = await bsub.recv_json()
                if msg.get("battery_call_sign") == CALL_SIGN:
                    missile_id = msg["missile_id"]
                    fire_ts = msg["fire_ts"]
                    
                    # Check if we have ammo
                    ammo = await pool.fetchval(
                        "SELECT ammo_count FROM battery WHERE call_sign=$1", 
                        CALL_SIGN
                    )
                    
                    if ammo and ammo > 0:
                        FIRES.labels(battery=CALL_SIGN).inc()
                        print(f"Battery {CALL_SIGN} firing at missile {missile_id}")
                        
                        # Send intercept command to interceptor_sim
                        intercept_cmd = {
                            "missile_id": missile_id,
                            "battery_call_sign": CALL_SIGN,
                            "fire_ts": fire_ts,
                            "blast_radius": 200
                        }
                        await nats.publish("command.intercept", json.dumps(intercept_cmd).encode())
                    else:
                        print(f"Battery {CALL_SIGN} out of ammo!")
            
            await asyncio.sleep(0.1)
                    
        except Exception as e:
            print(f"Error processing battery command: {e}")
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())