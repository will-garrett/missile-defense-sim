"""
Main entry point for the Simulation Service
Coordinates API endpoints, messaging services, and simulation engine
"""
import os
import asyncio
from prometheus_client import start_http_server
import uvicorn
import asyncpg
import nats
from nats.aio.client import Client as NATS
import zmq.asyncio
from fastapi.middleware.cors import CORSMiddleware

from api import SimulationServiceAPI
from messaging import SimulationMessagingService
from simulation_engine import SimulationEngine

# Start Prometheus metrics server
start_http_server(8001)

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
    messaging_service = SimulationMessagingService(db_pool)
    
    # Initialize simulation engine
    simulation_engine = SimulationEngine(db_pool, nats_client, zmq_context)
    await simulation_engine.initialize()
    
    # Store reference to simulation engine in messaging service for cleanup
    messaging_service.simulation_engine = simulation_engine
    
    # Initialize API service
    api_service = SimulationServiceAPI(messaging_service)
    app = api_service.get_app()
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add startup and shutdown events
    @app.on_event("startup")
    async def startup():
        print("Simulation Service starting up...")
        # Start simulation loop in background
        asyncio.create_task(simulation_engine.run_simulation_loop())
    
    @app.on_event("shutdown")
    async def shutdown():
        print("Simulation Service shutting down...")
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