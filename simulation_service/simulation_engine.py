"""
Simulation Engine for the Simulation Service
Contains physics engine and core simulation logic
"""
import asyncio
import json
import math
import time
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import asyncpg
import nats
from nats.aio.client import Client as NATS
import zmq.asyncio
from prometheus_client import Counter, Gauge, Histogram
import numpy as np
from scipy.integrate import solve_ivp
from scipy.spatial.distance import euclidean

# Prometheus metrics
MISSILE_UPDATES = Counter("missile_updates_total", "Total missile position updates")
DETECTION_EVENTS = Counter("detection_events_total", "Total radar detection events")
ENGAGEMENT_ATTEMPTS = Counter("engagement_attempts_total", "Total counter-missile engagement attempts")
INTERCEPTS = Counter("intercepts_total", "Total successful intercepts")
SIMULATION_TICKS = Counter("simulation_ticks_total", "Total simulation ticks")
ACTIVE_MISSILES = Gauge("active_missiles", "Number of active missiles")
ACTIVE_DEFENSES = Gauge("active_defenses", "Number of active defense missiles")
PHYSICS_CALC_TIME = Histogram("physics_calculation_seconds", "Time spent on physics calculations")

@dataclass
class Vector3D:
    x: float
    y: float
    z: float
    
    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)
    
    def normalize(self) -> 'Vector3D':
        mag = self.magnitude()
        if mag == 0:
            return Vector3D(0, 0, 0)
        return Vector3D(self.x/mag, self.y/mag, self.z/mag)
    
    def __add__(self, other: 'Vector3D') -> 'Vector3D':
        return Vector3D(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other: 'Vector3D') -> 'Vector3D':
        return Vector3D(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar: float) -> 'Vector3D':
        return Vector3D(self.x * scalar, self.y * scalar, self.z * scalar)

@dataclass
class MissileState:
    id: str
    callsign: str
    position: Vector3D
    velocity: Vector3D
    fuel_remaining: float
    mass: float
    thrust: float
    drag_coefficient: float
    cross_sectional_area: float
    target_position: Optional[Vector3D] = None
    missile_type: str = "attack"
    target_missile_id: Optional[str] = None
    status: str = "active"
    launch_time: float = 0.0

class PhysicsEngine:
    def __init__(self):
        self.gravity = 9.81  # m/s²
        self.air_density_sea_level = 1.225  # kg/m³
        self.scale_height = 8500  # m
        self.earth_radius = 6371000  # m
        
    def get_air_density(self, altitude: float) -> float:
        """Calculate air density at given altitude using exponential model"""
        return self.air_density_sea_level * math.exp(-altitude / self.scale_height)
    
    def get_gravity(self, altitude: float) -> float:
        """Calculate gravitational acceleration at given altitude"""
        return self.gravity * (self.earth_radius / (self.earth_radius + altitude))**2
    
    def calculate_drag_force(self, velocity: Vector3D, altitude: float, drag_coeff: float, area: float) -> Vector3D:
        """Calculate drag force based on velocity, altitude, and missile characteristics"""
        air_density = self.get_air_density(altitude)
        speed = velocity.magnitude()
        drag_force_magnitude = 0.5 * air_density * speed**2 * drag_coeff * area
        
        if speed > 0:
            drag_direction = Vector3D(-velocity.x/speed, -velocity.y/speed, -velocity.z/speed)
            return drag_direction * drag_force_magnitude
        return Vector3D(0, 0, 0)
    
    def calculate_thrust_force(self, thrust: float, direction: Vector3D) -> Vector3D:
        """Calculate thrust force in given direction"""
        return direction * thrust
    
    def missile_dynamics(self, t: float, state: List[float], missile: MissileState) -> List[float]:
        """Differential equations for missile flight dynamics"""
        x, y, z, vx, vy, vz = state
        
        position = Vector3D(x, y, z)
        velocity = Vector3D(vx, vy, vz)
        altitude = z
        
        # Gravity
        gravity = self.get_gravity(altitude)
        gravity_force = Vector3D(0, 0, -gravity * missile.mass)
        
        # Drag
        drag_force = self.calculate_drag_force(velocity, altitude, missile.drag_coefficient, missile.cross_sectional_area)
        
        # Thrust (if fuel available and missile is active)
        thrust_force = Vector3D(0, 0, 0)
        if missile.fuel_remaining > 0 and missile.status == "active":
            if missile.missile_type == "attack":
                # Attack missiles: thrust upward initially, then toward target
                if altitude < 10000:  # Initial boost phase
                    thrust_direction = Vector3D(0, 0, 1)
                else:
                    # Mid-course: thrust toward target
                    if missile.target_position:
                        direction_to_target = missile.target_position - position
                        thrust_direction = direction_to_target.normalize()
                    else:
                        thrust_direction = Vector3D(0, 0, 1)
            else:
                # Defense missiles: thrust toward target missile
                thrust_direction = Vector3D(0, 0, 1)  # Simplified for now
            
            thrust_force = self.calculate_thrust_force(missile.thrust, thrust_direction)
            
            # Fuel consumption
            fuel_consumption_rate = missile.thrust / 3000  # kg/s (simplified)
            missile.fuel_remaining = max(0, missile.fuel_remaining - fuel_consumption_rate * 0.1)  # 0.1s timestep
        
        # Total force
        total_force = gravity_force + drag_force + thrust_force
        
        # Acceleration
        acceleration = Vector3D(
            total_force.x / missile.mass,
            total_force.y / missile.mass,
            total_force.z / missile.mass
        )
        
        return [vx, vy, vz, acceleration.x, acceleration.y, acceleration.z]

