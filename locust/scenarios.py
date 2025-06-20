"""
Missile Defense Simulation Scenarios Configuration

This file contains predefined scenarios for testing the missile defense system.
Each scenario represents a realistic military situation with appropriate
platforms, locations, and timing.
"""

# Scenario 1: Defend Hawaii from Chinese Submarine Attack
DEFEND_HAWAII_SCENARIO = {
    "name": "defend_hawaii",
    "description": "Chinese submarine attack on Hawaii",
    "target": {
        "name": "Hawaii",
        "lat": 21.31,
        "lon": -157.86,
        "defenses": [
            "Aegis BMD SM-3",  # Naval defense
            "THAAD System",    # Terminal defense
            "Patriot PAC-3 MSE", # Point defense
        ]
    },
    "attackers": {
        "china": {
            "positions": [
                (25.0, -155.0),  # North of Hawaii
                (20.0, -160.0),  # West of Hawaii
                (22.0, -152.0),  # East of Hawaii
            ],
            "platforms": [
                "JL-2",           # Submarine-launched ballistic missile
                "DF-21D",         # Anti-ship ballistic missile
                "CJ-10",          # Land-attack cruise missile
            ],
            "phases": [
                {
                    "name": "Initial Strike",
                    "missiles_per_position": 1,
                    "altitude": -200,  # Submarine depth
                    "delay_between_launches": 2,
                },
                {
                    "name": "Cruise Missile Follow-up",
                    "missiles_per_position": 1,
                    "altitude": 15000,
                    "delay_between_launches": 1.5,
                    "platform_filter": ["CJ-10"],
                }
            ]
        }
    }
}

# Scenario 2: Iron Dome Defense
IRON_DOME_SCENARIO = {
    "name": "iron_dome",
    "description": "Israeli Iron Dome defense against rocket attacks",
    "target": {
        "name": "Israel",
        "lat": 32.09,
        "lon": 34.78,
        "defenses": [
            "Iron Dome",        # Short-range defense
            "David's Sling",    # Medium-range defense
            "Arrow 3",          # Exo-atmospheric interceptor
        ]
    },
    "attackers": {
        "insurgency": {
            "positions": [
                (31.50, 34.45),  # Northern Gaza
                (31.45, 34.40),  # Central Gaza
                (31.40, 34.35),  # Southern Gaza
            ],
            "platforms": [
                "Qassam Rocket",    # Hamas rocket
                "Grad Rocket",      # Multiple rocket launcher
                "Fajr-5",          # Iranian-backed rocket
                "Katyusha Rocket",  # Soviet-designed rocket
            ],
            "phases": [
                {
                    "name": "Rocket Barrage",
                    "total_missiles": 10,
                    "altitude": 0,
                    "delay_between_launches": 0.5,
                    "target_spread": 0.1,  # Random spread around target
                },
                {
                    "name": "Coordinated Attack",
                    "missiles_per_position": 1,
                    "altitude": 15000,
                    "delay_between_launches": 1,
                    "platform_filter": ["Fajr-5"],
                }
            ]
        }
    }
}

# Scenario 3: WW3 Full-Scale Conflict
WW3_SCENARIO = {
    "name": "ww3",
    "description": "Full-scale WW3: US vs Russia, China, North Korea",
    "target": {
        "name": "United States",
        "locations": {
            "east_coast": (40.71, -74.01),    # New York
            "west_coast": (34.05, -118.25),   # Los Angeles
            "central": (39.74, -104.99),      # Denver
            "southeast": (33.75, -84.39),     # Atlanta
        },
        "defenses": [
            "Aegis BMD SM-3",    # Naval defense
            "THAAD System",      # Terminal defense
            "Patriot PAC-3 MSE", # Point defense
            "GMD System",        # Ground-based midcourse defense
            "Aegis BMD SM-6",    # Extended range defense
        ]
    },
    "attackers": {
        "russia": {
            "positions": [
                (55.75, 37.62),   # Moscow area
                (55.80, 37.90),   # Moscow area
                (55.70, 37.50),   # Moscow area
            ],
            "platforms": [
                "RT-2PM2 Topol-M", # Strategic ballistic missile
                "R-29RMU2 Layner", # Submarine-launched ballistic missile
                "Kh-101",          # Air-launched cruise missile
            ],
            "phases": [
                {
                    "name": "Strategic ICBM Launch",
                    "missiles_per_position": 1,
                    "altitude": 0,
                    "delay_between_launches": 3,
                }
            ]
        },
        "china": {
            "positions": [
                (39.90, 116.41),  # Beijing area
                (39.95, 116.50),  # Beijing area
                (39.85, 116.30),  # Beijing area
            ],
            "platforms": [
                "DF-31AG",        # Road-mobile ICBM
                "JL-2",           # Submarine-launched ballistic missile
                "CJ-10",          # Land-attack cruise missile
            ],
            "phases": [
                {
                    "name": "Strategic Launch",
                    "missiles_per_position": 1,
                    "altitude": 0,
                    "delay_between_launches": 2,
                }
            ]
        },
        "north_korea": {
            "positions": [
                (39.03, 125.75),  # Pyongyang
                (38.96, 125.68),  # Pyongyang area
            ],
            "platforms": [
                "Hwasong-15",     # Intercontinental ballistic missile
                "Hwasong-12",     # Intermediate-range ballistic missile
                "Pukguksong-2",   # Submarine-launched ballistic missile
            ],
            "phases": [
                {
                    "name": "Strategic Launch",
                    "missiles_per_position": 1,
                    "altitude": 0,
                    "delay_between_launches": 2,
                }
            ]
        }
    },
    "phases": [
        {
            "name": "Russian ICBM Wave",
            "attacker": "russia",
            "delay_after_previous": 0,
        },
        {
            "name": "Chinese Strategic Wave",
            "attacker": "china",
            "delay_after_previous": 5,
        },
        {
            "name": "North Korean Wave",
            "attacker": "north_korea",
            "delay_after_previous": 3,
        },
        {
            "name": "Cruise Missile Follow-up",
            "attackers": ["russia", "china"],
            "platforms": ["Kh-101", "CJ-10"],
            "total_missiles": 5,
            "altitude": 15000,
            "delay_between_launches": 1.5,
            "delay_after_previous": 10,
        }
    ]
}

