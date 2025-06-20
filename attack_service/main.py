"""
Main entry point for the Attack Service
Coordinates API endpoints and messaging services
"""
import os
import asyncio
from prometheus_client import start_http_server
import uvicorn

from api import AttackServiceAPI
from messaging import MessagingService

# Start Prometheus metrics server
start_http_server(8000)

async def main():
    """Main application entry point"""
    # Get configuration from environment
    db_dsn = os.getenv("DB_DSN")
    nats_url = os.getenv("NATS_URL", "nats://nats:4222")
    
    if not db_dsn:
        raise ValueError("DB_DSN environment variable is required")
    
    # Initialize messaging service
    messaging_service = MessagingService(db_dsn, nats_url)
    await messaging_service.initialize()
    
    # Initialize API service
    api_service = AttackServiceAPI(messaging_service)
    app = api_service.get_app()
    
    # Add startup and shutdown events
    @app.on_event("startup")
    async def startup():
        print("Attack Service starting up...")
    
    @app.on_event("shutdown")
    async def shutdown():
        print("Attack Service shutting down...")
        await messaging_service.shutdown()
    
    # Start the FastAPI server
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=9000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())