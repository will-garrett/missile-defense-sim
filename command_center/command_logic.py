"""
Command Logic for the Command Center Service
Contains threat assessment and engagement coordination logic
"""
import asyncio
import json
import math
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import asyncpg
import nats
from nats.aio.client import Client as NATS
import zmq.asyncio
from prometheus_client import Counter, Gauge, Histogram
import numpy as np

# Prometheus metrics
THREAT_ASSESSMENTS = Counter("threat_assessments_total", "Total threat assessments performed")
ENGAGEMENT_ORDERS = Counter("engagement_orders_total", "Total engagement orders issued")
BATTERY_SELECTIONS = Counter("battery_selections_total", "Total battery selections made")
INTERCEPT_PREDICTIONS = Counter("intercept_predictions_total", "Total intercept predictions calculated")
COMMAND_DECISIONS = Histogram("command_decision_seconds", "Time spent on command decisions")

@dataclass
class ThreatAssessment:
    missile_id: str
    missile_callsign: str
    current_position: Tuple[float, float, float]  # lat, lon, alt
    current_velocity: Tuple[float, float, float]  # vx, vy, vz
    predicted_impact_point: Tuple[float, float, float]
    time_to_impact: float
    threat_level: str  # 'low', 'medium', 'high', 'critical'
    confidence: float
    detection_sources: List[str]

@dataclass
class BatteryCapability:
    battery_id: int
    callsign: str
    position: Tuple[float, float, float]
    max_range: float
    max_altitude: float
    accuracy: float
    reload_time: float
    ammo_count: int
    status: str
    time_to_ready: float

@dataclass
class InterceptSolution:
    battery_callsign: str
    intercept_point: Tuple[float, float, float]
    intercept_time: float
    intercept_altitude: float
    probability_of_success: float
    time_to_launch: float