# Scenario 4: NATO Defense Exercise
NATO_DEFENSE_SCENARIO = {
    "name": "nato_defense",
    "description": "NATO defense against Russian aggression in Europe",
    "target": {
        "name": "NATO Europe",
        "locations": {
            "uk": (51.51, -0.13),      # London
            "germany": (52.52, 13.41), # Berlin
            "france": (48.86, 2.35),   # Paris
            "italy": (41.90, 12.50),   # Rome
        },
        "defenses": [
            "Aster 30",         # European air defense missile
            "MEADS",            # US/German/Italian air defense system
            "NASAMS",           # Norwegian advanced surface-to-air missile
            "IRIS-T SLM",       # German air defense system
        ]
    },
    "attackers": {
        "russia": {
            "positions": [
                (55.75, 37.62),   # Moscow area
                (55.80, 37.90),   # Moscow area
                (59.93, 30.36),   # St. Petersburg area
            ],
            "platforms": [
                "9K720 Iskander-M", # Tactical ballistic missile
                "S-400 Triumf",     # Air defense system (offensive use)
                "Kh-101",           # Air-launched cruise missile
            ],
            "phases": [
                {
                    "name": "Tactical Strike",
                    "missiles_per_position": 2,
                    "altitude": 0,
                    "delay_between_launches": 1.5,
                }
            ]
        }
    }
}

# Scenario 5: Middle East Conflict
MIDDLE_EAST_SCENARIO = {
    "name": "middle_east",
    "description": "Regional conflict in the Middle East",
    "target": {
        "name": "Saudi Arabia",
        "lat": 24.71,
        "lon": 46.68,
        "defenses": [
            "Patriot PAC-3 MSE", # US Patriot system
            "THAAD System",      # Terminal High Altitude Area Defense
        ]
    },
    "attackers": {
        "iran": {
            "positions": [
                (35.69, 51.39),   # Tehran
                (32.65, 51.67),   # Isfahan
                (29.59, 52.58),   # Shiraz
            ],
            "platforms": [
                "Shahab-3",       # Medium-range ballistic missile
                "Ghadr-110",      # Medium-range ballistic missile
                "Soumar",         # Land-attack cruise missile
            ],
            "phases": [
                {
                    "name": "Ballistic Missile Attack",
                    "missiles_per_position": 1,
                    "altitude": 0,
                    "delay_between_launches": 2,
                }
            ]
        },
        "houthi": {
            "positions": [
                (15.37, 44.19),   # Sana'a
                (12.78, 45.01),   # Aden
            ],
            "platforms": [
                "Qassam Rocket",  # Improvised rocket
                "Grad Rocket",    # Multiple rocket launcher
            ],
            "phases": [
                {
                    "name": "Rocket Attack",
                    "total_missiles": 8,
                    "altitude": 0,
                    "delay_between_launches": 0.8,
                }
            ]
        }
    }
}

# All available scenarios
AVAILABLE_SCENARIOS = {
    "defend_hawaii": DEFEND_HAWAII_SCENARIO,
    "iron_dome": IRON_DOME_SCENARIO,
    "ww3": WW3_SCENARIO,
    "nato_defense": NATO_DEFENSE_SCENARIO,
    "middle_east": MIDDLE_EAST_SCENARIO,
}

def get_scenario(scenario_name):
    """Get a scenario configuration by name"""
    return AVAILABLE_SCENARIOS.get(scenario_name)

def list_scenarios():
    """List all available scenarios"""
    return list(AVAILABLE_SCENARIOS.keys())

def get_scenario_description(scenario_name):
    """Get the description of a scenario"""
    scenario = get_scenario(scenario_name)
    return scenario["description"] if scenario else None 