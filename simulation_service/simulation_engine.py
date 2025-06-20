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
    fuel_consumption_rate: float  # kg/s
    target_position: Optional[Vector3D] = None
    missile_type: str = "attack"
    target_missile_id: Optional[str] = None
    status: str = "active"
    launch_time: float = 0.0
    blast_radius: float = 0.0  # Will be set from database platform_type

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
    
    def calculate_drag_force(self, velocity: Vector3D, altitude: float, drag_coeff: float, area: float, fluid_density: float = None) -> Vector3D:
        """Calculate drag force on missile"""
        # Use provided fluid density or calculate air density
        if fluid_density is None:
            fluid_density = self.get_air_density(altitude)
        
        # Drag force = 0.5 * ρ * v² * Cd * A
        velocity_magnitude = velocity.magnitude()
        drag_magnitude = 0.5 * fluid_density * velocity_magnitude**2 * drag_coeff * area
        
        # Drag acts opposite to velocity direction
        if velocity_magnitude > 0:
            drag_direction = Vector3D(-velocity.x, -velocity.y, -velocity.z).normalize()
        else:
            drag_direction = Vector3D(0, 0, 0)
        
        return drag_direction * drag_magnitude
    
    def calculate_thrust_force(self, thrust: float, direction: Vector3D) -> Vector3D:
        """Calculate thrust force in given direction"""
        return direction * thrust
    
    def get_water_density(self, depth: float) -> float:
        """Get water density at given depth (kg/m³)"""
        # Seawater density increases with depth due to pressure
        # Surface: ~1025 kg/m³, increases by ~1 kg/m³ per 100m depth
        surface_density = 1025.0  # kg/m³
        depth_factor = 1.0 + (abs(depth) / 10000.0)  # Small increase with depth
        return surface_density * depth_factor
    
    def get_water_drag_coefficient(self, velocity: float) -> float:
        """Get water drag coefficient based on velocity"""
        # Water drag is much higher than air drag
        # Submarine torpedoes: ~0.3-0.5, missiles: ~0.2-0.4
        base_drag = 0.35
        # Increase drag at higher velocities due to cavitation
        if velocity > 50:  # m/s
            base_drag *= 1.2
        return base_drag
    
    def missile_dynamics(self, t: float, state: List[float], missile: MissileState) -> List[float]:
        """Differential equations for missile flight dynamics with realistic parabolic trajectories"""
        x, y, z, vx, vy, vz = state
        
        position = Vector3D(x, y, z)
        velocity = Vector3D(vx, vy, vz)
        altitude = z
        velocity_magnitude = velocity.magnitude()
        
        # Determine environment (underwater vs air)
        is_underwater = altitude < 0
        
        # Gravity
        gravity = self.get_gravity(altitude)
        gravity_force = Vector3D(0, 0, -gravity * missile.mass)
        
        # Drag force (different for water vs air)
        if is_underwater:
            # Underwater drag
            water_density = self.get_water_density(altitude)
            water_drag_coeff = self.get_water_drag_coefficient(velocity_magnitude)
            drag_force = self.calculate_drag_force(velocity, altitude, water_drag_coeff, missile.cross_sectional_area, water_density)
        else:
            # Air drag
            drag_force = self.calculate_drag_force(velocity, altitude, missile.drag_coefficient, missile.cross_sectional_area)
        
        # Thrust (if fuel available and missile is active)
        thrust_force = Vector3D(0, 0, 0)
        if missile.fuel_remaining > 0 and missile.status == "active":
            if missile.missile_type == "attack":
                # Realistic ballistic missile trajectory phases
                if is_underwater:
                    # Phase 1: Underwater boost (first 2-3 seconds)
                    if t < 3.0:  # First 3 seconds underwater
                        thrust_direction = Vector3D(0, 0, 1)  # Primarily upward
                        thrust_magnitude = missile.thrust * 0.5  # Reduced thrust underwater
                    else:
                        # Phase 2: Transition to main propulsion
                        thrust_direction = Vector3D(0, 0, 1)  # Continue upward
                        thrust_magnitude = missile.thrust * 0.9  # Increased thrust
                else:
                    # Phase 3: Airborne flight - realistic ballistic trajectory
                    if altitude < 1000:  # Initial boost phase
                        # Continue upward boost for first 1km
                        thrust_direction = Vector3D(0, 0, 1)
                        thrust_magnitude = missile.thrust
                    elif altitude < 50000:  # Mid-course phase - create parabolic arc
                        # Calculate optimal trajectory to target
                        if missile.target_position:
                            # Calculate required velocity for ballistic trajectory
                            target_pos = missile.target_position
                            dx = target_pos.x - position.x
                            dy = target_pos.y - position.y
                            dz = target_pos.z - position.z
                            
                            # Calculate horizontal distance
                            horizontal_distance = math.sqrt(dx*dx + dy*dy)
                            
                            # For ballistic trajectory, we need to calculate optimal angle
                            # This is a simplified ballistic calculation
                            if horizontal_distance > 0:
                                # Calculate required velocity for ballistic trajectory
                                # Using simplified ballistic equations
                                g = gravity
                                # Optimal angle for maximum range is 45 degrees
                                # But we'll use a more realistic angle based on distance
                                optimal_angle = min(60, max(30, math.degrees(math.atan2(abs(dz), horizontal_distance))))
                                
                                # Calculate thrust direction based on optimal trajectory
                                horizontal_direction = Vector3D(dx/horizontal_distance, dy/horizontal_distance, 0)
                                vertical_component = math.sin(math.radians(optimal_angle))
                                horizontal_component = math.cos(math.radians(optimal_angle))
                                
                                thrust_direction = (horizontal_direction * horizontal_component + Vector3D(0, 0, vertical_component)).normalize()
                            else:
                                thrust_direction = Vector3D(0, 0, 1)
                        else:
                            thrust_direction = Vector3D(0, 0, 1)
                        thrust_magnitude = missile.thrust * 0.8
                    else:  # Terminal phase - ballistic descent
                        # Missile is in ballistic descent, minimal thrust
                        thrust_magnitude = 0  # No thrust in terminal phase
                        thrust_direction = Vector3D(0, 0, 0)
            else:
                # Defense missiles: thrust toward target missile
                thrust_direction = Vector3D(0, 0, 1)  # Simplified for now
                thrust_magnitude = missile.thrust
            
            thrust_force = self.calculate_thrust_force(thrust_magnitude, thrust_direction)
        
        # Buoyancy force (only underwater)
        buoyancy_force = Vector3D(0, 0, 0)
        if is_underwater:
            # Buoyancy = ρ_water * V * g
            water_density = self.get_water_density(altitude)
            missile_volume = missile.mass / 1000.0  # Rough estimate: 1kg ≈ 1L
            buoyancy_magnitude = water_density * missile_volume * gravity
            buoyancy_force = Vector3D(0, 0, buoyancy_magnitude)
        
        # Net force
        net_force = gravity_force + drag_force + thrust_force + buoyancy_force
        
        # Acceleration = F/m
        acceleration = net_force * (1.0 / missile.mass)
        
        # Return derivatives: [dx/dt, dy/dt, dz/dt, dvx/dt, dvy/dt, dvz/dt]
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
        self.detected_missiles = {}  # {radar_callsign: set(missile_ids)}
        
        # Bind ZMQ sockets
        self.zmq_pub.bind("tcp://0.0.0.0:5555")
        self.zmq_sub.connect("tcp://0.0.0.0:5555")
        self.zmq_sub.setsockopt_string(zmq.SUBSCRIBE, "")
    
    async def initialize(self):
        """Initialize the simulation engine"""
        await self.load_simulation_config()
        await self.load_installations()
        
        # Subscribe to NATS topics
        await self.nats_client.subscribe("simulation.launch", cb=self.handle_nats_message)
        await self.nats_client.subscribe("radar.detection_areas", cb=self.handle_radar_detection_areas)
        
        print("Simulation engine initialized and subscribed to NATS topics")
    
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
                           missile_type: str = "attack", blast_radius: float = None, 
                           target_missile_id: str = None) -> str:
        """Create a new missile in the simulation"""
        missile_id = str(uuid.uuid4())
        
        # Get platform characteristics from database
        async with self.db_pool.acquire() as conn:
            platform = await conn.fetchrow("""
                SELECT max_speed_mps, max_range_m, max_altitude_m, blast_radius_m,
                       fuel_capacity_kg, fuel_consumption_rate_kgps, thrust_n, nickname
                FROM platform_type WHERE nickname = $1
            """, platform_nickname)
            
            if not platform:
                raise ValueError(f"Platform {platform_nickname} not found")
        
        # Use provided blast radius or database value
        missile_blast_radius = blast_radius if blast_radius is not None else float(platform['blast_radius_m']) if platform['blast_radius_m'] else 0.0
        
        # Use realistic values for JL-2 and similar SLBMs
        if platform_nickname in ["JL-2", "UGM-133 Trident II"]:
            missile_mass = 42000.0  # kg
            missile_thrust = 600000.0  # N
            missile_drag_coeff = 0.25
            missile_area = 3.14  # m² (2m diameter)
        else:
            missile_mass = 1000.0  # Default mass in kg
            missile_thrust = float(platform['thrust_n']) if platform['thrust_n'] else 50000.0
            missile_drag_coeff = 0.3
            missile_area = 0.1  # m²
        missile_fuel = float(platform['fuel_capacity_kg']) if platform['fuel_capacity_kg'] else 1000.0
        missile_fuel_consumption_rate = float(platform['fuel_consumption_rate_kgps']) if platform['fuel_consumption_rate_kgps'] else 50.0
        
        # Calculate initial velocity for underwater launch
        initial_speed = min(float(platform['max_speed_mps']), 1000.0)
        if launch_alt < 0:  # Underwater launch
            initial_velocity = Vector3D(0, 0, 50.0)  # 50 m/s upward initially
        else:
            target_pos = Vector3D(float(target_lon), float(target_lat), float(target_alt))
            launch_pos = Vector3D(float(launch_lon), float(launch_lat), float(launch_alt))
            direction_to_target = target_pos - launch_pos
            if direction_to_target.magnitude() > 0:
                initial_velocity = direction_to_target.normalize() * initial_speed
            else:
                initial_velocity = Vector3D(0, 0, initial_speed)
        
        missile = MissileState(
            id=missile_id,
            callsign=f"{launch_callsign}_{missile_id[:8]}",
            position=Vector3D(launch_lon, launch_lat, launch_alt),
            velocity=initial_velocity,
            fuel_remaining=missile_fuel,
            mass=missile_mass,
            thrust=missile_thrust,
            drag_coefficient=missile_drag_coeff,
            cross_sectional_area=missile_area,
            fuel_consumption_rate=missile_fuel_consumption_rate,
            target_position=Vector3D(target_lon, target_lat, target_alt),
            missile_type=missile_type,
            launch_time=time.time(),
            blast_radius=missile_blast_radius,
            target_missile_id=target_missile_id
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
                    target_geom, target_altitude_m, launch_ts, status, target_missile_id
                ) VALUES ($1, $2, $3, $4, $5, 
                         ST_SetSRID(ST_MakePoint($6, $7), 4326)::geography,
                         $8, NOW(), 'active', $9)
            """, missile_id, platform_id, installation_id, missile.callsign, missile_type,
                 target_lon, target_lat, target_alt, missile.target_missile_id)
        
        print(f"Created missile {missile.callsign} at {launch_lat}, {launch_lon}")
        return missile_id
    
    async def update_missile_physics(self, missile_id: str, dt: float):
        """Update missile physics for one timestep"""
        missile = self.missiles[missile_id]
        
        # Initialize launch time if not set
        if missile.launch_time == 0:
            missile.launch_time = time.time()
            print(f"DEBUG: Missile {missile.callsign} starting physics at position {missile.position}, velocity {missile.velocity}")
        
        # Get current state
        state = [missile.position.x, missile.position.y, missile.position.z,
                missile.velocity.x, missile.velocity.y, missile.velocity.z]
        
        # Calculate derivatives using physics engine
        derivatives = self.physics_engine.missile_dynamics(time.time() - missile.launch_time, state, missile)
        
        # Update position and velocity using simple Euler integration
        missile.position.x += derivatives[0] * dt
        missile.position.y += derivatives[1] * dt
        missile.position.z += derivatives[2] * dt
        missile.velocity.x = derivatives[3]
        missile.velocity.y = derivatives[4]
        missile.velocity.z = derivatives[5]
        
        # Consume fuel based on thrust usage
        if missile.fuel_remaining > 0 and missile.status == "active":
            current_thrust_ratio = 1.0
            if missile.position.z < 0:
                if time.time() - missile.launch_time < 3.0:
                    current_thrust_ratio = 0.5
                else:
                    current_thrust_ratio = 0.9
            else:
                if missile.position.z < 1000:
                    current_thrust_ratio = 1.0
                elif missile.position.z < 10000:
                    current_thrust_ratio = 0.9
                else:
                    current_thrust_ratio = 0.7
            fuel_consumed = missile.fuel_consumption_rate * current_thrust_ratio * dt
            missile.fuel_remaining = max(0, missile.fuel_remaining - fuel_consumed)
        
        if int(time.time() - missile.launch_time) % 10 == 0 and int(time.time() - missile.launch_time) > 0:
            print(f"DEBUG: Missile {missile.callsign} at t={time.time() - missile.launch_time:.1f}s: pos={missile.position}, vel={missile.velocity}, fuel={missile.fuel_remaining:.1f}kg")
        
        # Check for impact or fuel exhaustion
        if missile.fuel_remaining <= 0:
            print(f"DEBUG: Missile {missile.callsign} ran out of fuel at position {missile.position}")
            await self.handle_missile_impact(missile_id)
        elif missile.position.z <= -300 and missile.velocity.z < 0:
            # Missile hit seabed, detonate
            print(f"DEBUG: Missile {missile.callsign} hit seabed at position {missile.position}")
            await self.handle_missile_impact(missile_id)
        elif missile.position.z <= 0 and missile.velocity.z < 0 and missile.position.z > -300:
            # Missile hit water surface, but do not detonate, allow to continue
            pass
        elif missile.target_position and missile.position.z > 0:
            distance_to_target = (missile.position - missile.target_position).magnitude()
            # Use the blast radius that was set from the database during missile creation
            blast_radius = missile.blast_radius
            if blast_radius <= 0:
                print(f"WARNING: Missile {missile.callsign} has no blast radius set, using default 200m")
                blast_radius = 200.0
                
            target_horizontal_distance = math.sqrt(
                (missile.position.x - missile.target_position.x)**2 + 
                (missile.position.y - missile.target_position.y)**2
            )
            is_above_target = missile.position.z > missile.target_position.z
            is_within_blast_radius = target_horizontal_distance <= blast_radius
            is_descending = missile.velocity.z < 0
            if is_above_target and is_within_blast_radius and is_descending:
                print(f"DEBUG: Missile {missile.callsign} detonating above target at position {missile.position} (blast radius: {blast_radius}m)")
                await self.handle_missile_impact(missile_id)
        
        # Check for intercepts
        await self.check_intercepts()
    
    async def check_intercepts(self):
        """Check for intercepts between defense missiles and their targets"""
        for defense_missile_id, defense_missile in self.missiles.items():
            if (defense_missile.missile_type != "defense" or 
                defense_missile.status != "active" or 
                not defense_missile.target_missile_id):
                continue
            
            target_missile_id = defense_missile.target_missile_id
            if target_missile_id not in self.missiles:
                continue
            
            target_missile = self.missiles[target_missile_id]
            if target_missile.status != "active":
                continue
            
            # Calculate distance between defense missile and target
            distance = (defense_missile.position - target_missile.position).magnitude()
            
            # Check if defense missile is within blast radius of target
            if distance <= defense_missile.blast_radius:
                print(f"Intercept: Defense missile {defense_missile.callsign} intercepted target {target_missile.callsign} at distance {distance:.1f}m")
                
                # Handle the intercept
                await self.handle_intercept(defense_missile_id, target_missile_id)
                
                # Also handle the defense missile impact
                await self.handle_missile_impact(defense_missile_id)
    
    async def handle_missile_impact(self, missile_id: str):
        """Handle missile impact/detonation and record outcome"""
        if missile_id not in self.missiles:
            return
            
        missile = self.missiles[missile_id]
        
        # Determine outcome type
        outcome_type = 'detonated'
        target_achieved = False
        notes = ""
        
        if missile.fuel_remaining <= 0:
            outcome_type = 'fuel_exhaustion'
            notes = "Missile ran out of fuel"
        elif missile.position.z <= 0:
            outcome_type = 'ground_impact'
            notes = "Missile hit ground/water"
        elif missile.target_position:
            # Check if missile detonated near target
            distance_to_target = (missile.position - missile.target_position).magnitude()
            if distance_to_target <= missile.blast_radius:
                target_achieved = True
                notes = f"Target achieved, detonated {distance_to_target:.1f}m from target"
            else:
                notes = f"Missed target by {distance_to_target:.1f}m"
        
        # Record outcome in database
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO missile_outcome (
                    missile_id, callsign, missile_type, outcome_type, 
                    outcome_location, outcome_altitude_m, blast_radius_m,
                    target_achieved, notes
                ) VALUES ($1, $2, $3, $4, ST_SetSRID(ST_MakePoint($5, $6), 4326), $7, $8, $9, $10)
            """, 
                missile_id, missile.callsign, 'attack', outcome_type,
                missile.position.x, missile.position.y, missile.position.z,
                missile.blast_radius, target_achieved, notes
            )
            
            # Remove from active_missile table
            await conn.execute("DELETE FROM active_missile WHERE id = $1", missile_id)
        
        print(f"Missile {missile.callsign} {outcome_type} at {missile.position}")
        
        # Remove from active missiles
        del self.missiles[missile_id]
        
        # Publish impact event
        impact_event = {
            "type": "missile_impact",
            "missile_id": missile_id,
            "callsign": missile.callsign,
            "outcome_type": outcome_type,
            "position": {"x": missile.position.x, "y": missile.position.y, "z": missile.position.z},
            "target_achieved": target_achieved,
            "timestamp": time.time()
        }
        
        await self.nats_client.publish("missile.impact", json.dumps(impact_event).encode())
    
    async def handle_intercept(self, defense_missile_id: str, target_missile_id: str):
        """Handle missile interception and record outcome"""
        if target_missile_id not in self.missiles:
            return
            
        target_missile = self.missiles[target_missile_id]
        
        # Record interception outcome
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO missile_outcome (
                    missile_id, callsign, missile_type, outcome_type, 
                    outcome_location, outcome_altitude_m, blast_radius_m,
                    target_achieved, intercepting_missile_id, notes
                ) VALUES ($1, $2, $3, $4, ST_SetSRID(ST_MakePoint($5, $6), 4326), $7, $8, $9, $10, $11)
            """, 
                target_missile_id, target_missile.callsign, 'attack', 'intercepted',
                target_missile.position.x, target_missile.position.y, target_missile.position.z,
                target_missile.blast_radius, False, defense_missile_id, "Successfully intercepted by defense missile"
            )
            
            # Remove from active_missile table
            await conn.execute("DELETE FROM active_missile WHERE id = $1", target_missile_id)
        
        print(f"Missile {target_missile.callsign} intercepted by defense missile {defense_missile_id}")
        
        # Remove from active missiles
        del self.missiles[target_missile_id]
        
        # Publish interception event
        intercept_event = {
            "type": "missile_intercepted",
            "target_missile_id": target_missile_id,
            "defense_missile_id": defense_missile_id,
            "callsign": target_missile.callsign,
            "position": {"x": target_missile.position.x, "y": target_missile.position.y, "z": target_missile.position.z},
            "timestamp": time.time()
        }
        
        await self.nats_client.publish("missile.intercepted", json.dumps(intercept_event).encode())
    
    async def check_detections(self):
        """Check for missile detections by radars and send events via NATS"""
        for radar_callsign, radar in self.installations.items():
            if radar['category'] != 'detection_system':
                continue
            detection_range = float(radar['detection_range_m'])
            radar_pos = Vector3D(float(radar['lon']), float(radar['lat']), float(radar['altitude_m']))
            detected_set = self.detected_missiles.setdefault(radar_callsign, set())
            for missile_id, missile in self.missiles.items():
                if missile.status != 'active':
                    continue
                # Calculate distance (simple Euclidean for now)
                dx = missile.position.x - radar_pos.x
                dy = missile.position.y - radar_pos.y
                dz = missile.position.z - radar_pos.z
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist <= detection_range and missile_id not in detected_set:
                    # New detection
                    detected_set.add(missile_id)
                    detection_event = {
                        'radar_callsign': radar_callsign,
                        'missile_id': missile_id,
                        'missile_position': {'x': missile.position.x, 'y': missile.position.y, 'z': missile.position.z},
                        'timestamp': time.time(),
                        'signal_strength_db': 100,  # Placeholder
                        'confidence_percent': 95    # Placeholder
                    }
                    await self.nats_client.publish('detection.event', json.dumps(detection_event).encode())
                    print(f"Detection: Radar {radar_callsign} detected missile {missile_id} at {missile.position}")
    
    async def broadcast_missile_positions(self):
        """Broadcast missile positions to all subscribers"""
        # Create a copy of missile IDs to avoid dictionary changed size during iteration
        missile_ids = list(self.missiles.keys())
        
        for missile_id in missile_ids:
            if missile_id not in self.missiles:
                continue  # Missile was removed during iteration
                
            missile = self.missiles[missile_id]
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
            
            # Also broadcast via NATS for radar service
            await self.nats_client.publish(
                "missile.position",
                json.dumps({
                    "id": missile_id,
                    "callsign": missile.callsign,
                    "position": {"x": missile.position.x, "y": missile.position.y, "z": missile.position.z},
                    "velocity": {"x": missile.velocity.x, "y": missile.velocity.y, "z": missile.velocity.z},
                    "timestamp": time.time(),
                    "missile_type": missile.missile_type
                }).encode()
            )
            
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
                missile_type=message.get("missile_type", "attack"),
                blast_radius=message.get("blast_radius"),
                target_missile_id=message.get("target_missile_id")
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
    
    async def handle_radar_detection_areas(self, msg):
        """Handle incoming radar detection areas from radar service"""
        try:
            data = json.loads(msg.data.decode())
            if data.get('type') == 'detection_areas_update':
                radars = data.get('radars', [])
                
                # Update radar installations with detection area information
                for radar_data in radars:
                    radar_callsign = radar_data['radar_callsign']
                    if radar_callsign in self.installations:
                        # Update the installation with radar-specific data
                        self.installations[radar_callsign].update({
                            'detection_range_m': radar_data['detection_range_m'],
                            'max_altitude_m': radar_data['max_altitude_m'],
                            'sweep_rate_deg_per_sec': radar_data['sweep_rate_deg_per_sec'],
                            'update_interval_ms': radar_data['update_interval_ms'],
                            'radar_status': radar_data['status']
                        })
                
                print(f"Updated detection areas for {len(radars)} radars")
                
        except Exception as e:
            print(f"Error handling radar detection areas: {e}") 