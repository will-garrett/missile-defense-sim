"""
API endpoints for the Command Center Service
Handles REST API requests for command center operations
"""
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from messaging import CommandCenterMessagingService

# Pydantic models
class ThreatAssessmentResponse(BaseModel):
    missile_id: str
    missile_callsign: str
    threat_level: str
    time_to_impact: float
    confidence: float
    detection_sources: List[str]

class BatteryStatusResponse(BaseModel):
    callsign: str
    status: str
    ammo_count: int
    time_to_ready: float
    max_range: float
    max_altitude: float

class CommandCenterAPI:
    def __init__(self, messaging_service: CommandCenterMessagingService):
        self.messaging = messaging_service
        self.app = FastAPI(title="Missile Defense Command Center", version="1.0.0")
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up all API routes"""
        
        @self.app.get("/")
        async def root():
            return {"message": "Missile Defense Command Center v1.0", "status": "operational"}
        
        @self.app.get("/threats/active")
        async def get_active_threats():
            """Get all active threats"""
            return await self.messaging.get_active_threats()
        
        @self.app.get("/batteries/status")
        async def get_battery_status():
            """Get status of all batteries"""
            return await self.messaging.get_battery_status()
        
        @self.app.get("/engagements/recent")
        async def get_recent_engagements(limit: int = 50):
            """Get recent engagement decisions"""
            return await self.messaging.get_recent_engagements(limit)
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return await self.messaging.health_check()
        
        @self.app.get("/metrics")
        def metrics():
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application"""
        return self.app 