class CommandLogic:
    def __init__(self, db_pool: asyncpg.Pool, nats_client: NATS, zmq_context: zmq.asyncio.Context):
        self.db_pool = db_pool
        self.nats_client = nats_client
        self.zmq_context = zmq_context
        self.zmq_pub = self.zmq_context.socket(zmq.PUB)
        
        self.active_threats: Dict[str, ThreatAssessment] = {}
        self.available_batteries: Dict[str, BatteryCapability] = {}
        self.engagement_attempts: Dict[str, List[Dict]] = {}  # missile_id -> attempts
        self.max_retries = 3
        
        # Bind ZMQ socket
        self.zmq_pub.bind("tcp://0.0.0.0:5558")  # Command center channel
    
    async def initialize(self):
        """Initialize the command logic"""
        # Subscribe to radar detections
        await self.nats_client.subscribe("radar.detection", cb=self.handle_radar_detection)
        
        # Subscribe to missile position updates
        await self.nats_client.subscribe("missile.position", cb=self.handle_missile_position)
        
        # Subscribe to engagement results
        await self.nats_client.subscribe("engagement.result", cb=self.handle_engagement_result)
        
        # Load available batteries
        await self.load_available_batteries()
        
        print("Command logic initialized")
    
    async def load_available_batteries(self):
        """Load available defense batteries from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT i.id, i.callsign, i.altitude_m, pt.max_range_m, pt.max_altitude_m, 
                       pt.accuracy_percent, pt.reload_time_sec, i.ammo_count, i.status
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'counter_defense' AND i.status = 'active'
            """)
            
            print(f"DEBUG: Found {len(rows)} counter defense batteries in database")
            
            for row in rows:
                # Parse geometry - convert WKB to WKT first
                geom_wkt = await conn.fetchval(
                    "SELECT ST_AsText(geom) FROM installation WHERE callsign = $1",
                    row['callsign']
                )
                
                # Parse WKT format: POINT(lon lat)
                geom_parts = geom_wkt.replace('POINT(', '').replace(')', '').split(' ')
                lon = float(geom_parts[0])
                lat = float(geom_parts[1])
                
                battery = BatteryCapability(
                    battery_id=row['id'],
                    callsign=row['callsign'],
                    position=(lat, lon, row['altitude_m']),
                    max_range=float(row['max_range_m']),
                    max_altitude=float(row['max_altitude_m']),
                    accuracy=float(row['accuracy_percent']) / 100.0,
                    reload_time=float(row['reload_time_sec']),
                    ammo_count=row['ammo_count'],
                    status=row['status'],
                    time_to_ready=0.0
                )
                
                self.available_batteries[row['callsign']] = battery
                print(f"DEBUG: Loaded battery {battery.callsign} at {battery.position}, range: {battery.max_range}m, altitude: {battery.max_altitude}m, ammo: {battery.ammo_count}")
    
    async def handle_radar_detection(self, msg):
        """Handle radar detection events"""
        try:
            data = json.loads(msg.data.decode())
            radar_callsign = data['radar_callsign']
            missile_id = data['missile_id']
            position = data['position']
            
            # Create or update threat assessment
            await self.update_threat_assessment(missile_id, position, radar_callsign)
            
        except Exception as e:
            print(f"Error handling radar detection: {e}")
    
    async def handle_missile_position(self, msg):
        """Handle missile position updates"""
        try:
            data = json.loads(msg.data.decode())
            missile_id = data['id']
            position = data['position']
            velocity = data['velocity']
            missile_type = data.get('missile_type', 'attack')
            
            print(f"DEBUG: Received missile position for {missile_id} at {position}, type: {missile_type}")
            
            if missile_type == 'attack':
                await self.update_threat_assessment(missile_id, position, None, velocity)
            
        except Exception as e:
            print(f"Error handling missile position: {e}")
    
    async def handle_engagement_result(self, msg):
        """Handle engagement result notifications"""
        try:
            data = json.loads(msg.data.decode())
            target_missile_id = data['target_missile_id']
            defense_missile_id = data['defense_missile_id']
            success = data['success']
            
            if success:
                # Remove threat if successfully intercepted
                if target_missile_id in self.active_threats:
                    del self.active_threats[target_missile_id]
                if target_missile_id in self.engagement_attempts:
                    del self.engagement_attempts[target_missile_id]
                print(f"Successfully intercepted missile {target_missile_id}")
            else:
                # Handle failed engagement
                await self.handle_failed_engagement(target_missile_id, data.get('failure_reason', 'unknown'))
            
        except Exception as e:
            print(f"Error handling engagement result: {e}")
    
    async def update_threat_assessment(self, missile_id: str, position: Dict, 
                                     detection_source: Optional[str] = None, 
                                     velocity: Optional[Dict] = None):
        """Update threat assessment for a missile"""
        with COMMAND_DECISIONS.time():
            print(f"DEBUG: update_threat_assessment called for missile {missile_id}")
            
            # Get missile details from database
            async with self.db_pool.acquire() as conn:
                missile = await conn.fetchrow("""
                    SELECT am.callsign, am.target_geom, am.target_altitude_m, pt.blast_radius_m
                    FROM active_missile am
                    JOIN platform_type pt ON am.platform_type_id = pt.id
                    WHERE am.id = $1 AND am.missile_type = 'attack'
                """, missile_id)
                
                if not missile:
                    print(f"DEBUG: Missile {missile_id} not found in database")
                    # Check if missile exists at all
                    all_missiles = await conn.fetch("SELECT id, callsign, missile_type FROM active_missile LIMIT 5")
                    print(f"DEBUG: Sample missiles in database: {[dict(m) for m in all_missiles]}")
                    return
                
                print(f"DEBUG: Found missile {missile_id} in database: {dict(missile)}")
            
            # Calculate predicted impact point and time
            current_pos = (position['y'], position['x'], position['z'])  # lat, lon, alt
            
            if velocity:
                predicted_impact = self.predict_impact_point(current_pos, velocity)
                time_to_impact = self.calculate_time_to_impact(current_pos, velocity, predicted_impact)
            else:
                predicted_impact = self.predict_ballistic_impact(current_pos)
                time_to_impact = self.estimate_time_to_impact(current_pos, predicted_impact)
            
            # Assess threat level
            threat_level = self.assess_threat_level(predicted_impact, missile['blast_radius_m'], time_to_impact)
            print(f"DEBUG: Missile {missile_id} threat level: {threat_level}, time_to_impact: {time_to_impact}s, position: {current_pos}")
            
            # Update or create threat assessment
            if missile_id in self.active_threats:
                threat = self.active_threats[missile_id]
                threat.current_position = current_pos
                if velocity:
                    threat.current_velocity = (velocity['x'], velocity['y'], velocity['z'])
                threat.predicted_impact_point = predicted_impact
                threat.time_to_impact = time_to_impact
                threat.threat_level = threat_level
                if detection_source:
                    threat.detection_sources.append(detection_source)
            else:
                detection_sources = [detection_source] if detection_source else []
                self.active_threats[missile_id] = ThreatAssessment(
                    missile_id=missile_id,
                    missile_callsign=missile['callsign'],
                    current_position=current_pos,
                    current_velocity=(velocity['x'], velocity['y'], velocity['z']) if velocity else (0, 0, 0),
                    predicted_impact_point=predicted_impact,
                    time_to_impact=time_to_impact,
                    threat_level=threat_level,
                    confidence=0.85,  # Default confidence
                    detection_sources=detection_sources
                )
            
            THREAT_ASSESSMENTS.inc()
            
            # Consider engagement for high-priority threats
            if threat_level in ['high', 'critical']:
                print(f"DEBUG: Calling consider_engagement for missile {missile_id} with threat level {threat_level}")
                await self.consider_engagement(missile_id)
            else:
                print(f"DEBUG: NOT calling consider_engagement for missile {missile_id} with threat level {threat_level}")
    
    def predict_impact_point(self, current_pos: Tuple[float, float, float], 
                           velocity: Dict) -> Tuple[float, float, float]:
        """Predict impact point based on current position and velocity"""
        # Simplified ballistic trajectory prediction
        lat, lon, alt = current_pos
        vx, vy, vz = velocity['x'], velocity['y'], velocity['z']
        
        # Time to impact (simplified)
        time_to_impact = alt / abs(vz) if vz != 0 else 100
        
        # Predicted impact point
        impact_lat = lat + (vy * time_to_impact) / 111000  # Approximate conversion
        impact_lon = lon + (vx * time_to_impact) / (111000 * math.cos(math.radians(lat)))
        impact_alt = 0
        
        return (impact_lat, impact_lon, impact_alt)
    
    def predict_ballistic_impact(self, current_pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Predict ballistic impact point"""
        # Simplified ballistic trajectory
        return (current_pos[0], current_pos[1], 0)
    
    def calculate_time_to_impact(self, current_pos: Tuple[float, float, float], 
                               velocity: Dict, impact_point: Tuple[float, float, float]) -> float:
        """Calculate time to impact"""
        # Simplified calculation
        distance = math.sqrt(
            (impact_point[0] - current_pos[0])**2 + 
            (impact_point[1] - current_pos[1])**2 + 
            (impact_point[2] - current_pos[2])**2
        )
        speed = math.sqrt(velocity['x']**2 + velocity['y']**2 + velocity['z']**2)
        return distance / speed if speed > 0 else 100
    
    def estimate_time_to_impact(self, current_pos: Tuple[float, float, float], 
                              target_pos: Tuple[float, float, float]) -> float:
        """Estimate time to impact without velocity data"""
        # More realistic estimation based on altitude and distance
        lat, lon, alt = current_pos
        target_lat, target_lon, target_alt = target_pos
        
        # Calculate horizontal distance
        lat_diff = target_lat - lat
        lon_diff = target_lon - lon
        horizontal_distance = math.sqrt(lat_diff**2 + lon_diff**2) * 111000  # meters
        
        # Estimate time based on typical missile speed and altitude
        if alt > 1000:  # High altitude
            return 30.0  # 30 seconds
        elif alt > 100:  # Medium altitude
            return 60.0  # 1 minute
        else:  # Low altitude
            return 120.0  # 2 minutes
    
    def assess_threat_level(self, impact_point: Tuple[float, float, float], 
                          blast_radius: float, time_to_impact: float) -> str:
        """Assess threat level based on impact point and time"""
        # More aggressive threat assessment for testing
        if time_to_impact < 60:  # 1 minute
            return 'critical'
        elif time_to_impact < 180:  # 3 minutes
            return 'high'
        elif time_to_impact < 600:  # 10 minutes
            return 'medium'
        else:
            return 'low'
    
    async def consider_engagement(self, missile_id: str):
        """Consider engaging a threat"""
        if missile_id not in self.active_threats:
            return
        
        threat = self.active_threats[missile_id]
        
        # Check if we've already tried too many times
        if missile_id in self.engagement_attempts:
            if len(self.engagement_attempts[missile_id]) >= self.max_retries:
                print(f"Maximum engagement attempts reached for missile {missile_id}")
                return
        
        # Find best battery for engagement
        solution = await self.find_best_intercept_solution(threat)
        
        if solution:
            await self.order_engagement(missile_id, solution)
        else:
            print(f"No suitable battery found for missile {missile_id}")
    
    async def find_best_intercept_solution(self, threat: ThreatAssessment) -> Optional[InterceptSolution]:
        """Find the best battery and intercept solution for a threat"""
        best_solution = None
        best_score = 0
        
        print(f"DEBUG: Looking for battery to intercept missile at position {threat.current_position}")
        print(f"DEBUG: Available batteries: {list(self.available_batteries.keys())}")
        
        for battery_callsign, battery in self.available_batteries.items():
            print(f"DEBUG: Checking battery {battery_callsign} - status: {battery.status}, ammo: {battery.ammo_count}")
            
            if battery.status != 'active' or battery.ammo_count <= 0:
                print(f"DEBUG: Battery {battery_callsign} not available - status: {battery.status}, ammo: {battery.ammo_count}")
                continue
            
            print(f"DEBUG: About to call calculate_intercept_solution for battery {battery_callsign}")
            solution = self.calculate_intercept_solution(threat, battery)
            print(f"DEBUG: calculate_intercept_solution returned: {solution}")
            
            if solution:
                # Score based on probability of success and time to launch
                score = solution.probability_of_success / (solution.time_to_launch + 1)
                print(f"DEBUG: Battery {battery_callsign} can intercept with score {score}")
                if score > best_score:
                    best_score = score
                    best_solution = solution
            else:
                print(f"DEBUG: Battery {battery_callsign} cannot intercept - distance or altitude issue")
        
        return best_solution
    
    def calculate_intercept_solution(self, threat: ThreatAssessment, 
                                   battery: BatteryCapability) -> Optional[InterceptSolution]:
        """Calculate intercept solution for a battery"""
        try:
            print(f"DEBUG: calculate_intercept_solution called for battery {battery.callsign}")
            
            # Calculate distance to threat
            battery_pos = battery.position
            threat_pos = threat.current_position
            
            print(f"DEBUG: Battery {battery.callsign} at {battery_pos}, threat at {threat_pos}")
            
            distance = math.sqrt(
                (float(battery_pos[0]) - threat_pos[0])**2 + 
                (float(battery_pos[1]) - threat_pos[1])**2 + 
                (float(battery_pos[2]) - threat_pos[2])**2
            )
            
            print(f"DEBUG: Distance: {distance}m, battery max_range: {battery.max_range}m")
            print(f"DEBUG: Threat altitude: {threat_pos[2]}m, battery max_altitude: {battery.max_altitude}m")
            
            # Only engage missiles that are airborne (above surface)
            if threat_pos[2] <= 0:
                print(f"DEBUG: Threat is underwater (z={threat_pos[2]}), skipping")
                return None
            
            # Check if battery can reach the threat
            if distance > battery.max_range:
                print(f"DEBUG: Distance {distance}m exceeds battery range {battery.max_range}m")
                return None
                
            if threat_pos[2] > battery.max_altitude:
                print(f"DEBUG: Threat altitude {threat_pos[2]}m exceeds battery max altitude {battery.max_altitude}m")
                return None
            
            print(f"DEBUG: Battery {battery.callsign} CAN intercept!")
            
            # Calculate intercept point (simplified)
            intercept_lat = (float(battery_pos[0]) + threat_pos[0]) / 2
            intercept_lon = (float(battery_pos[1]) + threat_pos[1]) / 2
            intercept_alt = (float(battery_pos[2]) + threat_pos[2]) / 2
            
            # Calculate intercept time
            intercept_time = threat.time_to_impact * 0.5  # Simplified
            
            # Calculate probability of success
            probability = battery.accuracy * (1 - distance / battery.max_range)
            
            # Calculate time to launch
            time_to_launch = battery.time_to_ready
            
            return InterceptSolution(
                battery_callsign=battery.callsign,
                intercept_point=(intercept_lat, intercept_lon, intercept_alt),
                intercept_time=intercept_time,
                intercept_altitude=intercept_alt,
                probability_of_success=probability,
                time_to_launch=time_to_launch
            )
        except Exception as e:
            print(f"DEBUG: Error in calculate_intercept_solution: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def order_engagement(self, missile_id: str, solution: InterceptSolution):
        """Order a battery to engage a threat"""
        # Send engagement order to battery via NATS
        engagement_order = {
            "type": "engagement_order",
            "target_missile_id": missile_id,
            "battery_callsign": solution.battery_callsign,
            "intercept_point": solution.intercept_point,
            "intercept_time": solution.intercept_time,
            "probability_of_success": solution.probability_of_success,
            "timestamp": time.time()
        }
        
        await self.nats_client.publish(
            f"battery.{solution.battery_callsign}.engage",
            json.dumps(engagement_order).encode()
        )
        
        # Record engagement attempt
        if missile_id not in self.engagement_attempts:
            self.engagement_attempts[missile_id] = []
        
        self.engagement_attempts[missile_id].append({
            "battery": solution.battery_callsign,
            "timestamp": time.time(),
            "probability": solution.probability_of_success
        })
        
        ENGAGEMENT_ORDERS.inc()
        BATTERY_SELECTIONS.inc()
        print(f"Ordered engagement of missile {missile_id} by battery {solution.battery_callsign}")
    
    async def handle_failed_engagement(self, missile_id: str, failure_reason: str):
        """Handle failed engagement"""
        print(f"Engagement failed for missile {missile_id}: {failure_reason}")
        
        # Consider retry with different battery
        if missile_id in self.active_threats:
            await self.consider_engagement(missile_id)
    
    async def run_command_center(self):
        """Main command center loop"""
        print("Starting command center...")
        
        while True:
            try:
                # Update battery status
                await self.update_battery_status()
                
                # Clean up old threats
                await self.cleanup_old_threats()
                
                # Process threats
                for missile_id in list(self.active_threats.keys()):
                    threat = self.active_threats[missile_id]
                    if threat.threat_level in ['high', 'critical']:
                        await self.consider_engagement(missile_id)
                
                await asyncio.sleep(1)  # 1 second loop
                
            except Exception as e:
                print(f"Error in command center loop: {e}")
                await asyncio.sleep(1)
    
    async def update_battery_status(self):
        """Update battery status from database"""
        async with self.db_pool.acquire() as conn:
            batteries = await conn.fetch("""
                SELECT i.callsign, i.ammo_count, i.status
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'counter_defense'
            """)
            
            for row in batteries:
                if row['callsign'] in self.available_batteries:
                    battery = self.available_batteries[row['callsign']]
                    battery.ammo_count = row['ammo_count']
                    battery.status = row['status']
    
    async def cleanup_old_threats(self):
        """Clean up old threats"""
        current_time = time.time()
        threats_to_remove = []
        
        for missile_id, threat in self.active_threats.items():
            # Remove threats that are too old or have been handled
            if current_time - threat.time_to_impact > 300:  # 5 minutes
                threats_to_remove.append(missile_id)
        
        for missile_id in threats_to_remove:
            del self.active_threats[missile_id]
            if missile_id in self.engagement_attempts:
                del self.engagement_attempts[missile_id] 