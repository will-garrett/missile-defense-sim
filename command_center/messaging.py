"""
Messaging service for the Command Center Service
Handles database operations and API requests
"""
import time
from typing import Dict, List, Any, Optional
import asyncpg

class CommandCenterMessagingService:
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
    
    async def get_active_threats(self) -> List[Dict[str, Any]]:
        """Get all active threats"""
        async with self.db_pool.acquire() as con:
            threats = await con.fetch("""
                SELECT am.id, am.callsign, am.missile_type, am.launch_ts,
                       am.current_geom, am.current_altitude_m,
                       am.velocity_x_mps, am.velocity_y_mps, am.velocity_z_mps,
                       pt.blast_radius_m, pt.nickname as platform_nickname
                FROM active_missile am
                JOIN platform_type pt ON am.platform_type_id = pt.id
                WHERE am.missile_type = 'attack' AND am.status = 'active'
                ORDER BY am.launch_ts DESC
            """)
            return [dict(t) for t in threats]
    
    async def get_battery_status(self) -> List[Dict[str, Any]]:
        """Get status of all batteries"""
        async with self.db_pool.acquire() as con:
            batteries = await con.fetch("""
                SELECT i.callsign, i.status, i.ammo_count, i.current_speed_mps,
                       pt.max_range_m, pt.max_altitude_m, pt.accuracy_percent,
                       pt.reload_time_sec
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'counter_defense' AND i.status = 'active'
                ORDER BY i.callsign
            """)
            return [dict(b) for b in batteries]
    
    async def get_recent_engagements(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent engagement decisions"""
        async with self.db_pool.acquire() as con:
            engagements = await con.fetch("""
                SELECT e.id, e.intercept_geom, e.intercept_altitude_m, e.status,
                       e.intercept_distance_m, e.created_at,
                       i.callsign as battery_callsign
                FROM engagement e
                JOIN installation i ON e.launch_installation_id = i.id
                ORDER BY e.created_at DESC
                LIMIT $1
            """, limit)
            return [dict(e) for e in engagements] 