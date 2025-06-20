#!/usr/bin/env python3
"""
Missile Defense Simulation Scenario Runner

This script allows you to run specific scenarios without the full Locust framework.
Useful for testing individual scenarios or running them programmatically.
"""

import requests
import time
import random
import json
import argparse
import sys
from scenarios import AVAILABLE_SCENARIOS, get_scenario, list_scenarios

class ScenarioRunner:
    def __init__(self, api_url="http://localhost:9000"):
        self.api_url = api_url
        self.session = requests.Session()
    
    def launch_missile(self, platform_type, lat, lon, target_lat, target_lon, altitude=0):
        """Launch a missile with specified parameters"""
        try:
            response = self.session.post(f"{self.api_url}/launch", params={
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
    parser.add_argument("--api-url", default="http://localhost:9000", help="API server URL")
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
        print("  python scenario_runner.py ww3 --api-url http://localhost:9000")
        return
    
    runner = ScenarioRunner(args.api_url)
    success = runner.execute_scenario(args.scenario, args.delay)
    
    if success:
        print("✅ Scenario execution completed successfully!")
        sys.exit(0)
    else:
        print("❌ Scenario execution failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 