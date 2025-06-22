"""
API endpoints for the Battery Simulation Service.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter

from messaging import BatteryMessagingService

# Prometheus metrics
LAUNCHES = Counter("defense_missile_launches", "Total defense missiles launched")
PLATFORM_CREATIONS = Counter("defense_platform_creations", "Total defense platform installations created")
PLATFORM_ARMED = Counter("defense_platform_armed", "Total defense platforms armed with munitions")

# Pydantic models for API requests
class InstallationRequest(BaseModel):
    platform_nickname: str
    callsign: str
    lat: float
    lon: float
    altitude_m: float = 0

class ArmRequest(BaseModel):
    battery_callsign: str
    munition_nickname: str
    quantity: int

class LaunchRequest(BaseModel):
    battery_callsign: str
    munition_nickname: str
    target_missile_id: str

class BatterySimAPI:
    def __init__(self, messaging_service: BatteryMessagingService):
        self.messaging = messaging_service
        self.app = FastAPI(title="Missile Defense Battery Simulation Service", version="2.0.0")
        self._setup_routes()

    def _setup_routes(self):
        """Sets up all API routes for the service."""

        @self.app.post("/installations")
        async def create_installation(request: InstallationRequest):
            """Create a new battery installation."""
            try:
                result = await self.messaging.create_installation(
                    platform_nickname=request.platform_nickname,
                    callsign=request.callsign,
                    lat=request.lat,
                    lon=request.lon,
                    altitude_m=request.altitude_m,
                )
                PLATFORM_CREATIONS.inc()
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

        @self.app.post("/arm")
        async def arm_battery(request: ArmRequest):
            """Arm a battery with a specific munition."""
            try:
                result = await self.messaging.arm_battery(
                    battery_callsign=request.battery_callsign,
                    munition_nickname=request.munition_nickname,
                    quantity=request.quantity,
                )
                PLATFORM_ARMED.inc()
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

        @self.app.post("/launch")
        async def launch_defense_missile(request: LaunchRequest):
            """Launch a defense missile to intercept a target."""
            try:
                result = await self.messaging.launch_defense_missile(
                    battery_callsign=request.battery_callsign,
                    munition_nickname=request.munition_nickname,
                    target_missile_id=request.target_missile_id,
                )
                LAUNCHES.inc()
                return result
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

    def get_app(self) -> FastAPI:
        """Returns the FastAPI application instance."""
        return self.app 