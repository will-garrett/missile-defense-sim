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
            platforms = await con.fetch("SELECT * FROM platform_type ORDER BY category, nickname")
            return [dict(p) for p in platforms]
    
    async def get_installations(self) -> List[Dict[str, Any]]:
        """Get all installations"""
        async with self.db_pool.acquire() as con:
            installations = await con.fetch("""
                SELECT i.id, i.callsign, i.geom, i.altitude_m, 
                       i.heading_deg, i.status,
                       pt.nickname as platform_nickname, pt.category, pt.is_mobile
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                ORDER BY pt.category, i.callsign
            """)
            return [dict(i) for i in installations]
    
    async def create_installation(self, platform_nickname: str, callsign: str, 
                                lat: float, lon: float, altitude_m: float = 0) -> Dict[str, Any]:
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
                    platform_type_id, callsign, geom, altitude_m
                ) VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326)::geography, $5)
                RETURNING id
            """, platform_id, callsign, lon, lat, altitude_m)
            
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
    
    async def arm_launcher(self, launcher_callsign: str, munition_nickname: str, quantity: int) -> Dict[str, Any]:
        """Arm a launcher with a specific type of munition."""
        async with self.db_pool.acquire() as con:
            # Get launcher and munition IDs
            launcher_id = await con.fetchval("SELECT id FROM installation WHERE callsign = $1", launcher_callsign)
            if not launcher_id:
                raise ValueError(f"Launcher with callsign {launcher_callsign} not found")

            munition_id = await con.fetchval("SELECT id FROM munition_type WHERE nickname = $1", munition_nickname)
            if not munition_id:
                raise ValueError(f"Munition with nickname {munition_nickname} not found")

            # Use INSERT ... ON CONFLICT to either add new ammo or update existing count
            await con.execute("""
                INSERT INTO installation_munition (installation_id, munition_type_id, quantity)
                VALUES ($1, $2, $3)
                ON CONFLICT (installation_id, munition_type_id)
                DO UPDATE SET quantity = installation_munition.quantity + EXCLUDED.quantity;
            """, launcher_id, munition_id, quantity)

            return {
                "launcher_callsign": launcher_callsign,
                "munition_nickname": munition_nickname,
                "status": "armed",
                "added_quantity": quantity
            }
    
    async def launch_missile(self, launcher_callsign: str, munition_nickname: str,
                           target_lat: float, target_lon: float, target_alt: float) -> Dict[str, Any]:
        """Launch a missile from a specific launcher."""
        
        async with self.db_pool.acquire() as con:
            # Transaction to ensure atomicity
            async with con.transaction():
                # 1. Get launcher and munition info
                launcher = await con.fetchrow("""
                    SELECT 
                        i.id, 
                        ST_X(i.geom::geometry) as lon, 
                        ST_Y(i.geom::geometry) as lat,
                        i.altitude_m as alt
                    FROM installation i WHERE callsign = $1
                """, launcher_callsign)
                if not launcher:
                    raise ValueError(f"Launcher {launcher_callsign} not found")

                munition_type = await con.fetchrow("SELECT id, nickname FROM munition_type WHERE nickname = $1", munition_nickname)
                if not munition_type:
                    raise ValueError(f"Munition type {munition_nickname} not found")

                # 2. Check for available ammunition
                ammo_record = await con.fetchrow("""
                    SELECT id, quantity FROM installation_munition
                    WHERE installation_id = $1 AND munition_type_id = $2
                """, launcher['id'], munition_type['id'])

                if not ammo_record or ammo_record['quantity'] < 1:
                    raise ValueError(f"Launcher {launcher_callsign} has no {munition_nickname} ammunition")

                # 3. Decrement ammo count
                await con.execute(
                    "UPDATE installation_munition SET quantity = quantity - 1 WHERE id = $1",
                    ammo_record['id']
                )

                # 4. Generate a new missile callsign
                fired_count = await con.fetchval("""
                    SELECT COUNT(*) FROM active_missile WHERE launch_installation_id = $1
                """, launcher['id'])
                
                munition_abbreviation = "".join([c for c in munition_type['nickname'] if c.isupper() or c.isdigit()])
                new_missile_callsign = f"{launcher_callsign}-{munition_abbreviation}-{fired_count + 1}"

                # 5. Send launch request to simulation service
                launch_message = {
                    "type": "missile_launch",
                    "missile_callsign": new_missile_callsign,
                    "munition_nickname": munition_nickname,
                    "launch_callsign": launcher_callsign,
                    "launch_lat": launcher['lat'],
                    "launch_lon": launcher['lon'],
                    "launch_alt": launcher['alt'],
                    "target_lat": target_lat,
                    "target_lon": target_lon,
                    "target_alt": target_alt,
                    "timestamp": time.time()
                }
                
                if self.nats_client:
                    await self.nats_client.publish("simulation.launch", json.dumps(launch_message).encode())
                
                return {
                    "status": "launched",
                    "missile_callsign": new_missile_callsign,
                    "launcher_callsign": launcher_callsign,
                    "munition_nickname": munition_nickname
                }
    
    async def get_active_missiles(self) -> List[Dict[str, Any]]:
        """Get all active missiles"""
        async with self.db_pool.acquire() as con:
            missiles = await con.fetch("""
                SELECT 
                    am.id as callsign,
                    mt.nickname as munition_type,
                    am.status,
                    am.current_geom,
                    am.current_altitude_m,
                    am.launch_ts
                FROM active_missile am
                JOIN munition_type mt ON am.munition_type_id = mt.id
                WHERE am.status = 'active'
            """)
            return [dict(m) for m in missiles]
    
    async def get_recent_detections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent detection events"""
        # This will need to be updated in a later step, as the detection_event table was removed
        return []
    
    async def get_recent_engagements(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent engagement events"""
        # This will need to be updated in a later step, as the engagement table was removed
        return []
    
    async def get_recent_detonations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent detonation events"""
        # This will need to be updated in a later step, as the detonation_event table was removed
        return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        db_ok = False
        nats_ok = False
        
        # Check DB
        try:
            async with self.db_pool.acquire() as con:
                await con.fetchval("SELECT 1")
            db_ok = True
        except Exception as e:
            print(f"Health check DB error: {e}")
        
        # Check NATS
        if self.nats_client and self.nats_client.is_connected:
            nats_ok = True
            
        return {
            "service": "attack_service",
            "status": "ok" if db_ok and nats_ok else "degraded",
            "dependencies": {
                "database": "ok" if db_ok else "error",
                "nats": "ok" if nats_ok else "error"
            }
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