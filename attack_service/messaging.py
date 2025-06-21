"""
Messaging service for the Attack Service
Handles database operations and NATS communication
"""
import time
import asyncio
from typing import Optional, Dict, List, Any
import asyncpg
import nats
from nats.aio.client import Client as NATS
import json
import math

class MissileState:
    def __init__(self, missile_id, position, velocity, target, fuel_remaining, status="active"):
        self.missile_id = missile_id
        self.position = position  # [x, y, z]
        self.velocity = velocity  # [vx, vy, vz]
        self.target = target      # [x, y, z]
        self.fuel_remaining = fuel_remaining
        self.status = status

class MessagingService:
    def __init__(self, db_dsn: str, nats_url: str = "nats://nats:4222"):
        self.db_dsn = db_dsn
        self.nats_url = nats_url
        self.db_pool: Optional[asyncpg.Pool] = None
        self.nats_client: Optional[NATS] = None
        self.active_missiles: Dict[str, MissileState] = {}
        self.simulation_task = None
    
    async def initialize(self):
        """Initialize database connection and NATS client"""
        # Initialize database pool
        self.db_pool = await self._create_db_pool_with_retry()
        
        # Initialize NATS client
        self.nats_client = NATS()
        await self.nats_client.connect(self.nats_url)
        print("Attack Service messaging initialized")
        self.simulation_task = asyncio.create_task(self.simulate_missiles_loop())
    
    async def shutdown(self):
        """Shutdown connections"""
        if self.nats_client:
            await self.nats_client.close()
        if self.db_pool:
            await self.db_pool.close()
        if self.simulation_task:
            self.simulation_task.cancel()
    
    async def _create_db_pool_with_retry(self, max_retries=30, delay=2):
        """Create database pool with retry logic for startup timing"""
        for attempt in range(max_retries):
            try:
                pool = await asyncpg.create_pool(dsn=self.db_dsn)
                print(f"Database connection established on attempt {attempt + 1}")
                return pool
            except Exception as e:
                print(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise
        raise Exception("Failed to connect to database after all retries")
    
    async def get_platforms(self) -> List[Dict[str, Any]]:
        """Get all available platform types"""
        async with self.db_pool.acquire() as con:
            platforms = await con.fetch("""
                SELECT id, nickname, category, description, max_speed_mps, 
                       max_range_m, max_altitude_m, blast_radius_m, detection_range_m,
                       sweep_rate_deg_per_sec, reload_time_sec, accuracy_percent
                FROM platform_type
                ORDER BY category, nickname
            """)
            return [dict(p) for p in platforms]
    
    async def get_installations(self) -> List[Dict[str, Any]]:
        """Get all installations"""
        async with self.db_pool.acquire() as con:
            installations = await con.fetch("""
                SELECT i.id, i.callsign, i.geom, i.altitude_m, i.is_mobile, 
                       i.current_speed_mps, i.heading_deg, i.status, i.ammo_count,
                       pt.nickname as platform_nickname, pt.category
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                ORDER BY pt.category, i.callsign
            """)
            return [dict(i) for i in installations]
    
    async def create_installation(self, platform_nickname: str, callsign: str, 
                                lat: float, lon: float, altitude_m: float = 0,
                                is_mobile: bool = False, ammo_count: int = 0) -> Dict[str, Any]:
        """Create a new installation"""
        async with self.db_pool.acquire() as con:
            # Get platform type ID
            platform_id = await con.fetchval(
                "SELECT id FROM platform_type WHERE nickname = $1",
                platform_nickname
            )
            
            if not platform_id:
                raise ValueError(f"Platform {platform_nickname} not found")
            
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
                "installation_id": installation_id,
                "callsign": callsign,
                "status": "created"
            }
    
    async def delete_installation(self, callsign: str) -> Dict[str, Any]:
        """Delete a specific installation by callsign"""
        async with self.db_pool.acquire() as con:
            # Check if installation exists
            installation_id = await con.fetchval(
                "SELECT id FROM installation WHERE callsign = $1",
                callsign
            )
            
            if not installation_id:
                raise ValueError(f"Installation {callsign} not found")
            
            # Delete installation
            await con.execute(
                "DELETE FROM installation WHERE callsign = $1",
                callsign
            )
            
            return {
                "callsign": callsign,
                "status": "deleted"
            }
    
    async def delete_all_installations(self) -> Dict[str, Any]:
        """Delete all installations"""
        async with self.db_pool.acquire() as con:
            # Get count before deletion
            count = await con.fetchval("SELECT COUNT(*) FROM installation")
            
            # Delete all installations
            await con.execute("DELETE FROM installation")
            
            return {
                "deleted_count": count,
                "status": "all_deleted"
            }
    
    async def launch_missile(self, platform_nickname: str, launch_callsign: str,
                           launch_lat: float, launch_lon: float, launch_alt: float,
                           target_lat: float, target_lon: float, target_alt: float,
                           missile_type: str = "attack") -> Dict[str, Any]:
        """Launch a missile with realistic airburst target calculation"""
        
        # Validate platform exists
        async with self.db_pool.acquire() as con:
            platform = await con.fetchrow(
                "SELECT id, category, blast_radius_m FROM platform_type WHERE nickname = $1",
                platform_nickname
            )
            
            if not platform:
                raise ValueError(f"Platform {platform_nickname} not found")
            
            # Validate installation exists
            installation = await con.fetchrow(
                "SELECT id FROM installation WHERE callsign = $1",
                launch_callsign
            )
            
            if not installation:
                raise ValueError(f"Installation {launch_callsign} not found")
            
            # Check if installation has ammo (for counter-defense systems)
            if platform['category'] == 'counter_defense':
                ammo = await con.fetchval(
                    "SELECT ammo_count FROM installation WHERE callsign = $1",
                    launch_callsign
                )
                
                if ammo <= 0:
                    raise ValueError("Installation has no ammunition")
                
                # Decrement ammo
                await con.execute(
                    "UPDATE installation SET ammo_count = ammo_count - 1 WHERE callsign = $1",
                    launch_callsign
                )
        
        # Calculate airburst target position for realistic detonation
        blast_radius = platform.get('blast_radius_m')
        if blast_radius is None or blast_radius <= 0:
            print(f"WARNING: Platform {platform_nickname} has no blast radius set in database, using default 200m")
            blast_radius = 200.0
        else:
            blast_radius = float(blast_radius)
        
        # For airburst detonation, calculate optimal detonation altitude
        # This should be above the target but within blast radius for maximum effectiveness
        airburst_altitude = max(target_alt + 100, blast_radius * 0.5)  # At least 100m above target or half blast radius
        
        # Calculate target position for airburst (same lat/lon, but higher altitude)
        airburst_target_lat = target_lat
        airburst_target_lon = target_lon
        airburst_target_alt = airburst_altitude
        
        # Send launch request to simulation service via NATS
        launch_message = {
            "type": "missile_launch",
            "platform_nickname": platform_nickname,
            "launch_callsign": launch_callsign,
            "launch_lat": launch_lat,
            "launch_lon": launch_lon,
            "launch_alt": launch_alt,
            "target_lat": airburst_target_lat,
            "target_lon": airburst_target_lon,
            "target_alt": airburst_target_alt,
            "missile_type": missile_type,
            "blast_radius": blast_radius,
            "timestamp": time.time()
        }
        
        await self.nats_client.publish("simulation.launch", json.dumps(launch_message).encode())
        
        # Add to local simulation state
        missile_id = f"{launch_callsign}_{int(time.time()*1000)}"
        position = [launch_lon, launch_lat, launch_alt]
        target = [airburst_target_lon, airburst_target_lat, airburst_target_alt]
        # Simple initial velocity toward target
        dx = airburst_target_lon - launch_lon
        dy = airburst_target_lat - launch_lat
        dz = airburst_target_alt - launch_alt
        mag = math.sqrt(dx*dx + dy*dy + dz*dz)
        if mag > 0:
            velocity = [dx/mag*500, dy/mag*500, dz/mag*500]  # 500 m/s initial
        else:
            velocity = [0, 0, 500]
        self.active_missiles[missile_id] = MissileState(missile_id, position, velocity, target, fuel_remaining=1000.0)
        return {
            "status": "launch_requested",
            "platform": platform_nickname,
            "launch_installation": launch_callsign,
            "target": {"lat": airburst_target_lat, "lon": airburst_target_lon, "alt": airburst_target_alt},
            "blast_radius": blast_radius,
            "timestamp": time.time()
        }
    
    async def get_active_missiles(self) -> List[Dict[str, Any]]:
        """Get all active missiles"""
        async with self.db_pool.acquire() as con:
            missiles = await con.fetch("""
                SELECT am.id, am.callsign, am.missile_type, am.launch_ts,
                       am.current_geom, am.current_altitude_m,
                       am.velocity_x_mps, am.velocity_y_mps, am.velocity_z_mps,
                       am.fuel_remaining_kg, am.status,
                       pt.nickname as platform_nickname
                FROM active_missile am
                JOIN platform_type pt ON am.platform_type_id = pt.id
                WHERE am.status = 'active'
                ORDER BY am.launch_ts DESC
            """)
            return [dict(m) for m in missiles]
    
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
    
    async def get_recent_engagements(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent engagement events"""
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
    
    async def get_recent_detonations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent detonation events"""
        async with self.db_pool.acquire() as con:
            detonations = await con.fetch("""
                SELECT de.id, de.detonation_geom, de.detonation_altitude_m,
                       de.blast_radius_m, de.created_at,
                       am.callsign as missile_callsign
                FROM detonation_event de
                JOIN active_missile am ON de.missile_id = am.id
                ORDER BY de.created_at DESC
                LIMIT $1
            """, limit)
            return [dict(d) for d in detonations]
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check"""
        try:
            # Check database
            async with self.db_pool.acquire() as con:
                await con.fetchval("SELECT 1")
            
            # Check NATS
            if self.nats_client and self.nats_client.is_connected:
                nats_status = "connected"
            else:
                nats_status = "disconnected"
            
            return {
                "status": "healthy",
                "database": "connected",
                "nats": nats_status,
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }

    async def simulate_missiles_loop(self):
        while True:
            await asyncio.sleep(0.1)  # 10 Hz
            for missile_id, missile in list(self.active_missiles.items()):
                if missile.status != "active":
                    continue
                # Simple physics: move toward target
                for i in range(3):
                    missile.position[i] += missile.velocity[i] * 0.1
                # Publish position
                msg = {
                    "id": missile_id,
                    "callsign": f"ATT_{missile_id[:8]}",
                    "position": {"x": missile.position[0], "y": missile.position[1], "z": missile.position[2]},
                    "velocity": {"x": missile.velocity[0], "y": missile.velocity[1], "z": missile.velocity[2]},
                    "timestamp": time.time(),
                    "missile_type": "attack"
                }
                await self.nats_client.publish("missile.position", json.dumps(msg).encode())
                # End condition: reached target or below ground
                dist = math.sqrt(sum((missile.position[i] - missile.target[i])**2 for i in range(3)))
                if dist < 100 or missile.position[2] <= 0:
                    missile.status = "detonated" 