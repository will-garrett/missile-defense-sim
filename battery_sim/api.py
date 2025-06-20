"""
API endpoints for the Battery Simulation Service
Handles REST API requests for battery status, health, and control
"""
from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import Dict
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

class BatteryStatusResponse(BaseModel):
    callsign: str
    status: str
    ammo_count: int

class BatterySimAPI:
    def __init__(self, logic):
        self.logic = logic
        self.app = FastAPI(title="Missile Defense Battery Simulation Service", version="1.0.0")
        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"message": "Missile Defense Battery Simulation Service v1.0", "status": "operational"}

        @self.app.get("/status", response_model=BatteryStatusResponse)
        async def get_status():
            return BatteryStatusResponse(
                callsign=self.logic.callsign,
                status=self.logic.status,
                ammo_count=self.logic.ammo_count
            )

        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy"}

        @self.app.get("/metrics")
        def metrics():
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    def get_app(self):
        return self.app 