import json, time, random, asyncio
from nats.aio.client import Client as NATS
from prometheus_client import start_http_server, Counter

SUCCESS = Counter("intercepts_success", "Successful intercepts")

start_http_server(8000)

async def main():
    nc = NATS()
    await nc.connect("nats://nats:4222")

    async def cb(msg):
        cmd = json.loads(msg.data)
        await asyncio.sleep(random.uniform(0.5, 2.0))  # flight time
        SUCCESS.inc()
        # Notify missiles of detonation
        detonation = {
            "missile_id": cmd["missile_id"],
            "blast_ts": time.time(),
            "blast_radius": cmd.get("blast_radius", 200)  # default radius if not provided
        }
        await nc.publish("interceptor.detonation", json.dumps(detonation).encode())
        print(f"Intercepted {cmd['missile_id']}")

    await nc.subscribe("command.intercept", cb=cb)
    while True:
        await asyncio.sleep(1)

asyncio.run(main())