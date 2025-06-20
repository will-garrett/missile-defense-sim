"""
Messaging service for the Simulation Service
Handles database operations and API requests
"""
import time
from typing import Dict, List, Any, Optional
import asyncpg

class SimulationMessagingService:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check"""
        try:
            async with self.db_pool.acquire() as con:
                await con.fetchval("SELECT 1")
            
            return {
                "status": "healthy",
                "database": "connected",
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def get_installations(self) -> List[Dict[str, Any]]:
        """Get all installations"""
        async with self.db_pool.acquire() as con:
            installations = await con.fetch("""
                SELECT i.id, i.callsign, i.geom, i.altitude_m, i.is_mobile, 
                       i.current_speed_mps, i.heading_deg, i.status, i.ammo_count,
                       pt.nickname as platform_type_nickname
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                ORDER BY pt.category, i.callsign
            """)
            return [dict(i) for i in installations]
    
    async def create_installation(self, platform_type_nickname: str, callsign: str,
                                lat: float, lon: float, altitude_m: float = 0,
                                is_mobile: bool = False, ammo_count: int = 0) -> Dict[str, Any]:
        """Create a new installation"""
        async with self.db_pool.acquire() as con:
            # Get platform type ID
            platform_id = await con.fetchval(
                "SELECT id FROM platform_type WHERE nickname = $1",
                platform_type_nickname
            )
            
            if not platform_id:
                raise ValueError(f"Platform type {platform_type_nickname} not found")
            
            # Check if callsign already exists
            existing = await con.fetchval(
                "SELECT id FROM installation WHERE callsign = $1",
                callsign
            )
            
            if existing:
                raise ValueError(f"Installation with callsign {callsign} already exists")
            
            # Create installation
            installation_id = await con.fetchval("""
                INSERT INTO installation (
                    platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count
                ) VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326)::geography, $5, $6, $7)
                RETURNING id
            """, platform_id, callsign, lon, lat, altitude_m, is_mobile, ammo_count)
            
            return {
                "id": installation_id,
                "platform_type_nickname": platform_type_nickname,
                "callsign": callsign,
                "lat": lat,
                "lon": lon,
                "altitude_m": altitude_m,
                "is_mobile": is_mobile,
                "ammo_count": ammo_count
            }
    
    async def delete_installation(self, callsign: str) -> Dict[str, Any]:
        """Delete an installation by callsign"""
        async with self.db_pool.acquire() as con:
            # Check if installation exists
            installation = await con.fetchrow(
                "SELECT id, callsign FROM installation WHERE callsign = $1",
                callsign
            )
            
            if not installation:
                raise ValueError(f"Installation with callsign {callsign} not found")
            
            # Delete installation
            await con.execute(
                "DELETE FROM installation WHERE callsign = $1",
                callsign
            )
            
            return {
                "callsign": callsign,
                "status": "deleted"
            }
    
    async def setup_scenario(self, scenario_name: str, installations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Set up a complete scenario with installations"""
        async with self.db_pool.acquire() as con:
            # Start transaction
            async with con.transaction():
                created_installations = []
                
                for installation_data in installations:
                    try:
                        # Get platform type ID
                        platform_id = await con.fetchval(
                            "SELECT id FROM platform_type WHERE nickname = $1",
                            installation_data["platform_type_nickname"]
                        )
                        
                        if not platform_id:
                            raise ValueError(f"Platform type {installation_data['platform_type_nickname']} not found")
                        
                        # Check if callsign already exists
                        existing = await con.fetchval(
                            "SELECT id FROM installation WHERE callsign = $1",
                            installation_data["callsign"]
                        )
                        
                        if existing:
                            # Skip if already exists
                            continue
                        
                        # Create installation
                        installation_id = await con.fetchval("""
                            INSERT INTO installation (
                                platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count
                            ) VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326)::geography, $5, $6, $7)
                            RETURNING id
                        """, platform_id, installation_data["callsign"], 
                             installation_data["lon"], installation_data["lat"],
                             installation_data["altitude_m"], installation_data["is_mobile"],
                             installation_data["ammo_count"])
                        
                        created_installations.append({
                            "id": installation_id,
                            "callsign": installation_data["callsign"],
                            "platform_type": installation_data["platform_type_nickname"]
                        })
                        
                    except Exception as e:
                        raise ValueError(f"Failed to create installation {installation_data['callsign']}: {str(e)}")
                
                return {
                    "scenario_name": scenario_name,
                    "installations_created": len(created_installations),
                    "installations": created_installations
                }
    
    async def get_platform_types(self) -> List[Dict[str, Any]]:
        """Get all available platform types"""
        async with self.db_pool.acquire() as con:
            platform_types = await con.fetch("""
                SELECT id, nickname, category, description, max_speed_mps, 
                       max_range_m, max_altitude_m, blast_radius_m, detection_range_m,
                       sweep_rate_deg_per_sec, reload_time_sec, accuracy_percent
                FROM platform_type
                ORDER BY category, nickname
            """)
            return [dict(p) for p in platform_types]
    
    async def cleanup_simulation(self) -> Dict[str, Any]:
        """Clean up all simulation data - missiles, installations, etc."""
        try:
            async with self.db_pool.acquire() as con:
                # Start transaction
                async with con.transaction():
                    # Clear active missiles
                    active_missiles_deleted = await con.execute("DELETE FROM active_missile")
                    
                    # Clear missile outcomes
                    outcomes_deleted = await con.execute("DELETE FROM missile_outcome")
                    
                    # Clear engagements
                    engagements_deleted = await con.execute("DELETE FROM engagement")
                    
                    # Clear all installations
                    installations_deleted = await con.execute("DELETE FROM installation")
                    
                    # Clean up simulation engine state
                    engine_cleanup = await self.cleanup_simulation_engine()
                    
                    return {
                        "status": "cleaned",
                        "active_missiles_deleted": active_missiles_deleted,
                        "outcomes_deleted": outcomes_deleted,
                        "engagements_deleted": engagements_deleted,
                        "installations_deleted": installations_deleted,
                        "engine_cleanup": engine_cleanup,
                        "timestamp": time.time()
                    }
        except Exception as e:
            print(f"Error in cleanup_simulation: {e}")
            return {
                "status": "cleanup_failed",
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def abort_simulation(self) -> Dict[str, Any]:
        """Abort the current simulation and clean up"""
        return await self.cleanup_simulation()
    
    async def cleanup_simulation_engine(self, simulation_engine=None):
        """Clean up the simulation engine state"""
        try:
            if simulation_engine:
                await simulation_engine.cleanup_simulation()
            elif hasattr(self, 'simulation_engine') and self.simulation_engine:
                await self.simulation_engine.cleanup_simulation()
            else:
                print("No simulation engine reference available for cleanup")
            return {"status": "engine_cleaned"}
        except Exception as e:
            print(f"Error cleaning simulation engine: {e}")
            return {"status": "engine_cleanup_failed", "error": str(e)} 