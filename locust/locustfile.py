from locust import HttpUser, task, between, events
import random
import time
import json

class ScenarioBase:
    """Base class for missile defense scenarios"""
    
    def __init__(self, client):
        self.client = client
        self.scenario_name = "base"
    
    def launch_missile(self, platform_type, lat, lon, target_lat, target_lon, altitude=0):
        """Launch a missile with specified parameters"""
        try:
            response = self.client.post("/launch", params={
                "platform_type": platform_type,
                "lat": lat,
                "lon": lon,
                "target_lat": target_lat,
                "target_lon": target_lon,
                "altitude_m": altitude
            })
            if response.status_code == 200:
                print(f"✅ Launched {platform_type} from ({lat}, {lon}) to ({target_lat}, {target_lon})")
            else:
                print(f"❌ Failed to launch {platform_type}: {response.status_code}")
            return response
        except Exception as e:
            print(f"❌ Exception launching {platform_type}: {e}")
            return None

class DefendHawaiiScenario(ScenarioBase):
    """Chinese submarine attack on Hawaii scenario"""
    
    def __init__(self, client):
        super().__init__(client)
        self.scenario_name = "defend_hawaii"
        
        # Hawaii coordinates
        self.hawaii_lat = 21.31
        self.hawaii_lon = -157.86
        
        # Chinese submarine positions (approximate)
        self.submarine_positions = [
            (25.0, -155.0),  # North of Hawaii
            (20.0, -160.0),  # West of Hawaii
            (22.0, -152.0),  # East of Hawaii
        ]
        
        # Chinese missile types
        self.chinese_missiles = [
            "JL-2",           # Submarine-launched ballistic missile
            "DF-21D",         # Anti-ship ballistic missile
            "CJ-10",          # Land-attack cruise missile
        ]
        
        # US defense systems in Hawaii
        self.us_defenses = [
            "Aegis BMD SM-3",  # Naval defense
            "THAAD System",    # Terminal defense
            "Patriot PAC-3 MSE", # Point defense
        ]
    
    def execute_scenario(self):
        """Execute the Hawaii defense scenario"""
        print(f"🚀 Starting {self.scenario_name} scenario...")
        
        # Phase 1: Chinese submarine launches
        for i, (sub_lat, sub_lon) in enumerate(self.submarine_positions):
            missile_type = random.choice(self.chinese_missiles)
            self.launch_missile(
                platform_type=missile_type,
                lat=sub_lat,
                lon=sub_lon,
                target_lat=self.hawaii_lat,
                target_lon=self.hawaii_lon,
                altitude=-200  # Submarine depth
            )
            time.sleep(2)  # Stagger launches
        
        # Phase 2: Additional cruise missile attacks
        for _ in range(3):
            missile_type = "CJ-10"
            sub_lat, sub_lon = random.choice(self.submarine_positions)
            # Add some randomness to target coordinates
            target_lat = self.hawaii_lat + random.uniform(-0.1, 0.1)
            target_lon = self.hawaii_lon + random.uniform(-0.1, 0.1)
            
            self.launch_missile(
                platform_type=missile_type,
                lat=sub_lat,
                lon=sub_lon,
                target_lat=target_lat,
                target_lon=target_lon,
                altitude=15000  # Cruise missile altitude
            )
            time.sleep(1.5)

