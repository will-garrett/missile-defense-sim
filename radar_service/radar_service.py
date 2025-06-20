import asyncio
import json
import math
import os
import time
import uuid
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import asyncpg
import nats
from nats.aio.client import Client as NATS
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import numpy as np

# Prometheus metrics
start_http_server(8000)
DETECTIONS = Counter("radar_detections_total", "Total radar detections", ["radar_callsign"])
SCAN_CYCLES = Counter("radar_scan_cycles_total", "Total radar scan cycles")
ACTIVE_TRACKS = Gauge("active_tracks", "Number of active tracks")
RADAR_INSTALLATIONS = Gauge("radar_installations", "Number of active radar installations")
DETECTION_LATENCY = Histogram("detection_latency_seconds", "Time from missile launch to detection")

@dataclass
class RadarCapability:
    detection_range_m: float
    sweep_rate_deg_per_sec: float
    max_altitude_m: float
    accuracy_m: float
    update_interval_ms: int
    signal_strength_db: float
    false_alarm_rate: float

@dataclass
class RadarInstallation:
    id: int
    callsign: str
    position: Tuple[float, float, float]  # lat, lon, alt
    capability: RadarCapability
    status: str
    last_scan: float
    active_tracks: Set[str]
    detection_history: List[Dict]

@dataclass
class Track:
    missile_id: str
    missile_callsign: str
    position: Dict[str, float]
    velocity: Dict[str, float]
    first_detection: float
    last_detection: float
    detection_count: int
    confidence: float
    detecting_radars: Set[str]

