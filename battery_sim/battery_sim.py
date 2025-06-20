"""
Main entry point for the Battery Simulation Service
Coordinates API endpoints, messaging, and battery logic
"""
import os
import asyncio
from prometheus_client import start_http_server, Gauge, Counter
import uvicorn
import asyncpg
import nats
from nats.aio.client import Client as NATS
import json
import math
import time
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass

from api import BatterySimAPI
from messaging import BatteryMessagingService
from battery_logic import BatteryLogic

# Prometheus metrics
start_http_server(8000)

# New position and event metrics
BATTERY_POSITION = Gauge("battery_position", "Current position of each battery installation",
                        ["battery_callsign", "status"])
BATTERY_ENGAGEMENT_EVENT = Counter("battery_engagement_event", "Battery engagement event positions",
                                  ["battery_callsign", "target_missile_id", "timestamp"])

@dataclass
class BatteryCapability:
    max_range_m: float
    max_altitude_m: float
    accuracy_percent: float
    reload_time_sec: float
    max_speed_mps: float
    blast_radius_m: float

@dataclass
class EngagementOrder:
    target_missile_id: str
    intercept_point: Dict[str, float]
    intercept_altitude: float
    probability_of_success: float
    timestamp: float

class BatterySim:
    def __init__(self):
        self.db_pool = None
        self.nats_client = None
        self.callsign = os.getenv("CALL_SIGN", "DEF_AEG_01")
        self.battery_capability: Optional[BatteryCapability] = None
        self.status = "ready"  # ready, preparing, launching, reloading
        self.ammo_count = 0
        self.last_launch_time = 0
        self.pending_engagements: List[EngagementOrder] = []
        self.current_engagement: Optional[EngagementOrder] = None
        
    async def initialize(self):
        """Initialize database connection and NATS"""
        # Database
        self.db_pool = await asyncpg.create_pool(os.getenv("DB_DSN"))
        
        # NATS
        self.nats_client = NATS()
        await self.nats_client.connect("nats://nats://nats:4222")
        
        # Load battery capabilities
        await self.load_battery_capabilities()
        
        # Subscribe to engagement orders
        await self.nats_client.subscribe(
            f"battery.{self.callsign}.engage",
            cb=self.handle_engagement_order
        )
        
        print(f"Battery {self.callsign} initialized")
    
    async def load_battery_capabilities(self):
        """Load battery capabilities from database"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT pt.max_range_m, pt.max_altitude_m, pt.accuracy_percent,
                       pt.reload_time_sec, pt.max_speed_mps, pt.blast_radius_m,
                       i.ammo_count, i.status
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE i.callsign = $1
            """, self.callsign)
            
            if row:
                self.battery_capability = BatteryCapability(
                    max_range_m=row['max_range_m'],
                    max_altitude_m=row['max_altitude_m'],
                    accuracy_percent=row['accuracy_percent'],
                    reload_time_sec=row['reload_time_sec'],
                    max_speed_mps=row['max_speed_mps'],
                    blast_radius_m=row['blast_radius_m']
                )
                self.ammo_count = row['ammo_count']
                self.status = row['status']
                
                # Update Prometheus metrics for battery position
                battery_pos = await self.get_battery_position()
                if battery_pos:
                    position_value = battery_pos['lat'] * 1000000 + (battery_pos['lon'] + 180) * 1000
                    BATTERY_POSITION.labels(
                        battery_callsign=self.callsign,
                        status=self.status
                    ).set(position_value)
                
                print(f"Loaded battery capabilities: range={self.battery_capability.max_range_m}m, "
                      f"altitude={self.battery_capability.max_altitude_m}m, "
                      f"ammo={self.ammo_count}")
            else:
                print(f"Warning: No battery capabilities found for {self.callsign}")
                # Use default capabilities
                self.battery_capability = BatteryCapability(
                    max_range_m=200000,  # 200km
                    max_altitude_m=150000,  # 150km
                    accuracy_percent=85,
                    reload_time_sec=30,
                    max_speed_mps=3500,
                    blast_radius_m=50  # Defense missiles have blast radius for intercept detonation
                )
    
    async def handle_engagement_order(self, msg):
        """Handle engagement order from command center"""
        try:
            data = msg.data.decode()
            
            if data['type'] != 'engagement_order':
                return
            
            order = EngagementOrder(
                target_missile_id=data['target_missile_id'],
                intercept_point=data['intercept_point'],
                intercept_altitude=data['intercept_altitude'],
                probability_of_success=data['probability_of_success'],
                timestamp=data['timestamp']
            )
            
            # Add to pending engagements
            self.pending_engagements.append(order)
            
            print(f"Received engagement order for missile {order.target_missile_id}")
            
        except Exception as e:
            print(f"Error handling engagement order: {e}")
    
    async def get_battery_position(self) -> Optional[Dict[str, float]]:
        """Get battery installation position"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT geom, altitude_m
                FROM installation
                WHERE callsign = $1
            """, self.callsign)
            
            if row:
                geom_str = row['geom']
                lon = float(geom_str.split('(')[1].split(' ')[0])
                lat = float(geom_str.split('(')[1].split(' ')[1])
                
                return {
                    "lat": lat,
                    "lon": lon,
                    "alt": row['altitude_m']
                }
        return None
    
    def can_engage(self) -> bool:
        """Check if battery can engage a target"""
        if self.status != "ready":
            return False
        
        if self.ammo_count <= 0:
            return False
        
        # Check if enough time has passed since last launch
        current_time = time.time()
        if current_time - self.last_launch_time < self.battery_capability.reload_time_sec:
            return False
        
        return True
    
    async def prepare_for_engagement(self, order: EngagementOrder) -> bool:
        """Prepare battery for engagement"""
        if not self.can_engage():
            return False
        
        # Check if intercept point is within range
        battery_pos = await self.get_battery_position()
        if not battery_pos:
            return False
        
        # Calculate distance to intercept point
        distance = self.calculate_distance(battery_pos, order.intercept_point)
        
        if distance > self.battery_capability.max_range_m:
            print(f"Intercept point {distance}m away exceeds range {self.battery_capability.max_range_m}m")
            return False
        
        if order.intercept_altitude > self.battery_capability.max_altitude_m:
            print(f"Intercept altitude {order.intercept_altitude}m exceeds max altitude {self.battery_capability.max_altitude_m}m")
            return False
        
        # Change status to preparing
        self.status = "preparing"
        
        # Simulate preparation time (5 seconds)
        await asyncio.sleep(5)
        
        return True
    
    def calculate_distance(self, pos1: Dict[str, float], pos2: Dict[str, float]) -> float:
        """Calculate 3D distance between two positions"""
        lat_diff = pos1['lat'] - pos2['lat']
        lon_diff = pos1['lon'] - pos2['lon']
        alt_diff = pos1['alt'] - pos2['alt']
        
        # Convert lat/lon to approximate meters
        lat_m = lat_diff * 111000  # ~111km per degree
        lon_m = lon_diff * 111000 * math.cos(math.radians(pos1['lat']))
        
        return math.sqrt(lat_m**2 + lon_m**2 + alt_diff**2)
    
    async def launch_missile(self, order: EngagementOrder) -> bool:
        """Launch a missile at the target"""
        if self.status != "preparing":
            return False
        
        # Change status to launching
        self.status = "launching"
        
        # Decrement ammo
        self.ammo_count -= 1
        
        # Update database
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE installation SET ammo_count = $1 WHERE callsign = $2
            """, self.ammo_count, self.callsign)
        
        # Generate missile ID and callsign
        missile_id = f"M{uuid.uuid4().hex[:8]}"
        missile_callsign = f"DEF_{self.callsign.split('_')[1]}_{missile_id[-4:]}"
        
        # Get battery position for launch
        battery_pos = await self.get_battery_position()
        if not battery_pos:
            return False
        
        # Create defense missile in database
        async with self.db_pool.acquire() as conn:
            platform_id = await conn.fetchval("""
                SELECT pt.id FROM platform_type pt
                JOIN installation i ON i.platform_type_id = pt.id
                WHERE i.callsign = $1
            """, self.callsign)
            
            await conn.execute("""
                INSERT INTO active_missile (
                    id, callsign, platform_type_id, launch_installation_id,
                    target_geom, target_altitude_m, launch_ts, current_geom,
                    current_altitude_m, velocity_x_mps, velocity_y_mps, velocity_z_mps,
                    fuel_remaining_kg, missile_type, target_missile_id
                ) VALUES ($1, $2, $3, 
                    (SELECT id FROM installation WHERE callsign = $4),
                    ST_SetSRID(ST_MakePoint($5, $6), 4326)::geography,
                    $7, NOW(), ST_SetSRID(ST_MakePoint($8, $9), 4326)::geography,
                    $10, $11, $12, $13, $14, $15, $16)
            """, missile_id, missile_callsign, platform_id, self.callsign,
                 order.intercept_point['lon'], order.intercept_point['lat'],
                 order.intercept_altitude, battery_pos['lon'], battery_pos['lat'],
                 battery_pos['alt'], 0, 0, 0, 1000, "defense", order.target_missile_id)
        
        # Send launch notification to simulation service
        launch_message = {
            "type": "missile_launch",
            "platform_nickname": "Aegis Ballistic Missile Defense System",  # Default
            "launch_callsign": self.callsign,
            "launch_lat": battery_pos['lat'],
            "launch_lon": battery_pos['lon'],
            "launch_alt": battery_pos['alt'],
            "target_lat": order.intercept_point['lat'],
            "target_lon": order.intercept_point['lon'],
            "target_alt": order.intercept_altitude,
            "missile_type": "defense",
            "target_missile_id": order.target_missile_id,
            "blast_radius": self.battery_capability.blast_radius_m,  # Include blast radius for intercept
            "timestamp": time.time()
        }
        
        await self.nats_client.publish(
            "simulation.launch",
            json.dumps(launch_message).encode()
        )
        
        # Record engagement attempt
        await self.record_engagement_attempt(order, missile_id)
        
        # Update timing
        self.last_launch_time = time.time()
        
        # Change status to reloading
        self.status = "reloading"
        
        print(f"Launched defense missile {missile_callsign} at target {order.target_missile_id}")
        
        return True
    
    async def record_engagement_attempt(self, order: EngagementOrder, missile_id: str):
        """Record engagement attempt in database"""
        # Update Prometheus metrics for battery engagement event position
        position_value = order.intercept_point['lat'] * 1000000 + (order.intercept_point['lon'] + 180) * 1000
        BATTERY_ENGAGEMENT_EVENT.labels(
            battery_callsign=self.callsign,
            target_missile_id=order.target_missile_id,
            timestamp=str(int(order.timestamp))
        ).inc()
        
        async with self.db_pool.acquire() as conn:
            # Get attempt number
            attempt_count = await conn.fetchval("""
                SELECT COUNT(*) FROM engagement_attempt
                WHERE target_missile_id = $1 AND defense_installation_id = 
                    (SELECT id FROM installation WHERE callsign = $2)
            """, order.target_missile_id, self.callsign)
            
            await conn.execute("""
                INSERT INTO engagement_attempt (
                    target_missile_id, defense_installation_id, attempt_number,
                    launch_ts, intercept_geom, intercept_altitude_m, status
                ) VALUES ($1, 
                    (SELECT id FROM installation WHERE callsign = $2),
                    $3, NOW(), ST_SetSRID(ST_MakePoint($4, $5), 4326)::geography,
                    $6, 'attempted')
            """, order.target_missile_id, self.callsign, attempt_count + 1,
                 order.intercept_point['lon'], order.intercept_point['lat'],
                 order.intercept_altitude)
    
    async def update_status(self):
        """Update battery status"""
        current_time = time.time()
        
        if self.status == "reloading":
            # Check if reload time has passed
            if current_time - self.last_launch_time >= self.battery_capability.reload_time_sec:
                self.status = "ready"
                print(f"Battery {self.callsign} ready for next engagement")
        
        # Update database status
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE installation SET status = $1 WHERE callsign = $2
            """, self.status, self.callsign)
    
    async def process_engagements(self):
        """Process pending engagements"""
        if not self.pending_engagements:
            return
        
        # Get highest priority engagement (first in list)
        order = self.pending_engagements[0]
        
        if self.current_engagement is None:
            # Start new engagement
            if await self.prepare_for_engagement(order):
                self.current_engagement = order
                self.pending_engagements.pop(0)
            else:
                # Remove failed engagement
                self.pending_engagements.pop(0)
                print(f"Failed to prepare for engagement of missile {order.target_missile_id}")
        
        elif self.current_engagement:
            # Launch missile
            if await self.launch_missile(self.current_engagement):
                self.current_engagement = None
            else:
                # Failed to launch, remove engagement
                self.current_engagement = None
                print(f"Failed to launch missile for engagement")
    
    async def run_battery(self):
        """Main battery operation loop"""
        print(f"Battery {self.callsign} operational")
        
        while True:
            try:
                # Update status
                await self.update_status()
                
                # Process engagements
                await self.process_engagements()
                
                # Wait before next cycle
                await asyncio.sleep(1.0)
                
            except Exception as e:
                print(f"Error in battery operation: {e}")
                await asyncio.sleep(1.0)

