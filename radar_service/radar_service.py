"""
Main entry point for the Radar Service
Coordinates API endpoints, messaging services, and radar logic
"""
import os
import asyncio
from prometheus_client import start_http_server
import uvicorn
import asyncpg
import nats
from nats.aio.client import Client as NATS

from api import RadarServiceAPI
from messaging import RadarMessagingService
from radar_logic import RadarLogic

# Start Prometheus metrics server
start_http_server(8000)

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
    """Main application entry point"""
    # Get configuration from environment
    db_dsn = os.getenv("DB_DSN")
    nats_url = os.getenv("NATS_URL", "nats://nats:4222")
    
    if not db_dsn:
        raise ValueError("DB_DSN environment variable is required")
    
    # Initialize database pool
    db_pool = await create_db_pool_with_retry(db_dsn)
    
    # Initialize NATS client
    nats_client = NATS()
    await nats_client.connect(nats_url)
    print("Connected to NATS")
    
    # Initialize messaging service
    messaging_service = RadarMessagingService(db_pool)
    
    # Initialize radar logic
    radar_logic = RadarLogic(db_pool, nats_client)
    await radar_logic.initialize()
    
    # Initialize API service
    api_service = RadarServiceAPI(messaging_service)
    app = api_service.get_app()
    
    # Add startup and shutdown events
    @app.on_event("startup")
    async def startup():
        print("Radar Service starting up...")
        # Start radar logic loop in background
        asyncio.create_task(radar_logic.run_radar_service())
    
    @app.on_event("shutdown")
    async def shutdown():
        print("Radar Service shutting down...")
        await nats_client.close()
        await db_pool.close()
    
    # Start the FastAPI server
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8006,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main()) 