class RadarService:
    def __init__(self):
        self.db_pool = None
        self.nats_client = None
        self.radar_installations: Dict[str, RadarInstallation] = {}
        self.active_tracks: Dict[str, Track] = {}
        self.scan_interval = 0.1  # 100ms base scan interval
        self.max_workers = 10  # Thread pool for parallel radar processing
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
    async def initialize(self):
        """Initialize database connection and NATS"""
        # Database
        self.db_pool = await asyncpg.create_pool(os.getenv("DB_DSN"))
        
        # NATS
        self.nats_client = NATS()
        await self.nats_client.connect("nats://nats:4222")
        
        # Subscribe to missile position updates
        await self.nats_client.subscribe("missile.position", cb=self.handle_missile_position)
        
        # Load all radar installations
        await self.load_radar_installations()
        
        print(f"Radar service initialized with {len(self.radar_installations)} installations")
    
    async def load_radar_installations(self):
        """Load all radar installations from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT i.id, i.callsign, i.geom, i.altitude_m, i.status,
                       pt.detection_range_m, pt.sweep_rate_deg_per_sec, pt.max_altitude_m,
                       pt.accuracy_percent
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'detection_system' AND i.status = 'active'
                ORDER BY i.callsign
            """)
            
            for row in rows:
                # Parse geometry
                geom_str = row['geom']
                lon = float(geom_str.split('(')[1].split(' ')[0])
                lat = float(geom_str.split('(')[1].split(' ')[1])
                
                # Create radar capability
                capability = RadarCapability(
                    detection_range_m=row['detection_range_m'],
                    sweep_rate_deg_per_sec=row['sweep_rate_deg_per_sec'],
                    max_altitude_m=row['max_altitude_m'],
                    accuracy_m=100.0,  # Default accuracy
                    update_interval_ms=self._calculate_update_interval(row['sweep_rate_deg_per_sec']),
                    signal_strength_db=-50,  # Default signal strength
                    false_alarm_rate=0.01  # 1% false alarm rate
                )
                
                # Create radar installation
                installation = RadarInstallation(
                    id=row['id'],
                    callsign=row['callsign'],
                    position=(lat, lon, row['altitude_m']),
                    capability=capability,
                    status=row['status'],
                    last_scan=0,
                    active_tracks=set(),
                    detection_history=[]
                )
                
                self.radar_installations[row['callsign']] = installation
            
            RADAR_INSTALLATIONS.set(len(self.radar_installations))
            print(f"Loaded {len(self.radar_installations)} radar installations")
    
    def _calculate_update_interval(self, sweep_rate: float) -> int:
        """Calculate update interval based on sweep rate"""
        # Higher sweep rate = faster updates
        # Base interval: 1000ms for 60°/s sweep rate
        base_interval = 1000
        base_sweep_rate = 60.0
        
        if sweep_rate <= 0:
            return 1000
        
        interval = int(base_interval * (base_sweep_rate / sweep_rate))
        return max(100, min(5000, interval))  # Clamp between 100ms and 5s
    
    async def handle_missile_position(self, msg):
        """Handle missile position updates from simulation service"""
        try:
            data = json.loads(msg.data.decode())
            missile_id = data['id']
            missile_callsign = data['callsign']
            position = data['position']
            velocity = data['velocity']
            missile_type = data.get('missile_type', 'attack')
            timestamp = data.get('timestamp', time.time())
            
            if missile_type == 'attack':
                # Update track if exists, create if new
                if missile_id in self.active_tracks:
                    track = self.active_tracks[missile_id]
                    track.position = position
                    track.velocity = velocity
                    track.last_detection = timestamp
                else:
                    track = Track(
                        missile_id=missile_id,
                        missile_callsign=missile_callsign,
                        position=position,
                        velocity=velocity,
                        first_detection=timestamp,
                        last_detection=timestamp,
                        detection_count=0,
                        confidence=0.0,
                        detecting_radars=set()
                    )
                    self.active_tracks[missile_id] = track
                
                # Check all radar installations for detection
                await self.check_all_radars_for_detection(missile_id, track, timestamp)
            
        except Exception as e:
            print(f"Error handling missile position: {e}")
    
    async def check_all_radars_for_detection(self, missile_id: str, track: Track, timestamp: float):
        """Check all radar installations for missile detection"""
        # Use thread pool for parallel radar processing
        loop = asyncio.get_event_loop()
        
        # Create tasks for each radar installation
        tasks = []
        for callsign, installation in self.radar_installations.items():
            # Check if it's time for this radar to scan
            if timestamp - installation.last_scan >= (installation.capability.update_interval_ms / 1000.0):
                task = loop.run_in_executor(
                    self.executor,
                    self._check_single_radar,
                    installation,
                    missile_id,
                    track,
                    timestamp
                )
                tasks.append(task)
        
        # Wait for all radar checks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process detection results
            for result in results:
                if isinstance(result, dict) and result.get('detected'):
                    await self.process_detection(result)
    
    def _check_single_radar(self, installation: RadarInstallation, missile_id: str, 
                           track: Track, timestamp: float) -> Optional[Dict]:
        """Check if a single radar installation detects the missile"""
        try:
            # Calculate distance to missile
            distance = self._calculate_distance(installation.position, track.position)
            
            # Check if missile is within range
            if distance > installation.capability.detection_range_m:
                return None
            
            # Check altitude limits
            if track.position['z'] > installation.capability.max_altitude_m:
                return None
            
            # Calculate detection probability
            detection_prob = self._calculate_detection_probability(
                installation, distance, track.position
            )
            
            # Simulate detection based on probability
            if self._simulate_detection(detection_prob):
                return {
                    'detected': True,
                    'radar_callsign': installation.callsign,
                    'missile_id': missile_id,
                    'missile_callsign': track.missile_callsign,
                    'position': track.position,
                    'velocity': track.velocity,
                    'detection_probability': detection_prob,
                    'distance': distance,
                    'timestamp': timestamp
                }
            
            return None
            
        except Exception as e:
            print(f"Error in radar check for {installation.callsign}: {e}")
            return None
    
    def _calculate_distance(self, radar_pos: Tuple[float, float, float], 
                          missile_pos: Dict[str, float]) -> float:
        """Calculate 3D distance between radar and missile"""
        lat_diff = radar_pos[0] - missile_pos['y']  # lat
        lon_diff = radar_pos[1] - missile_pos['x']  # lon
        alt_diff = radar_pos[2] - missile_pos['z']  # alt
        
        # Convert lat/lon to approximate meters
        lat_m = lat_diff * 111000  # ~111km per degree
        lon_m = lon_diff * 111000 * math.cos(math.radians(radar_pos[0]))
        
        return math.sqrt(lat_m**2 + lon_m**2 + alt_diff**2)
    
    def _calculate_detection_probability(self, installation: RadarInstallation, 
                                       distance: float, missile_pos: Dict[str, float]) -> float:
        """Calculate probability of detecting a missile"""
        # Base detection probability decreases with distance
        range_factor = 1.0 - (distance / installation.capability.detection_range_m)
        
        # Altitude factor (easier to detect at higher altitudes)
        altitude_factor = min(1.0, missile_pos['z'] / 10000)  # Normalize to 10km
        
        # RCS (Radar Cross Section) factor (simplified)
        rcs_factor = 0.8  # Typical missile RCS
        
        # Signal strength factor
        signal_factor = 1.0 + (installation.capability.signal_strength_db / 100.0)
        
        # Final probability
        probability = range_factor * altitude_factor * rcs_factor * signal_factor
        
        # Add some randomness for realistic simulation
        probability *= (0.8 + 0.4 * np.random.random())
        
        return max(0.05, min(0.95, probability))  # Clamp between 5% and 95%
    
    def _simulate_detection(self, probability: float) -> bool:
        """Simulate detection based on probability"""
        return np.random.random() < probability
    
    async def process_detection(self, detection: Dict):
        """Process a missile detection"""
        radar_callsign = detection['radar_callsign']
        missile_id = detection['missile_id']
        current_time = detection['timestamp']
        
        # Update track
        if missile_id in self.active_tracks:
            track = self.active_tracks[missile_id]
            track.detection_count += 1
            track.detecting_radars.add(radar_callsign)
            track.confidence = min(0.95, track.confidence + 0.1)
            
            # Update radar installation
            if radar_callsign in self.radar_installations:
                radar = self.radar_installations[radar_callsign]
                radar.active_tracks.add(missile_id)
                radar.last_scan = current_time
                
                # Add to detection history (keep last 100)
                radar.detection_history.append({
                    'missile_id': missile_id,
                    'timestamp': current_time,
                    'probability': detection['detection_probability']
                })
                radar.detection_history = radar.detection_history[-100:]
        
        # Record detection in database
        await self.record_detection(detection)
        
        # Publish detection event via NATS
        await self.publish_detection(detection)
        
        # Update metrics
        DETECTIONS.labels(radar_callsign=radar_callsign).inc()
        
        # Calculate detection latency
        if missile_id in self.active_tracks:
            track = self.active_tracks[missile_id]
            latency = current_time - track.first_detection
            DETECTION_LATENCY.observe(latency)
        
        print(f"Radar {radar_callsign} detected missile {detection['missile_callsign']} "
              f"at distance {detection['distance']:.0f}m (confidence: {detection['detection_probability']:.2f})")
    
    async def record_detection(self, detection: Dict):
        """Record detection in database"""
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
            """, detection['radar_callsign'], detection['missile_id'],
                 detection['position']['x'], detection['position']['y'],
                 detection['position']['z'], -50,  # Signal strength
                 int(detection['detection_probability'] * 100))
    
    async def publish_detection(self, detection: Dict):
        """Publish detection event via NATS"""
        detection_event = {
            "radar_callsign": detection['radar_callsign'],
            "missile_id": detection['missile_id'],
            "missile_callsign": detection['missile_callsign'],
            "position": detection['position'],
            "velocity": detection['velocity'],
            "detection_probability": detection['detection_probability'],
            "distance": detection['distance'],
            "timestamp": detection['timestamp']
        }
        
        await self.nats_client.publish(
            "radar.detection",
            json.dumps(detection_event).encode()
        )
    
    async def cleanup_old_tracks(self):
        """Remove tracks that haven't been updated recently"""
        current_time = time.time()
        tracks_to_remove = []
        
        for missile_id, track in self.active_tracks.items():
            # Remove track if not detected for 60 seconds
            if current_time - track.last_detection > 60:
                tracks_to_remove.append(missile_id)
        
        for missile_id in tracks_to_remove:
            # Remove from all radar installations
            for radar in self.radar_installations.values():
                radar.active_tracks.discard(missile_id)
            
            del self.active_tracks[missile_id]
            print(f"Removed stale track for missile {missile_id}")
        
        ACTIVE_TRACKS.set(len(self.active_tracks))
    
    async def update_radar_status(self):
        """Update radar installation status from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT i.callsign, i.status
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE pt.category = 'detection_system'
            """)
            
            for row in rows:
                if row['callsign'] in self.radar_installations:
                    self.radar_installations[row['callsign']].status = row['status']
    
    async def get_radar_statistics(self) -> Dict:
        """Get radar service statistics"""
        stats = {
            'total_installations': len(self.radar_installations),
            'active_installations': sum(1 for r in self.radar_installations.values() if r.status == 'active'),
            'total_tracks': len(self.active_tracks),
            'detections_last_hour': 0,
            'avg_detection_latency': 0
        }
        
        # Calculate detections in last hour
        current_time = time.time()
        for radar in self.radar_installations.values():
            recent_detections = [
                d for d in radar.detection_history 
                if current_time - d['timestamp'] < 3600
            ]
            stats['detections_last_hour'] += len(recent_detections)
        
        return stats
    
    async def run_radar_service(self):
        """Main radar service loop"""
        print("Radar service operational")
        
        while True:
            try:
                # Periodic tasks
                await self.cleanup_old_tracks()
                await self.update_radar_status()
                
                # Update metrics
                SCAN_CYCLES.inc()
                
                # Wait before next cycle
                await asyncio.sleep(self.scan_interval)
                
            except Exception as e:
                print(f"Error in radar service loop: {e}")
                await asyncio.sleep(1.0)

async def main():
    """Main entry point"""
    radar_service = RadarService()
    await radar_service.initialize()
    
    try:
        await radar_service.run_radar_service()
    except KeyboardInterrupt:
        print("Radar service shutting down...")
    finally:
        if radar_service.db_pool:
            await radar_service.db_pool.close()
        if radar_service.nats_client:
            await radar_service.nats_client.close()
        radar_service.executor.shutdown(wait=True)

if __name__ == "__main__":
    asyncio.run(main()) 