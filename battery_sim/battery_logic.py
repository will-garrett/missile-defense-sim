"""
Core logic for the Battery Simulation Service
Handles engagement, launch, and status logic
"""
import time
import math
from typing import Dict, Optional, List
from dataclasses import dataclass

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

class BatteryLogic:
    def __init__(self, callsign: str, battery_capability: BatteryCapability, ammo_count: int):
        self.callsign = callsign
        self.battery_capability = battery_capability
        self.status = "ready"  # ready, preparing, launching, reloading
        self.ammo_count = ammo_count
        self.last_launch_time = 0
        self.pending_engagements: List[EngagementOrder] = []
        self.current_engagement: Optional[EngagementOrder] = None

    def can_engage(self) -> bool:
        if self.status != "ready":
            return False
        if self.ammo_count <= 0:
            return False
        current_time = time.time()
        if current_time - self.last_launch_time < self.battery_capability.reload_time_sec:
            return False
        return True

    def calculate_distance(self, pos1: Dict[str, float], pos2: Dict[str, float]) -> float:
        lat_diff = (pos1["lat"] - pos2["lat"]) * 111000
        lon_diff = (pos1["lon"] - pos2["lon"]) * 111000 * math.cos(math.radians(pos1["lat"]))
        alt_diff = pos1["alt"] - pos2["alt"]
        return math.sqrt(lat_diff**2 + lon_diff**2 + alt_diff**2)

    def prepare_for_engagement(self, order: EngagementOrder, battery_pos: Dict[str, float]) -> bool:
        if not self.can_engage():
            return False
        distance = self.calculate_distance(battery_pos, order.intercept_point)
        if distance > self.battery_capability.max_range_m:
            return False
        if order.intercept_altitude > self.battery_capability.max_altitude_m:
            return False
        self.status = "preparing"
        return True

    def launch(self, order: EngagementOrder):
        self.status = "launching"
        self.last_launch_time = time.time()
        self.ammo_count -= 1
        self.current_engagement = order
        return True

    def reload(self):
        self.status = "reloading"
        # Simulate reload time externally
        return True

    def set_ready(self):
        self.status = "ready"
        self.current_engagement = None
        return True 