async def create_db_pool_with_retry(dsn, max_retries=30, delay=2):
    for attempt in range(max_retries):
        try:
            pool = await asyncpg.create_pool(dsn=dsn)
            print(f"Database connection established on attempt {attempt + 1}")
            return pool
        except Exception as e:
            print(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
            else:
                raise
    raise Exception("Failed to connect to database after all retries")

async def main():
    callsign = os.getenv("CALL_SIGN", "DEF_AEG_01")
    db_dsn = os.getenv("DB_DSN")
    nats_url = os.getenv("NATS_URL", "nats://nats:4222")
    if not db_dsn:
        raise ValueError("DB_DSN environment variable is required")

    db_pool = await create_db_pool_with_retry(db_dsn)
    nats_client = NATS()
    await nats_client.connect(nats_url)
    print("Connected to NATS")

    messaging = BatteryMessagingService(callsign, db_pool, nats_client)
    battery_capability, ammo_count = await messaging.load_battery_capabilities()
    logic = BatteryLogic(callsign, battery_capability, ammo_count)

    # Engagement order handler
    async def engagement_order_handler(msg):
        data = msg.data.decode()
        try:
            order_data = json.loads(data)
            if order_data.get('type') != 'engagement_order':
                return
            order = logic.EngagementOrder(
                target_missile_id=order_data['target_missile_id'],
                intercept_point=order_data['intercept_point'],
                intercept_altitude=order_data['intercept_altitude'],
                probability_of_success=order_data['probability_of_success'],
                timestamp=order_data['timestamp']
            )
            logic.pending_engagements.append(order)
            print(f"Received engagement order for missile {order.target_missile_id}")
        except Exception as e:
            print(f"Error handling engagement order: {e}")

    await messaging.subscribe_engagement_orders(engagement_order_handler)

    # API
    api_service = BatterySimAPI(logic)
    app = api_service.get_app()

    # Background battery operation loop
    async def battery_loop():
        print(f"Battery {callsign} operational")
        while True:
            try:
                # Update status, process engagements, etc.
                # (You may want to call logic methods or messaging as needed)
                await asyncio.sleep(1.0)
            except Exception as e:
                print(f"Error in battery operation: {e}")
                await asyncio.sleep(1.0)

    @app.on_event("startup")
    async def startup():
        asyncio.create_task(battery_loop())

    @app.on_event("shutdown")
    async def shutdown():
        print(f"Battery {callsign} shutting down...")
        await nats_client.close()
        await db_pool.close()

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8007,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())