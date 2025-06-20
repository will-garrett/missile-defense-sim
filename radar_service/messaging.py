"""
Messaging service for the Radar Service
Handles database operations and API requests
"""
import time
from typing import Dict, List, Any, Optional
import asyncpg

class RadarMessagingService:
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
    
    async def get_radar_installations(self) -> List[Dict[str, Any]]:
        """Get all radar installations"""
        async with self.db_pool.acquire() as con:
            installations = await con.fetch("""
                SELECT i.callsign, i.status, i.altitude_m,
                       pt.detection_range_m, pt.sweep_rate_deg_per_sec, pt.max_altitude_m,
                       pt.accuracy_percent
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'detection_system' AND i.status = 'active'
                ORDER BY i.callsign
            """)
            return [dict(i) for i in installations]
    
    async def get_active_tracks(self) -> List[Dict[str, Any]]:
        """Get all active tracks"""
        async with self.db_pool.acquire() as con:
            tracks = await con.fetch("""
                SELECT am.id as missile_id, am.callsign as missile_callsign,
                       am.current_geom, am.current_altitude_m,
                       am.velocity_x_mps, am.velocity_y_mps, am.velocity_z_mps,
                       am.launch_ts, am.updated_at
                FROM active_missile am
                WHERE am.missile_type = 'attack' AND am.status = 'active'
                ORDER BY am.launch_ts DESC
            """)
            return [dict(t) for t in tracks]
    
    async def get_recent_detections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent detection events"""
        async with self.db_pool.acquire() as con:
            detections = await con.fetch("""
                SELECT de.id, de.detection_ts, de.detection_geom, de.detection_altitude_m,
                       de.signal_strength_db, de.confidence_percent,
                       i.callsign as radar_callsign,
                       am.callsign as missile_callsign
                FROM detection_event de
                JOIN installation i ON de.detection_installation_id = i.id
                JOIN active_missile am ON de.detected_missile_id = am.id
                ORDER BY de.detection_ts DESC
                LIMIT $1
            """, limit)
            return [dict(d) for d in detections]
    
    async def get_radar_statistics(self) -> Dict[str, Any]:
        """Get radar service statistics"""
        async with self.db_pool.acquire() as con:
            # Count radar installations
            installation_count = await con.fetchval("""
                SELECT COUNT(*)
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'detection_system' AND i.status = 'active'
            """)
            
            # Count active tracks
            track_count = await con.fetchval("""
                SELECT COUNT(*)
                FROM active_missile
                WHERE missile_type = 'attack' AND status = 'active'
            """)
            
            # Count recent detections
            recent_detections = await con.fetchval("""
                SELECT COUNT(*)
                FROM detection_event
                WHERE detection_ts > NOW() - INTERVAL '1 hour'
            """)
            
            return {
                "radar_installations": installation_count,
                "active_tracks": track_count,
                "recent_detections": recent_detections,
                "timestamp": time.time()
            } 