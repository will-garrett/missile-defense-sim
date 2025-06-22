"""
API endpoints for the Attack Service
Handles REST API requests for missile launches and installation management
"""
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from prometheus_client import Counter

from messaging import MessagingService

# Prometheus metrics
LAUNCHES = Counter("missile_launches", "Total missiles launched")
PLATFORM_CREATIONS = Counter("platform_creations", "Total platform installations created")
PLATFORM_ARMED = Counter("platform_armed", "Total platforms armed with munitions")

# Pydantic models
class ArmRequest(BaseModel):
    launcher_callsign: str
    munition_nickname: str
    quantity: int

class LaunchRequest(BaseModel):
    launcher_callsign: str
    munition_nickname: str
    target_lat: float
    target_lon: float
    target_alt: float = 0

class InstallationRequest(BaseModel):
    platform_nickname: str
    callsign: str
    lat: float
    lon: float
    altitude_m: float = 0
    is_mobile: bool = False
    ammo_count: int = 0

class AttackServiceAPI:
    def __init__(self, messaging_service: MessagingService):
        self.messaging = messaging_service
        self.app = FastAPI(title="Missile Defense Attack Service", version="2.0.0")
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up all API routes"""
        
        @self.app.get("/")
        async def root():
            return {"message": "Missile Defense Attack Service v2.0", "status": "operational"}
        
        @self.app.get("/platforms")
        async def get_platforms():
            """Get all available platform types"""
            return await self.messaging.get_platforms()
        
        @self.app.get("/installations")
        async def get_installations():
            """Get all installations"""
            return await self.messaging.get_installations()
        
        @self.app.post("/installations")
        async def create_installation(request: InstallationRequest):
            """Create a new installation"""
            try:
                result = await self.messaging.create_installation(
                    platform_nickname=request.platform_nickname,
                    callsign=request.callsign,
                    lat=request.lat,
                    lon=request.lon,
                    altitude_m=request.altitude_m,
                    is_mobile=request.is_mobile,
                    ammo_count=request.ammo_count
                )
                PLATFORM_CREATIONS.inc()
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.delete("/installations/{callsign}")
        async def delete_installation(callsign: str):
            """Delete a specific installation by callsign"""
            try:
                result = await self.messaging.delete_installation(callsign)
                return {"message": f"Installation {callsign} deleted successfully"}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.delete("/installations")
        async def delete_all_installations():
            """Delete all installations"""
            try:
                result = await self.messaging.delete_all_installations()
                return {"message": "All installations deleted successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.post("/arm")
        async def arm_launcher(request: ArmRequest):
            """Arm a launcher with a specific munition"""
            try:
                result = await self.messaging.arm_launcher(
                    launcher_callsign=request.launcher_callsign,
                    munition_nickname=request.munition_nickname,
                    quantity=request.quantity
                )
                PLATFORM_ARMED.inc()
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.post("/launch")
        async def launch_missile(request: LaunchRequest):
            """Launch a missile"""
            try:
                result = await self.messaging.launch_missile(
                    launcher_callsign=request.launcher_callsign,
                    munition_nickname=request.munition_nickname,
                    target_lat=request.target_lat,
                    target_lon=request.target_lon,
                    target_alt=request.target_alt,
                )
                LAUNCHES.inc()
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.get("/missiles/active")
        async def get_active_missiles():
            """Get all active missiles"""
            return await self.messaging.get_active_missiles()
        
        @self.app.get("/detections/recent")
        async def get_recent_detections(limit: int = 50):
            """Get recent detection events"""
            return await self.messaging.get_recent_detections(limit)
        
        @self.app.get("/engagements/recent")
        async def get_recent_engagements(limit: int = 50):
            """Get recent engagement events"""
            return await self.messaging.get_recent_engagements(limit)
        
        @self.app.get("/detonations/recent")
        async def get_recent_detonations(limit: int = 50):
            """Get recent detonation events"""
            return await self.messaging.get_recent_detonations(limit)
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return await self.messaging.health_check()
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application"""
        return self.app 