import asyncio
import json
import math
import os
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import asyncpg
import nats
from nats.aio.client import Client as NATS
import zmq.asyncio
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import numpy as np

# Prometheus metrics
start_http_server(8000)
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

class CommandCenter:
    def __init__(self):
        self.db_pool = None
        self.nats_client = None
        self.zmq_context = zmq.asyncio.Context()
        self.zmq_pub = self.zmq_context.socket(zmq.PUB)
        
        self.active_threats: Dict[str, ThreatAssessment] = {}
        self.available_batteries: Dict[str, BatteryCapability] = {}
        self.engagement_attempts: Dict[str, List[Dict]] = {}  # missile_id -> attempts
        self.max_retries = 3
        
        # Subscribe to relevant topics
        self.nats_subscriptions = []
        
    async def initialize(self):
        """Initialize database connection, NATS, and ZMQ"""
        # Database
        self.db_pool = await asyncpg.create_pool(os.getenv("DB_DSN"))
        
        # NATS
        self.nats_client = NATS()
        await self.nats_client.connect("nats://nats:4222")
        
        # ZMQ
        self.zmq_pub.bind("tcp://0.0.0.0:5558")  # Command center channel
        
        # Subscribe to radar detections
        await self.nats_client.subscribe("radar.detection", cb=self.handle_radar_detection)
        
        # Subscribe to missile position updates
        await self.nats_client.subscribe("missile.position", cb=self.handle_missile_position)
        
        # Subscribe to engagement results
        await self.nats_client.subscribe("engagement.result", cb=self.handle_engagement_result)
        
        # Load available batteries
        await self.load_available_batteries()
        
        print("Command center initialized")
    
    async def load_available_batteries(self):
        """Load all available counter-defense batteries"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT i.id, i.callsign, i.geom, i.altitude_m, i.ammo_count, i.status,
                       pt.max_range_m, pt.max_altitude_m, pt.accuracy_percent, pt.reload_time_sec
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'counter_defense' AND i.status = 'active'
            """)
            
            for row in rows:
                # Parse geometry
                geom_str = row['geom']
                lon = float(geom_str.split('(')[1].split(' ')[0])
                lat = float(geom_str.split('(')[1].split(' ')[1])
                
                self.available_batteries[row['callsign']] = BatteryCapability(
                    battery_id=row['id'],
                    callsign=row['callsign'],
                    position=(lat, lon, row['altitude_m']),
                    max_range=row['max_range_m'],
                    max_altitude=row['max_altitude_m'],
                    accuracy=row['accuracy_percent'] / 100.0,
                    reload_time=row['reload_time_sec'],
                    ammo_count=row['ammo_count'],
                    status=row['status'],
                    time_to_ready=0.0
                )
    
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
            # Get missile details from database
            async with self.db_pool.acquire() as conn:
                missile = await conn.fetchrow("""
                    SELECT am.callsign, am.target_geom, am.target_altitude_m, pt.blast_radius_m
                    FROM active_missile am
                    JOIN platform_type pt ON am.platform_type_id = pt.id
                    WHERE am.id = $1 AND am.missile_type = 'attack'
                """, missile_id)
                
                if not missile:
                    return
            
            # Calculate predicted impact point and time
            current_pos = (position['y'], position['x'], position['z'])  # lat, lon, alt
            
            if velocity:
                # Use velocity to predict trajectory
                predicted_impact = self.predict_impact_point(current_pos, velocity)
                time_to_impact = self.calculate_time_to_impact(current_pos, velocity, predicted_impact)
            else:
                # Use target coordinates if available
                target_geom = missile['target_geom']
                if target_geom:
                    target_lon = float(target_geom.split('(')[1].split(' ')[0])
                    target_lat = float(target_geom.split('(')[1].split(' ')[1])
                    predicted_impact = (target_lat, target_lon, missile['target_altitude_m'])
                    time_to_impact = self.estimate_time_to_impact(current_pos, predicted_impact)
                else:
                    # Fallback: assume ballistic trajectory
                    predicted_impact = self.predict_ballistic_impact(current_pos)
                    time_to_impact = 60.0  # Default estimate
            
            # Assess threat level
            threat_level = self.assess_threat_level(predicted_impact, missile['blast_radius_m'], time_to_impact)
            
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
                threat = ThreatAssessment(
                    missile_id=missile_id,
                    missile_callsign=missile['callsign'],
                    current_position=current_pos,
                    current_velocity=velocity or (0, 0, 0),
                    predicted_impact_point=predicted_impact,
                    time_to_impact=time_to_impact,
                    threat_level=threat_level,
                    confidence=0.8,
                    detection_sources=[detection_source] if detection_source else []
                )
                self.active_threats[missile_id] = threat
                
                # Initialize engagement attempts tracking
                self.engagement_attempts[missile_id] = []
            
            THREAT_ASSESSMENTS.inc()
            
            # Check if we need to engage this threat
            if threat_level in ['high', 'critical']:
                await self.consider_engagement(missile_id)
    
    def predict_impact_point(self, current_pos: Tuple[float, float, float], 
                           velocity: Dict) -> Tuple[float, float, float]:
        """Predict impact point based on current velocity"""
        # Simplified ballistic trajectory prediction
        lat, lon, alt = current_pos
        vx, vy, vz = velocity['x'], velocity['y'], velocity['z']
        
        # Time to reach ground (assuming constant acceleration due to gravity)
        g = 9.81
        time_to_ground = (-vz - math.sqrt(vz**2 + 2*g*alt)) / g
        
        # Predict horizontal position at impact
        impact_lat = lat + (vy * time_to_ground) / 111000  # Approximate m/degree
        impact_lon = lon + (vx * time_to_ground) / (111000 * math.cos(math.radians(lat)))
        
        return (impact_lat, impact_lon, 0)
    
    def predict_ballistic_impact(self, current_pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Predict impact point for ballistic trajectory"""
        # Simplified: assume straight down trajectory
        return (current_pos[0], current_pos[1], 0)
    
    def calculate_time_to_impact(self, current_pos: Tuple[float, float, float], 
                               velocity: Dict, impact_point: Tuple[float, float, float]) -> float:
        """Calculate time to impact"""
        # Distance to impact
        distance = math.sqrt(
            (current_pos[0] - impact_point[0])**2 + 
            (current_pos[1] - impact_point[1])**2 + 
            (current_pos[2] - impact_point[2])**2
        )
        
        # Average velocity
        avg_velocity = math.sqrt(velocity['x']**2 + velocity['y']**2 + velocity['z']**2)
        
        return distance / avg_velocity if avg_velocity > 0 else 60.0
    
    def estimate_time_to_impact(self, current_pos: Tuple[float, float, float], 
                              target_pos: Tuple[float, float, float]) -> float:
        """Estimate time to impact based on distance"""
        distance = math.sqrt(
            (current_pos[0] - target_pos[0])**2 + 
            (current_pos[1] - target_pos[1])**2 + 
            (current_pos[2] - target_pos[2])**2
        )
        
        # Assume average missile speed of 1000 m/s
        return distance / 1000.0
    
    def assess_threat_level(self, impact_point: Tuple[float, float, float], 
                          blast_radius: float, time_to_impact: float) -> str:
        """Assess threat level based on impact point and characteristics"""
        # This would include analysis of:
        # - Proximity to critical infrastructure
        # - Blast radius
        # - Time to impact
        # - Payload type
        
        # Simplified assessment
        if time_to_impact < 30:  # Less than 30 seconds
            return 'critical'
        elif time_to_impact < 120:  # Less than 2 minutes
            return 'high'
        elif time_to_impact < 300:  # Less than 5 minutes
            return 'medium'
        else:
            return 'low'
    
    async def consider_engagement(self, missile_id: str):
        """Consider engaging a threat"""
        threat = self.active_threats.get(missile_id)
        if not threat:
            return
        
        # Check if we've already tried too many times
        attempts = self.engagement_attempts.get(missile_id, [])
        if len(attempts) >= self.max_retries:
            print(f"Maximum engagement attempts reached for missile {missile_id}")
            return
        
        # Find best battery for engagement
        intercept_solution = await self.find_best_intercept_solution(threat)
        
        if intercept_solution and intercept_solution.probability_of_success > 0.3:
            await self.order_engagement(missile_id, intercept_solution)
        else:
            print(f"No suitable intercept solution found for missile {missile_id}")
    
    async def find_best_intercept_solution(self, threat: ThreatAssessment) -> Optional[InterceptSolution]:
        """Find the best battery and intercept solution for a threat"""
        best_solution = None
        best_score = 0
        
        for battery_callsign, battery in self.available_batteries.items():
            # Check if battery is ready and has ammo
            if battery.ammo_count <= 0 or battery.status != 'active':
                continue
            
            # Calculate intercept solution
            solution = self.calculate_intercept_solution(threat, battery)
            
            if solution:
                # Score the solution based on probability and time
                score = solution.probability_of_success * (1.0 / (1.0 + solution.time_to_launch))
                
                if score > best_score:
                    best_score = score
                    best_solution = solution
        
        if best_solution:
            BATTERY_SELECTIONS.inc()
            INTERCEPT_PREDICTIONS.inc()
        
        return best_solution
    
    def calculate_intercept_solution(self, threat: ThreatAssessment, 
                                   battery: BatteryCapability) -> Optional[InterceptSolution]:
        """Calculate intercept solution for a battery"""
        # Calculate distance from battery to threat trajectory
        battery_pos = battery.position
        threat_pos = threat.current_position
        
        # Simplified intercept calculation
        # In reality, this would involve complex trajectory analysis
        
        # Calculate intercept point (simplified)
        intercept_lat = (battery_pos[0] + threat_pos[0]) / 2
        intercept_lon = (battery_pos[1] + threat_pos[1]) / 2
        intercept_alt = max(battery_pos[2] + 1000, threat_pos[2] - 5000)  # Mid-altitude intercept
        
        intercept_point = (intercept_lat, intercept_lon, intercept_alt)
        
        # Calculate distance to intercept point
        distance_to_intercept = math.sqrt(
            (battery_pos[0] - intercept_lat)**2 + 
            (battery_pos[1] - intercept_lon)**2 + 
            (battery_pos[2] - intercept_alt)**2
        )
        
        # Check if intercept is within battery range
        if distance_to_intercept > battery.max_range:
            return None
        
        # Calculate probability of success
        base_probability = battery.accuracy
        range_factor = 1.0 - (distance_to_intercept / battery.max_range)
        altitude_factor = 1.0 if intercept_alt <= battery.max_altitude else 0.5
        
        probability = base_probability * range_factor * altitude_factor
        
        # Calculate time to launch
        time_to_launch = battery.time_to_ready + 5.0  # 5 seconds for launch sequence
        
        return InterceptSolution(
            battery_callsign=battery.callsign,
            intercept_point=intercept_point,
            intercept_time=time.time() + time_to_launch + (distance_to_intercept / 3000),  # Assume 3000 m/s missile
            intercept_altitude=intercept_alt,
            probability_of_success=probability,
            time_to_launch=time_to_launch
        )
    
    async def order_engagement(self, missile_id: str, solution: InterceptSolution):
        """Order an engagement"""
        # Record engagement attempt
        attempt = {
            "timestamp": time.time(),
            "battery": solution.battery_callsign,
            "intercept_point": solution.intercept_point,
            "probability": solution.probability_of_success
        }
        
        self.engagement_attempts[missile_id].append(attempt)
        
        # Send engagement order to battery via NATS
        engagement_order = {
            "type": "engagement_order",
            "target_missile_id": missile_id,
            "battery_callsign": solution.battery_callsign,
            "intercept_point": solution.intercept_point,
            "intercept_altitude": solution.intercept_altitude,
            "probability_of_success": solution.probability_of_success,
            "timestamp": time.time()
        }
        
        await self.nats_client.publish(
            f"battery.{solution.battery_callsign}.engage",
            json.dumps(engagement_order).encode()
        )
        
        ENGAGEMENT_ORDERS.inc()
        print(f"Ordered engagement of missile {missile_id} by battery {solution.battery_callsign}")
    
    async def handle_failed_engagement(self, missile_id: str, failure_reason: str):
        """Handle failed engagement"""
        attempts = self.engagement_attempts.get(missile_id, [])
        if attempts:
            attempts[-1]["failure_reason"] = failure_reason
            attempts[-1]["failed"] = True
        
        print(f"Engagement failed for missile {missile_id}: {failure_reason}")
        
        # Consider retry with different battery
        if len(attempts) < self.max_retries:
            await self.consider_engagement(missile_id)
    
    async def run_command_center(self):
        """Main command center loop"""
        print("Command center operational")
        
        while True:
            try:
                # Periodic tasks
                await self.update_battery_status()
                await self.cleanup_old_threats()
                
                # Wait before next cycle
                await asyncio.sleep(1.0)
                
            except Exception as e:
                print(f"Error in command center loop: {e}")
                await asyncio.sleep(1.0)
    
    async def update_battery_status(self):
        """Update battery status from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT i.callsign, i.ammo_count, i.status
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'counter_defense'
            """)
            
            for row in rows:
                if row['callsign'] in self.available_batteries:
                    battery = self.available_batteries[row['callsign']]
                    battery.ammo_count = row['ammo_count']
                    battery.status = row['status']
    
    async def cleanup_old_threats(self):
        """Remove old threats that are no longer active"""
        current_time = time.time()
        threats_to_remove = []
        
        for missile_id, threat in self.active_threats.items():
            # Remove if missile has been inactive for too long
            if current_time - threat.time_to_impact > 300:  # 5 minutes past impact time
                threats_to_remove.append(missile_id)
        
        for missile_id in threats_to_remove:
            del self.active_threats[missile_id]
            if missile_id in self.engagement_attempts:
                del self.engagement_attempts[missile_id]

async def main():
    """Main entry point"""
    command_center = CommandCenter()
    await command_center.initialize()
    
    try:
        await command_center.run_command_center()
    except KeyboardInterrupt:
        print("Command center shutting down...")
    finally:
        if command_center.db_pool:
            await command_center.db_pool.close()
        if command_center.nats_client:
            await command_center.nats_client.close()

if __name__ == "__main__":
    asyncio.run(main())