"""
Main entry point for the Battery Simulation Service.
This service is responsible for managing defensive battery installations and launching interceptors.
"""
import os
import asyncio
from prometheus_client import start_http_server
import uvicorn

from api import BatterySimAPI
from messaging import BatteryMessagingService

# Start Prometheus metrics server for operational monitoring
start_http_server(8000)

async def main():
    """Initializes and runs the Battery Simulation Service."""
    db_dsn = os.getenv("DB_DSN")
    nats_url = os.getenv("NATS_URL", "nats://nats:4222")

    if not db_dsn:
        raise ValueError("DB_DSN environment variable is required")

    # Initialize the messaging service which handles all NATS and DB interactions
    messaging_service = BatteryMessagingService(db_dsn=db_dsn, nats_url=nats_url)
    await messaging_service.initialize()

    # Initialize the API service, passing the messaging service for dependency injection
    api_service = BatterySimAPI(messaging_service=messaging_service)
    app = api_service.get_app()

    @app.on_event("startup")
    async def startup():
        """Handles application startup logic."""
        print("Battery Simulation Service starting up...")
        # Start any background tasks if necessary, like listening to NATS subjects
        asyncio.create_task(messaging_service.listen_for_engagement_orders())

    @app.on_event("shutdown")
    async def shutdown():
        """Handles application shutdown logic."""
        print("Battery Simulation Service shutting down...")
        await messaging_service.shutdown()

    # Configure and run the FastAPI server
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=9001,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())