"""
API endpoints for the Radar Service
Handles REST API requests for radar operations
"""
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from messaging import RadarMessagingService

# Pydantic models
class RadarInstallationResponse(BaseModel):
    callsign: str
    status: str
    detection_range_m: float
    sweep_rate_deg_per_sec: float
    max_altitude_m: float
    active_tracks: int

class TrackResponse(BaseModel):
    missile_id: str
    missile_callsign: str
    position: Dict[str, float]
    velocity: Dict[str, float]
    first_detection: float
    last_detection: float
    detection_count: int
    confidence: float
    detecting_radars: List[str]

class RadarServiceAPI:
    def __init__(self, messaging_service: RadarMessagingService):
        self.messaging = messaging_service
        self.app = FastAPI(title="Missile Defense Radar Service", version="1.0.0")
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up all API routes"""
        
        @self.app.get("/")
        async def root():
            return {"message": "Missile Defense Radar Service v1.0", "status": "operational"}
        
        @self.app.get("/installations")
        async def get_radar_installations():
            """Get all radar installations"""
            return await self.messaging.get_radar_installations()
        
        @self.app.get("/tracks/active")
        async def get_active_tracks():
            """Get all active tracks"""
            return await self.messaging.get_active_tracks()
        
        @self.app.get("/detections/recent")
        async def get_recent_detections(limit: int = 50):
            """Get recent detection events"""
            return await self.messaging.get_recent_detections(limit)
        
        @self.app.get("/statistics")
        async def get_radar_statistics():
            """Get radar service statistics"""
            return await self.messaging.get_radar_statistics()
        
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