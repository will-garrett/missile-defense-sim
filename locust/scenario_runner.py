#!/usr/bin/env python3
"""
Missile Defense Simulation Scenario Runner

This script allows you to run specific scenarios without the full Locust framework.
It sets up scenarios via the simulation service API and then initiates attacks.
"""

import requests
import time
import random
import json
import argparse
import sys
from scenarios import AVAILABLE_SCENARIOS, get_scenario, list_scenarios

class ScenarioRunner:
    def __init__(self, simulation_api_url="http://localhost:8001", api_launcher_url="http://localhost:9000"):
        self.simulation_api_url = simulation_api_url
        self.api_launcher_url = api_launcher_url
        self.session = requests.Session()
    
    def setup_scenario_installations(self, scenario_name):
        """Set up installations for a specific scenario via simulation service API"""
        scenario = get_scenario(scenario_name)
        if not scenario:
            print(f"❌ Scenario '{scenario_name}' not found!")
            return False
        
        print(f"🔧 Setting up installations for scenario: {scenario['name']}")
        print(f"📝 Description: {scenario['description']}")
        
        # Prepare installations for the scenario
        installations = []
        
        # Add target defense installations
        if 'defenses' in scenario['target']:
            if 'lat' in scenario['target']:
                # Single target location
                target_lat = scenario['target']['lat']
                target_lon = scenario['target']['lon']
                
                for i, defense_platform in enumerate(scenario['target']['defenses']):
                    # Spread defense installations around the target
                    offset_lat = random.uniform(-0.1, 0.1)
                    offset_lon = random.uniform(-0.1, 0.1)
                    
                    installations.append({
                        "platform_type_nickname": defense_platform,
                        "callsign": f"DEF_{defense_platform.replace(' ', '_')}_{i+1:02d}",
                        "lat": target_lat + offset_lat,
                        "lon": target_lon + offset_lon,
                        "altitude_m": 0,
                        "is_mobile": "THAAD" in defense_platform or "Iron Dome" in defense_platform,
                        "ammo_count": self._get_default_ammo_count(defense_platform)
                    })
            else:
                # Multiple target locations
                for location_name, (lat, lon) in scenario['target']['locations'].items():
                    for i, defense_platform in enumerate(scenario['target']['defenses']):
                        offset_lat = random.uniform(-0.05, 0.05)
                        offset_lon = random.uniform(-0.05, 0.05)
                        
                        installations.append({
                            "platform_type_nickname": defense_platform,
                            "callsign": f"DEF_{location_name.upper()}_{defense_platform.replace(' ', '_')}_{i+1:02d}",
                            "lat": lat + offset_lat,
                            "lon": lon + offset_lon,
                            "altitude_m": 0,
                            "is_mobile": "THAAD" in defense_platform or "Iron Dome" in defense_platform,
                            "ammo_count": self._get_default_ammo_count(defense_platform)
                        })
        
        # Add detection systems
        detection_systems = self._get_detection_systems_for_scenario(scenario_name)
        for i, detection_system in enumerate(detection_systems):
            if 'lat' in scenario['target']:
                # Single target - place detection systems around target
                target_lat = scenario['target']['lat']
                target_lon = scenario['target']['lon']
                offset_lat = random.uniform(-0.2, 0.2)
                offset_lon = random.uniform(-0.2, 0.2)
                
                installations.append({
                    "platform_type_nickname": detection_system,
                    "callsign": f"DET_{detection_system.replace(' ', '_')}_{i+1:02d}",
                    "lat": target_lat + offset_lat,
                    "lon": target_lon + offset_lon,
                    "altitude_m": 100 if "Satellite" not in detection_system else 35786000,
                    "is_mobile": False,
                    "ammo_count": 0
                })
            else:
                # Multiple targets - place detection systems strategically
                for location_name, (lat, lon) in scenario['target']['locations'].items():
                    offset_lat = random.uniform(-0.1, 0.1)
                    offset_lon = random.uniform(-0.1, 0.1)
                    
                    installations.append({
                        "platform_type_nickname": detection_system,
                        "callsign": f"DET_{location_name.upper()}_{detection_system.replace(' ', '_')}_{i+1:02d}",
                        "lat": lat + offset_lat,
                        "lon": lon + offset_lon,
                        "altitude_m": 100 if "Satellite" not in detection_system else 35786000,
                        "is_mobile": False,
                        "ammo_count": 0
                    })
        
        # Add attacker installations
        for attacker_name, attacker_config in scenario['attackers'].items():
            for i, position in enumerate(attacker_config['positions']):
                for platform in attacker_config['platforms']:
                    installations.append({
                        "platform_type_nickname": platform,
                        "callsign": f"ATK_{attacker_name.upper()}_{platform.replace(' ', '_')}_{i+1:02d}",
                        "lat": position[0] + random.uniform(-0.02, 0.02),
                        "lon": position[1] + random.uniform(-0.02, 0.02),
                        "altitude_m": -200 if "Submarine" in platform else 0,
                        "is_mobile": "Road-Mobile" in platform or "Mobile" in platform,
                        "ammo_count": self._get_default_ammo_count(platform)
                    })
        
        # Set up scenario via simulation service API
        try:
            response = self.session.post(
                f"{self.simulation_api_url}/scenarios/setup",
                json={
                    "scenario_name": scenario_name,
                    "installations": installations
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Scenario setup successful!")
                print(f"📊 Created {result['installations_created']} installations")
                return True
            else:
                print(f"❌ Failed to set up scenario: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Exception setting up scenario: {e}")
            return False
    
    def _get_default_ammo_count(self, platform_name):
        """Get default ammunition count for a platform"""
        ammo_counts = {
            # Attack platforms
            "MGM-140 ATACMS": 4,
            "UGM-133 Trident II": 24,
            "9K720 Iskander-M": 2,
            "RT-2PM2 Topol-M": 1,
            "DF-21D": 4,
            "DF-31AG": 3,
            "Hwasong-15": 1,
            "Hwasong-12": 2,
            "Shahab-3": 3,
            "Qassam Rocket": 50,
            "Grad Rocket": 40,
            "Fajr-5": 12,
            
            # Defense systems
            "Aegis BMD SM-3": 32,
            "THAAD System": 8,
            "Patriot PAC-3 MSE": 16,
            "GMD System": 44,
            "Aegis BMD SM-6": 24,
            "S-400 Triumf": 8,
            "S-500 Prometheus": 4,
            "A-135 Amur": 68,
            "HQ-9B": 8,
            "HQ-19": 12,
            "Aster 30": 32,
            "MEADS": 12,
            "Iron Dome": 20,
            "David's Sling": 12,
            "Arrow 3": 6,
        }
        return ammo_counts.get(platform_name, 10)
    
    def _get_detection_systems_for_scenario(self, scenario_name):
        """Get appropriate detection systems for a scenario"""
        detection_systems = {
            "defend_hawaii": [
                "AN/TPY-2",
                "AN/SPY-1", 
                "SBX-1",
                "SBIRS GEO"
            ],
            "iron_dome": [
                "AN/TPY-2",
                "AN/SPY-1"
            ],
            "ww3": [
                "AN/FPS-132",
                "SBX-1",
                "Cobra Dane",
                "SBIRS GEO",
                "SBIRS HEO"
            ],
            "nato_defense": [
                "SAMPSON",
                "APAR",
                "EMPAR",
                "Herakles"
            ],
            "middle_east": [
                "AN/TPY-2",
                "AN/SPY-1"
            ]
        }
        return detection_systems.get(scenario_name, ["AN/TPY-2", "AN/SPY-1"])
    
    def launch_missile(self, platform_type, lat, lon, target_lat, target_lon, altitude=0):
        """Launch a missile with specified parameters"""
        try:
            response = self.session.post(f"{self.api_launcher_url}/launch", params={
                "platform_type": platform_type,
                "lat": lat,
                "lon": lon,
                "target_lat": target_lat,
                "target_lon": target_lon,
                "altitude_m": altitude
            })
            
            if response.status_code == 200:
                print(f"✅ Launched {platform_type} from ({lat:.3f}, {lon:.3f}) to ({target_lat:.3f}, {target_lon:.3f})")
                return True
            else:
                print(f"❌ Failed to launch {platform_type}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Exception launching {platform_type}: {e}")
            return False
    
    def execute_scenario(self, scenario_name, delay_between_phases=5):
        """Execute a specific scenario"""
        scenario = get_scenario(scenario_name)
        if not scenario:
            print(f"❌ Scenario '{scenario_name}' not found!")
            return False
        
        print(f"🚀 Starting scenario: {scenario['name']}")
        print(f"📝 Description: {scenario['description']}")
        print(f"⏱️  Delay between phases: {delay_between_phases} seconds")
        print("-" * 60)
        
        # First, set up the scenario installations
        if not self.setup_scenario_installations(scenario_name):
            return False
        
        print(f"\n🎯 Scenario setup complete. Waiting 3 seconds before launching attacks...")
        time.sleep(3)
        
        success_count = 0
        total_count = 0
        
        # Execute each attacker's phases
        for attacker_name, attacker_config in scenario['attackers'].items():
            print(f"\n🇺🇸 Attacker: {attacker_name.upper()}")
            
            for phase in attacker_config['phases']:
                print(f"  📡 Phase: {phase['name']}")
                
                # Determine platforms to use
                platforms = attacker_config['platforms']
                if 'platform_filter' in phase:
                    platforms = [p for p in platforms if p in phase['platform_filter']]
                
                # Execute launches based on phase configuration
                if 'total_missiles' in phase:
                    # Launch total_missiles from random positions
                    for _ in range(phase['total_missiles']):
                        position = random.choice(attacker_config['positions'])
                        platform = random.choice(platforms)
                        
                        # Handle target coordinates
                        if 'lat' in scenario['target']:
                            # Single target
                            target_lat = scenario['target']['lat']
                            target_lon = scenario['target']['lon']
                            if 'target_spread' in phase:
                                target_lat += random.uniform(-phase['target_spread'], phase['target_spread'])
                                target_lon += random.uniform(-phase['target_spread'], phase['target_spread'])
                        else:
                            # Multiple targets
                            target = random.choice(list(scenario['target']['locations'].values()))
                            target_lat, target_lon = target
                        
                        # Add randomness to launch position
                        launch_lat = position[0] + random.uniform(-0.02, 0.02)
                        launch_lon = position[1] + random.uniform(-0.02, 0.02)
                        
                        success = self.launch_missile(
                            platform_type=platform,
                            lat=launch_lat,
                            lon=launch_lon,
                            target_lat=target_lat,
                            target_lon=target_lon,
                            altitude=phase.get('altitude', 0)
                        )
                        
                        if success:
                            success_count += 1
                        total_count += 1
                        
                        time.sleep(phase.get('delay_between_launches', 1))
                
                elif 'missiles_per_position' in phase:
                    # Launch missiles_per_position from each position
                    for position in attacker_config['positions']:
                        for _ in range(phase['missiles_per_position']):
                            platform = random.choice(platforms)
                            
                            # Handle target coordinates
                            if 'lat' in scenario['target']:
                                target_lat = scenario['target']['lat']
                                target_lon = scenario['target']['lon']
                            else:
                                target = random.choice(list(scenario['target']['locations'].values()))
                                target_lat, target_lon = target
                            
                            # Add randomness to launch position
                            launch_lat = position[0] + random.uniform(-0.02, 0.02)
                            launch_lon = position[1] + random.uniform(-0.02, 0.02)
                            
                            success = self.launch_missile(
                                platform_type=platform,
                                lat=launch_lat,
                                lon=launch_lon,
                                target_lat=target_lat,
                                target_lon=target_lon,
                                altitude=phase.get('altitude', 0)
                            )
                            
                            if success:
                                success_count += 1
                            total_count += 1
                            
                            time.sleep(phase.get('delay_between_launches', 1))
                
                print(f"  ✅ Phase complete: {phase['name']}")
                time.sleep(delay_between_phases)
        
        # Handle scenario-level phases (like WW3)
        if 'phases' in scenario:
            print(f"\n🌍 Executing scenario-level phases...")
            for phase in scenario['phases']:
                print(f"  📡 Phase: {phase['name']}")
                
                if 'attacker' in phase:
                    # Single attacker phase
                    attacker_config = scenario['attackers'][phase['attacker']]
                    for position in attacker_config['positions']:
                        platform = random.choice(attacker_config['platforms'])
                        
                        # Handle target coordinates
                        if 'lat' in scenario['target']:
                            target_lat = scenario['target']['lat']
                            target_lon = scenario['target']['lon']
                        else:
                            target = random.choice(list(scenario['target']['locations'].values()))
                            target_lat, target_lon = target
                        
                        success = self.launch_missile(
                            platform_type=platform,
                            lat=position[0],
                            lon=position[1],
                            target_lat=target_lat,
                            target_lon=target_lon,
                            altitude=0
                        )
                        
                        if success:
                            success_count += 1
                        total_count += 1
                        
                        time.sleep(3)  # Strategic timing
                
                elif 'attackers' in phase:
                    # Multiple attackers phase
                    for _ in range(phase.get('total_missiles', 5)):
                        attacker_name = random.choice(phase['attackers'])
                        attacker_config = scenario['attackers'][attacker_name]
                        position = random.choice(attacker_config['positions'])
                        platform = random.choice(phase['platforms'])
                        
                        # Handle target coordinates
                        if 'lat' in scenario['target']:
                            target_lat = scenario['target']['lat']
                            target_lon = scenario['target']['lon']
                        else:
                            target = random.choice(list(scenario['target']['locations'].values()))
                            target_lat, target_lon = target
                        
                        success = self.launch_missile(
                            platform_type=platform,
                            lat=position[0],
                            lon=position[1],
                            target_lat=target_lat,
                            target_lon=target_lon,
                            altitude=phase.get('altitude', 15000)
                        )
                        
                        if success:
                            success_count += 1
                        total_count += 1
                        
                        time.sleep(phase.get('delay_between_launches', 1.5))
                
                print(f"  ✅ Phase complete: {phase['name']}")
                time.sleep(phase.get('delay_after_previous', 5))
        
        print(f"\n🏁 Scenario '{scenario_name}' complete!")
        print(f"📊 Results: {success_count}/{total_count} launches successful ({success_count/total_count*100:.1f}%)")
        return success_count > 0

def main():
    parser = argparse.ArgumentParser(description="Missile Defense Simulation Scenario Runner")
    parser.add_argument("scenario", nargs="?", help="Scenario name to run")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--simulation-api", default="http://localhost:8001", help="Simulation service API URL")
    parser.add_argument("--api-launcher", default="http://localhost:9000", help="API launcher URL")
    parser.add_argument("--delay", type=int, default=5, help="Delay between phases in seconds")
    
    args = parser.parse_args()
    
    if args.list:
        print("Available scenarios:")
        for name, scenario in AVAILABLE_SCENARIOS.items():
            print(f"  {name}: {scenario['description']}")
        return
    
    if not args.scenario:
        print("❌ Please specify a scenario name or use --list to see available scenarios")
        print("Usage examples:")
        print("  python scenario_runner.py defend_hawaii")
        print("  python scenario_runner.py iron_dome --delay 3")
        print("  python scenario_runner.py ww3 --simulation-api http://localhost:8001")
        return
    
    runner = ScenarioRunner(args.simulation_api, args.api_launcher)
    success = runner.execute_scenario(args.scenario, args.delay)
    
    if success:
        print("✅ Scenario execution completed successfully!")
        sys.exit(0)
    else:
        print("❌ Scenario execution failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 