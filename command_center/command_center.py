"""
Main entry point for the Command Center Service
Coordinates API endpoints, messaging services, and command logic
"""
import os
import asyncio
from prometheus_client import start_http_server
import uvicorn
import asyncpg
import nats
from nats.aio.client import Client as NATS
import zmq.asyncio

from api import CommandCenterAPI
from messaging import CommandCenterMessagingService
from command_logic import CommandLogic

# Start Prometheus metrics server
start_http_server(8002)

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
    
    # Initialize ZMQ context
    zmq_context = zmq.asyncio.Context()
    
    # Initialize messaging service
    messaging_service = CommandCenterMessagingService(db_pool)
    
    # Initialize command logic
    command_logic = CommandLogic(db_pool, nats_client, zmq_context)
    await command_logic.initialize()
    
    # Initialize API service
    api_service = CommandCenterAPI(messaging_service)
    app = api_service.get_app()
    
    # Add startup and shutdown events
    @app.on_event("startup")
    async def startup():
        print("Command Center starting up...")
        # Start command center loop in background
        asyncio.create_task(command_logic.run_command_center())
    
    @app.on_event("shutdown")
    async def shutdown():
        print("Command Center shutting down...")
        await nats_client.close()
        await db_pool.close()
        zmq_context.term()
    
    # Start the FastAPI server
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())