class IronDomeScenario(ScenarioBase):
    """Israeli Iron Dome defense scenario"""
    
    def __init__(self, client):
        super().__init__(client)
        self.scenario_name = "iron_dome"
        
        # Israel coordinates
        self.israel_lat = 32.09
        self.israel_lon = 34.78
        
        # Gaza Strip coordinates (approximate)
        self.gaza_positions = [
            (31.50, 34.45),  # Northern Gaza
            (31.45, 34.40),  # Central Gaza
            (31.40, 34.35),  # Southern Gaza
        ]
        
        # Insurgency rocket types
        self.insurgency_rockets = [
            "Qassam Rocket",    # Hamas rocket
            "Grad Rocket",      # Multiple rocket launcher
            "Fajr-5",          # Iranian-backed rocket
            "Katyusha Rocket",  # Soviet-designed rocket
        ]
        
        # Israeli defense systems
        self.israeli_defenses = [
            "Iron Dome",        # Short-range defense
            "David's Sling",    # Medium-range defense
            "Arrow 3",          # Exo-atmospheric interceptor
        ]
    
    def execute_scenario(self):
        """Execute the Iron Dome scenario"""
        print(f"🚀 Starting {self.scenario_name} scenario...")
        
        # Phase 1: Rocket barrage
        for _ in range(10):  # Multiple rocket launches
            rocket_type = random.choice(self.insurgency_rockets)
            launch_pos = random.choice(self.gaza_positions)
            
            # Add randomness to launch position
            launch_lat = launch_pos[0] + random.uniform(-0.02, 0.02)
            launch_lon = launch_pos[1] + random.uniform(-0.02, 0.02)
            
            # Target various Israeli locations
            target_lat = self.israel_lat + random.uniform(-0.1, 0.1)
            target_lon = self.israel_lon + random.uniform(-0.1, 0.1)
            
            self.launch_missile(
                platform_type=rocket_type,
                lat=launch_lat,
                lon=launch_lon,
                target_lat=target_lat,
                target_lon=target_lon,
                altitude=0
            )
            time.sleep(0.5)  # Rapid fire
        
        # Phase 2: Coordinated attack
        for i, launch_pos in enumerate(self.gaza_positions):
            rocket_type = "Fajr-5"  # More sophisticated rocket
            target_lat = self.israel_lat + (i * 0.05)  # Spread targets
            target_lon = self.israel_lon + (i * 0.05)
            
            self.launch_missile(
                platform_type=rocket_type,
                lat=launch_pos[0],
                lon=launch_pos[1],
                target_lat=target_lat,
                target_lon=target_lon,
                altitude=15000
            )
            time.sleep(1)

class WW3Scenario(ScenarioBase):
    """Full-scale WW3 scenario: US vs Russia, China, North Korea"""
    
    def __init__(self, client):
        super().__init__(client)
        self.scenario_name = "ww3"
        
        # US mainland coordinates
        self.us_mainland = {
            "east_coast": (40.71, -74.01),    # New York
            "west_coast": (34.05, -118.25),   # Los Angeles
            "central": (39.74, -104.99),      # Denver
            "southeast": (33.75, -84.39),     # Atlanta
        }
        
        # Russian launch positions
        self.russian_positions = [
            (55.75, 37.62),   # Moscow area
            (55.80, 37.90),   # Moscow area
            (55.70, 37.50),   # Moscow area
        ]
        
        # Chinese launch positions
        self.chinese_positions = [
            (39.90, 116.41),  # Beijing area
            (39.95, 116.50),  # Beijing area
            (39.85, 116.30),  # Beijing area
        ]
        
        # North Korean launch positions
        self.nk_positions = [
            (39.03, 125.75),  # Pyongyang
            (38.96, 125.68),  # Pyongyang area
        ]
        
        # Strategic missile types
        self.strategic_missiles = {
            "russia": ["RT-2PM2 Topol-M", "R-29RMU2 Layner", "Kh-101"],
            "china": ["DF-31AG", "JL-2", "CJ-10"],
            "north_korea": ["Hwasong-15", "Hwasong-12", "Pukguksong-2"],
        }
        
        # US defense systems
        self.us_defenses = [
            "Aegis BMD SM-3",    # Naval defense
            "THAAD System",      # Terminal defense
            "Patriot PAC-3 MSE", # Point defense
            "GMD System",        # Ground-based midcourse defense
            "Aegis BMD SM-6",    # Extended range defense
        ]
    
    def execute_scenario(self):
        """Execute the WW3 scenario"""
        print(f"🚀 Starting {self.scenario_name} scenario...")
        
        # Phase 1: Russian ICBM launches
        print("🇷🇺 Russian strategic missile launches...")
        for i, (lat, lon) in enumerate(self.russian_positions):
            missile_type = random.choice(self.strategic_missiles["russia"])
            target = random.choice(list(self.us_mainland.values()))
            
            self.launch_missile(
                platform_type=missile_type,
                lat=lat,
                lon=lon,
                target_lat=target[0],
                target_lon=target[1],
                altitude=0
            )
            time.sleep(3)  # Strategic timing
        
        # Phase 2: Chinese strategic launches
        print("🇨🇳 Chinese strategic missile launches...")
        for i, (lat, lon) in enumerate(self.chinese_positions):
            missile_type = random.choice(self.strategic_missiles["china"])
            target = random.choice(list(self.us_mainland.values()))
            
            self.launch_missile(
                platform_type=missile_type,
                lat=lat,
                lon=lon,
                target_lat=target[0],
                target_lon=target[1],
                altitude=0
            )
            time.sleep(2)
        
        # Phase 3: North Korean launches
        print("🇰🇵 North Korean missile launches...")
        for i, (lat, lon) in enumerate(self.nk_positions):
            missile_type = random.choice(self.strategic_missiles["north_korea"])
            target = random.choice(list(self.us_mainland.values()))
            
            self.launch_missile(
                platform_type=missile_type,
                lat=lat,
                lon=lon,
                target_lat=target[0],
                target_lon=target[1],
                altitude=0
            )
            time.sleep(2)
        
        # Phase 4: Second wave (cruise missiles)
        print("🚀 Second wave: Cruise missile attacks...")
        for _ in range(5):
            country = random.choice(["russia", "china"])
            positions = self.russian_positions if country == "russia" else self.chinese_positions
            missile_type = "Kh-101" if country == "russia" else "CJ-10"
            
            lat, lon = random.choice(positions)
            target = random.choice(list(self.us_mainland.values()))
            
            self.launch_missile(
                platform_type=missile_type,
                lat=lat,
                lon=lon,
                target_lat=target[0],
                target_lon=target[1],
                altitude=15000
            )
            time.sleep(1.5)

class MissileUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Initialize scenarios when user starts"""
        self.scenarios = {
            "defend_hawaii": DefendHawaiiScenario(self.client),
            "iron_dome": IronDomeScenario(self.client),
            "ww3": WW3Scenario(self.client),
        }
        self.current_scenario = None
    
    @task(3)
    def defend_hawaii_scenario(self):
        """Defend Hawaii from Chinese submarine attack"""
        if not self.current_scenario or self.current_scenario != "defend_hawaii":
            self.current_scenario = "defend_hawaii"
            self.scenarios["defend_hawaii"].execute_scenario()
    
    @task(2)
    def iron_dome_scenario(self):
        """Iron Dome defense against rocket attacks"""
        if not self.current_scenario or self.current_scenario != "iron_dome":
            self.current_scenario = "iron_dome"
            self.scenarios["iron_dome"].execute_scenario()
    
    @task(1)
    def ww3_scenario(self):
        """Full-scale WW3 scenario"""
        if not self.current_scenario or self.current_scenario != "ww3":
            self.current_scenario = "ww3"
            self.scenarios["ww3"].execute_scenario()
    
    @task(1)
    def random_launch(self):
        """Random missile launch for continuous testing"""
        platforms = [
            "MGM-140 ATACMS", "9K720 Iskander-M", "DF-21D", 
            "Hwasong-15", "Shahab-3", "Qassam Rocket"
        ]
        
        self.client.post("/launch", params={
            "platform_type": random.choice(platforms),
            "lat": random.uniform(30, 60),
            "lon": random.uniform(-180, 180),
            "target_lat": random.uniform(30, 60),
            "target_lon": random.uniform(-180, 180),
            "altitude_m": random.uniform(0, 50000)
        })

# Event listeners for monitoring
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("🚀 Missile Defense Simulation Test Starting...")
    print("📊 Scenarios available:")
    print("  - Defend Hawaii (Chinese submarine attack)")
    print("  - Iron Dome (Israeli rocket defense)")
    print("  - WW3 (US vs Russia, China, North Korea)")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("🏁 Missile Defense Simulation Test Complete!")