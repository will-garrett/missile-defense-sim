"""
API endpoints for the Simulation Service
Handles REST API requests for simulation management
"""
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from messaging import SimulationMessagingService

# Pydantic models
class InstallationCreate(BaseModel):
    platform_type_nickname: str
    callsign: str
    lat: float
    lon: float
    altitude_m: float = 0
    is_mobile: bool = False
    ammo_count: int = 0

class InstallationResponse(BaseModel):
    id: int
    platform_type_nickname: str
    callsign: str
    lat: float
    lon: float
    altitude_m: float
    is_mobile: bool
    ammo_count: int

class ScenarioSetup(BaseModel):
    scenario_name: str
    installations: List[InstallationCreate]

class SimulationServiceAPI:
    def __init__(self, messaging_service: SimulationMessagingService):
        self.messaging = messaging_service
        self.app = FastAPI(title="Missile Defense Simulation Service", version="1.0.0")
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up all API routes"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return await self.messaging.health_check()
        
        @self.app.get("/installations")
        async def get_installations():
            """Get all installations"""
            return await self.messaging.get_installations()
        
        @self.app.post("/installations", response_model=InstallationResponse)
        async def create_installation(installation: InstallationCreate):
            """Create a new installation"""
            try:
                result = await self.messaging.create_installation(
                    platform_type_nickname=installation.platform_type_nickname,
                    callsign=installation.callsign,
                    lat=installation.lat,
                    lon=installation.lon,
                    altitude_m=installation.altitude_m,
                    is_mobile=installation.is_mobile,
                    ammo_count=installation.ammo_count
                )
                return InstallationResponse(**result)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.delete("/installations/{callsign}")
        async def delete_installation(callsign: str):
            """Delete an installation by callsign"""
            try:
                result = await self.messaging.delete_installation(callsign)
                return result
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.post("/scenarios/setup")
        async def setup_scenario(scenario: ScenarioSetup):
            """Set up a complete scenario with installations"""
            try:
                # Convert Pydantic models to dictionaries
                installations_dict = [installation.model_dump() for installation in scenario.installations]
                result = await self.messaging.setup_scenario(
                    scenario_name=scenario.scenario_name,
                    installations=installations_dict
                )
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.get("/platform-types")
        async def get_platform_types():
            """Get all available platform types"""
            return await self.messaging.get_platform_types()
        
        @self.app.post("/cleanup")
        async def cleanup_simulation():
            """Clean up all simulation data"""
            try:
                result = await self.messaging.cleanup_simulation()
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
        
        @self.app.post("/abort")
        async def abort_simulation():
            """Abort the current simulation and clean up"""
            try:
                result = await self.messaging.abort_simulation()
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Abort failed: {str(e)}")
        
        @self.app.get("/metrics")
        def metrics():
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application"""
        return self.app 