class SimulationEngine:
    def __init__(self, db_pool: asyncpg.Pool, nats_client: NATS, zmq_context: zmq.asyncio.Context):
        self.db_pool = db_pool
        self.nats_client = nats_client
        self.zmq_context = zmq_context
        self.zmq_pub = self.zmq_context.socket(zmq.PUB)
        self.zmq_sub = self.zmq_context.socket(zmq.SUB)
        
        self.physics_engine = PhysicsEngine()
        self.missiles: Dict[str, MissileState] = {}
        self.installations: Dict[str, Dict] = {}
        self.simulation_config: Dict = {}
        self.simulation_tick_ms = 100  # 100ms simulation tick
        
        # Bind ZMQ sockets
        self.zmq_pub.bind("tcp://0.0.0.0:5555")
        self.zmq_sub.connect("tcp://0.0.0.0:5555")
        self.zmq_sub.setsockopt_string(zmq.SUBSCRIBE, "")
    
    async def initialize(self):
        """Initialize the simulation engine"""
        await self.load_simulation_config()
        await self.load_installations()
        
        # Subscribe to NATS messages
        await self.nats_client.subscribe("simulation.launch", cb=self.handle_nats_message)
        print("Subscribed to simulation.launch NATS topic")
        
        print("Simulation engine initialized")
    
    async def load_simulation_config(self):
        """Load simulation configuration from database"""
        async with self.db_pool.acquire() as conn:
            config_rows = await conn.fetch("SELECT config_key, config_value FROM simulation_config")
            self.simulation_config = {row['config_key']: row['config_value'] for row in config_rows}
    
    async def load_installations(self):
        """Load all installations from database"""
        async with self.db_pool.acquire() as conn:
            installations = await conn.fetch("""
                SELECT i.callsign, i.geom, i.altitude_m, i.status, i.ammo_count,
                       pt.category, pt.detection_range_m, pt.max_range_m, pt.max_altitude_m
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE i.status = 'active'
            """)
            
            for row in installations:
                # Parse geometry - convert WKB to WKT first
                async with self.db_pool.acquire() as conn:
                    geom_wkt = await conn.fetchval(
                        "SELECT ST_AsText(geom) FROM installation WHERE callsign = $1",
                        row['callsign']
                    )
                
                # Parse WKT format: POINT(lon lat)
                geom_parts = geom_wkt.replace('POINT(', '').replace(')', '').split(' ')
                lon = float(geom_parts[0])
                lat = float(geom_parts[1])
                
                self.installations[row['callsign']] = {
                    'geom': geom_wkt,
                    'lat': lat,
                    'lon': lon,
                    'altitude_m': row['altitude_m'],
                    'status': row['status'],
                    'ammo_count': row['ammo_count'],
                    'category': row['category'],
                    'detection_range_m': row['detection_range_m'],
                    'max_range_m': row['max_range_m'],
                    'max_altitude_m': row['max_altitude_m']
                }
    
    async def create_missile(self, platform_nickname: str, launch_callsign: str, 
                           launch_lat: float, launch_lon: float, launch_alt: float,
                           target_lat: float, target_lon: float, target_alt: float,
                           missile_type: str = "attack") -> str:
        """Create a new missile in the simulation"""
        missile_id = str(uuid.uuid4())
        
        # Get platform characteristics
        async with self.db_pool.acquire() as conn:
            platform = await conn.fetchrow("""
                SELECT max_speed_mps, max_range_m, max_altitude_m, blast_radius_m
                FROM platform_type WHERE nickname = $1
            """, platform_nickname)
            
            if not platform:
                raise ValueError(f"Platform {platform_nickname} not found")
        
        # Calculate initial velocity (simplified)
        initial_speed = min(platform['max_speed_mps'], 1000)  # m/s
        initial_velocity = Vector3D(0, 0, initial_speed)
        
        # Create missile state
        missile = MissileState(
            id=missile_id,
            callsign=f"{launch_callsign}_{missile_id[:8]}",
            position=Vector3D(launch_lon, launch_lat, launch_alt),
            velocity=initial_velocity,
            fuel_remaining=1000.0,  # kg
            mass=1000.0,  # kg
            thrust=50000.0,  # N
            drag_coefficient=0.3,
            cross_sectional_area=0.1,  # m²
            target_position=Vector3D(target_lon, target_lat, target_alt),
            missile_type=missile_type,
            launch_time=time.time()
        )
        
        self.missiles[missile_id] = missile
        ACTIVE_MISSILES.inc()
        
        # Store in database
        async with self.db_pool.acquire() as conn:
            platform_id = await conn.fetchval(
                "SELECT id FROM platform_type WHERE nickname = $1", platform_nickname
            )
            installation_id = await conn.fetchval(
                "SELECT id FROM installation WHERE callsign = $1", launch_callsign
            )
            
            await conn.execute("""
                INSERT INTO active_missile (
                    id, platform_type_id, launch_installation_id, callsign, missile_type,
                    target_geom, target_altitude_m, launch_ts, status
                ) VALUES ($1, $2, $3, $4, $5, 
                         ST_SetSRID(ST_MakePoint($6, $7), 4326)::geography,
                         $8, NOW(), 'active')
            """, missile_id, platform_id, installation_id, missile.callsign, missile_type,
                 target_lon, target_lat, target_alt)
        
        print(f"Created missile {missile.callsign} at {launch_lat}, {launch_lon}")
        return missile_id
    
    async def update_missile_physics(self, missile_id: str, dt: float):
        """Update missile physics for one timestep"""
        missile = self.missiles[missile_id]
        if missile.status != "active":
            return
        
        with PHYSICS_CALC_TIME.time():
            # Current state
            state = [
                missile.position.x, missile.position.y, missile.position.z,
                missile.velocity.x, missile.velocity.y, missile.velocity.z
            ]
            
            # Solve differential equations
            solution = solve_ivp(
                lambda t, y: self.physics_engine.missile_dynamics(t, y, missile),
                [0, dt], state, method='RK45', t_eval=[dt]
            )
            
            # Update missile state
            new_state = solution.y.flatten()
            missile.position = Vector3D(new_state[0], new_state[1], new_state[2])
            missile.velocity = Vector3D(new_state[3], new_state[4], new_state[5])
            
            # Check for impact or fuel exhaustion
            if missile.position.z <= 0 or missile.fuel_remaining <= 0:
                await self.handle_missile_impact(missile_id)
    
    async def handle_missile_impact(self, missile_id: str):
        """Handle missile impact or destruction"""
        missile = self.missiles[missile_id]
        missile.status = "impacted"
        
        # Record detonation event
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO detonation_event (
                    missile_id, detonation_geom, detonation_altitude_m, blast_radius_m
                ) VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326)::geography, $4, $5)
            """, missile_id, missile.position.x, missile.position.y, 
                 missile.position.z, 200)  # Default blast radius
        
        # Remove from active missiles
        del self.missiles[missile_id]
        ACTIVE_MISSILES.dec()
        
        print(f"Missile {missile.callsign} detonated at {missile.position}")
    
    async def handle_intercept(self, defense_missile_id: str, target_missile_id: str):
        """Handle successful intercept"""
        defense_missile = self.missiles[defense_missile_id]
        target_missile = self.missiles[target_missile_id]
        
        # Mark both missiles as destroyed
        defense_missile.status = "destroyed"
        target_missile.status = "destroyed"
        
        # Record engagement
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO engagement (
                    target_missile_id, defense_missile_id, launch_installation_id,
                    intercept_geom, intercept_altitude_m, status, intercept_distance_m
                ) VALUES ($1, $2, 
                    (SELECT id FROM installation WHERE callsign = $3),
                    ST_SetSRID(ST_MakePoint($4, $5), 4326)::geography,
                    $6, 'intercepted', $7)
            """, target_missile_id, defense_missile_id, defense_missile.callsign,
                 defense_missile.position.x, defense_missile.position.y,
                 defense_missile.position.z, 50)  # Approximate intercept distance
        
        # Remove from active missiles
        del self.missiles[defense_missile_id]
        del self.missiles[target_missile_id]
        ACTIVE_MISSILES.dec()
        ACTIVE_MISSILES.dec()
        
        INTERCEPTS.inc()
        print(f"Intercept successful: {defense_missile.callsign} destroyed {target_missile.callsign}")
    
    async def check_detections(self):
        """Check for missile detections by radar installations"""
        for installation_callsign, installation in self.installations.items():
            if installation['category'] != 'detection_system':
                continue
            
            # Get detection range and update interval
            detection_range = installation.get('detection_range_m', 100000)
            update_interval = int(self.simulation_config.get('radar_update_interval_ms', '1000'))
            
            # Check if it's time for this radar to update
            current_time = time.time() * 1000  # Convert to milliseconds
            if int(current_time) % update_interval != 0:
                continue
            
            # Check each active missile
            for missile_id, missile in self.missiles.items():
                if missile.missile_type != "attack":
                    continue
                
                # Calculate distance to missile
                radar_pos = Vector3D(
                    installation['lon'],
                    installation['lat'],
                    installation['altitude_m']
                )
                
                distance = (missile.position - radar_pos).magnitude()
                
                if distance <= detection_range:
                    # Create detection event
                    await self.create_detection_event(installation_callsign, missile_id, missile.position)
    
    async def create_detection_event(self, radar_callsign: str, missile_id: str, position: Vector3D):
        """Create a radar detection event"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO detection_event (
                    detection_installation_id, detected_missile_id,
                    detection_geom, detection_altitude_m, detection_ts,
                    signal_strength_db, confidence_percent
                ) VALUES (
                    (SELECT id FROM installation WHERE callsign = $1),
                    $2, ST_SetSRID(ST_MakePoint($3, $4), 4326)::geography,
                    $5, NOW(), $6, $7
                )
            """, radar_callsign, missile_id, position.x, position.y, position.z,
                 -50, 85)  # Typical radar signal strength and confidence
        
        DETECTION_EVENTS.inc()
        
        # Notify command center via NATS
        await self.nats_client.publish(
            "radar.detection",
            json.dumps({
                "radar_callsign": radar_callsign,
                "missile_id": missile_id,
                "position": {"x": position.x, "y": position.y, "z": position.z},
                "timestamp": time.time()
            }).encode()
        )
    
    async def broadcast_missile_positions(self):
        """Broadcast missile positions to all subscribers"""
        for missile_id, missile in self.missiles.items():
            if missile.status != "active":
                continue
            
            # Update database
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE active_missile SET
                        current_geom = ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                        current_altitude_m = $3,
                        velocity_x_mps = $4, velocity_y_mps = $5, velocity_z_mps = $6,
                        fuel_remaining_kg = $7, updated_at = NOW()
                    WHERE id = $8
                """, missile.position.x, missile.position.y, missile.position.z,
                     missile.velocity.x, missile.velocity.y, missile.velocity.z,
                     missile.fuel_remaining, missile_id)
            
            # Broadcast via ZMQ
            await self.zmq_pub.send_json({
                "id": missile_id,
                "callsign": missile.callsign,
                "position": {"x": missile.position.x, "y": missile.position.y, "z": missile.position.z},
                "velocity": {"x": missile.velocity.x, "y": missile.velocity.y, "z": missile.velocity.z},
                "timestamp": time.time(),
                "missile_type": missile.missile_type
            })
            
            MISSILE_UPDATES.inc()
    
    async def run_simulation_loop(self):
        """Main simulation loop"""
        print("Starting simulation loop...")
        
        while True:
            start_time = time.time()
            
            # Update physics for all missiles
            dt = self.simulation_tick_ms / 1000.0  # Convert to seconds
            for missile_id in list(self.missiles.keys()):
                await self.update_missile_physics(missile_id, dt)
            
            # Check for detections
            await self.check_detections()
            
            # Broadcast positions
            await self.broadcast_missile_positions()
            
            # Process incoming messages
            await self.process_messages()
            
            # Wait for next tick
            elapsed = time.time() - start_time
            sleep_time = max(0, (self.simulation_tick_ms / 1000.0) - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            
            SIMULATION_TICKS.inc()
    
    async def process_messages(self):
        """Process incoming messages from other services"""
        # Process ZMQ messages
        try:
            while await self.zmq_sub.poll(timeout=1):
                message = await self.zmq_sub.recv_json()
                await self.handle_message(message)
        except Exception as e:
            print(f"Error processing ZMQ message: {e}")
        
        # Process NATS messages
        # (NATS subscription handling would go here)
    
    async def handle_message(self, message: dict):
        """Handle incoming messages"""
        msg_type = message.get("type")
        
        if msg_type == "missile_launch":
            await self.handle_missile_launch(message)
        elif msg_type == "engagement_request":
            await self.handle_engagement_request(message)
        elif msg_type == "detonation":
            await self.handle_detonation(message)
    
    async def handle_missile_launch(self, message: dict):
        """Handle missile launch request"""
        try:
            missile_id = await self.create_missile(
                platform_nickname=message["platform_nickname"],
                launch_callsign=message["launch_callsign"],
                launch_lat=message["launch_lat"],
                launch_lon=message["launch_lon"],
                launch_alt=message["launch_alt"],
                target_lat=message["target_lat"],
                target_lon=message["target_lon"],
                target_alt=message["target_alt"],
                missile_type=message.get("missile_type", "attack")
            )
            print(f"Launched missile {missile_id}")
        except Exception as e:
            print(f"Error launching missile: {e}")
    
    async def handle_engagement_request(self, message: dict):
        """Handle engagement request"""
        # Implementation for engagement requests
        pass
    
    async def handle_detonation(self, message: dict):
        """Handle detonation event"""
        # Implementation for detonation events
        pass
    
    async def handle_nats_message(self, msg):
        """Handle incoming NATS messages"""
        try:
            import json
            message = json.loads(msg.data.decode())
            await self.handle_message(message)
        except Exception as e:
            print(f"Error handling NATS message: {e}") 