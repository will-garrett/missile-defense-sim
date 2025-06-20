CREATE EXTENSION IF NOT EXISTS postgis;

-- Platform Types (Attack and Defense) -----------------------------------------
CREATE TABLE platform_type (
    id SERIAL PRIMARY KEY,
    nickname TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('launch_platform', 'detection_system', 'counter_defense')),
    description TEXT,
    max_speed_mps NUMERIC DEFAULT 0, -- 0 for permanent installations
    max_range_m NUMERIC,
    max_altitude_m NUMERIC,
    blast_radius_m NUMERIC,
    detection_range_m NUMERIC,
    sweep_rate_deg_per_sec NUMERIC,
    reload_time_sec NUMERIC,
    accuracy_percent NUMERIC,
    max_payload_kg NUMERIC,
    fuel_capacity_kg NUMERIC,
    fuel_consumption_rate_kgps NUMERIC, -- Fuel consumption rate in kg/s
    thrust_n NUMERIC,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Installation Locations ------------------------------------------------------
CREATE TABLE installation (
    id SERIAL PRIMARY KEY,
    platform_type_id INT REFERENCES platform_type(id),
    callsign TEXT UNIQUE NOT NULL,
    geom GEOGRAPHY(Point,4326) NOT NULL,
    altitude_m NUMERIC DEFAULT 0,
    is_mobile BOOLEAN DEFAULT FALSE,
    current_speed_mps NUMERIC DEFAULT 0,
    heading_deg NUMERIC DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'damaged', 'destroyed')),
    ammo_count INT DEFAULT 0,
    fuel_level_percent NUMERIC DEFAULT 100,
    last_position_update TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Movement Paths for Mobile Installations ------------------------------------
CREATE TABLE movement_path (
    id SERIAL PRIMARY KEY,
    installation_id INT REFERENCES installation(id),
    path_order INT NOT NULL,
    geom GEOGRAPHY(Point,4326) NOT NULL,
    altitude_m NUMERIC DEFAULT 0,
    speed_mps NUMERIC DEFAULT 0,
    wait_time_sec NUMERIC DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Active Missiles (Attack and Defense) ---------------------------------------
CREATE TABLE active_missile (
    id TEXT PRIMARY KEY,
    callsign TEXT NOT NULL,
    platform_type_id INT REFERENCES platform_type(id),
    launch_installation_id INT REFERENCES installation(id),
  target_geom GEOGRAPHY(Point,4326),
    target_altitude_m NUMERIC DEFAULT 0,
    launch_ts TIMESTAMP DEFAULT NOW(),
    current_geom GEOGRAPHY(Point,4326),
    current_altitude_m NUMERIC,
    velocity_x_mps NUMERIC,
    velocity_y_mps NUMERIC,
    velocity_z_mps NUMERIC,
    fuel_remaining_kg NUMERIC,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'destroyed', 'detonated', 'fuel_exhausted')),
    missile_type TEXT DEFAULT 'attack' CHECK (missile_type IN ('attack', 'defense')),
    target_missile_id TEXT REFERENCES active_missile(id), -- for defense missiles
    detonation_geom GEOGRAPHY(Point,4326),
    detonation_ts TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Detection Events -----------------------------------------------------------
CREATE TABLE detection_event (
    id SERIAL PRIMARY KEY,
    detection_installation_id INT REFERENCES installation(id),
    detected_missile_id TEXT REFERENCES active_missile(id),
    detection_geom GEOGRAPHY(Point,4326),
    detection_altitude_m NUMERIC,
    detection_ts TIMESTAMP DEFAULT NOW(),
    signal_strength_db NUMERIC,
    confidence_percent NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tracking Data --------------------------------------------------------------
CREATE TABLE tracking_data (
    id SERIAL PRIMARY KEY,
    missile_id TEXT REFERENCES active_missile(id),
    tracking_installation_id INT REFERENCES installation(id),
    geom GEOGRAPHY(Point,4326),
    altitude_m NUMERIC,
    velocity_x_mps NUMERIC,
    velocity_y_mps NUMERIC,
    velocity_z_mps NUMERIC,
    tracking_ts TIMESTAMP DEFAULT NOW(),
    accuracy_m NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Counter-Defense Engagements ------------------------------------------------
CREATE TABLE engagement (
    id SERIAL PRIMARY KEY,
    target_missile_id TEXT REFERENCES active_missile(id),
    defense_missile_id TEXT REFERENCES active_missile(id),
    launch_installation_id INT REFERENCES installation(id),
    engagement_ts TIMESTAMP DEFAULT NOW(),
    intercept_geom GEOGRAPHY(Point,4326),
    intercept_altitude_m NUMERIC,
    status TEXT DEFAULT 'launched' CHECK (status IN ('launched', 'intercepted', 'missed', 'failed')),
    intercept_distance_m NUMERIC,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Engagement Attempts (for retry logic) --------------------------------------
CREATE TABLE engagement_attempt (
    id SERIAL PRIMARY KEY,
    target_missile_id TEXT REFERENCES active_missile(id),
    defense_installation_id INT REFERENCES installation(id),
    attempt_number INT NOT NULL,
    launch_ts TIMESTAMP DEFAULT NOW(),
    intercept_geom GEOGRAPHY(Point,4326),
    intercept_altitude_m NUMERIC,
    status TEXT DEFAULT 'attempted' CHECK (status IN ('attempted', 'successful', 'failed')),
    failure_reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Detonation Events ----------------------------------------------------------
CREATE TABLE detonation_event (
    id SERIAL PRIMARY KEY,
    missile_id TEXT REFERENCES active_missile(id),
    detonation_geom GEOGRAPHY(Point,4326),
    detonation_altitude_m NUMERIC,
    detonation_ts TIMESTAMP DEFAULT NOW(),
    blast_radius_m NUMERIC,
    casualties_estimated INT DEFAULT 0,
    damage_assessment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Simulation Configuration ---------------------------------------------------
CREATE TABLE simulation_config (
    id SERIAL PRIMARY KEY,
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Missile outcome tracking
CREATE TABLE missile_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    missile_id UUID NOT NULL,
    callsign VARCHAR(100) NOT NULL,
    missile_type VARCHAR(50) NOT NULL,
    outcome_type VARCHAR(50) NOT NULL, -- 'detonated', 'intercepted', 'fuel_exhaustion', 'malfunction', 'ground_impact'
    outcome_location GEOMETRY(POINT, 4326),
    outcome_altitude_m DECIMAL(10,2),
    outcome_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    blast_radius_m DECIMAL(10,2),
    target_achieved BOOLEAN,
    intercepting_missile_id UUID,
    intercepting_battery_callsign VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for Performance ----------------------------------------------------
CREATE INDEX idx_installation_geom ON installation USING GIST (geom);
CREATE INDEX idx_installation_platform ON installation(platform_type_id);
CREATE INDEX idx_active_missile_status ON active_missile(status);
CREATE INDEX idx_active_missile_type ON active_missile(missile_type);
CREATE INDEX idx_detection_event_ts ON detection_event(detection_ts);
CREATE INDEX idx_tracking_data_missile ON tracking_data(missile_id);
CREATE INDEX idx_tracking_data_ts ON tracking_data(tracking_ts);
CREATE INDEX idx_engagement_target ON engagement(target_missile_id);
CREATE INDEX idx_engagement_status ON engagement(status);
CREATE INDEX idx_missile_outcome_missile_id ON missile_outcome(missile_id);
CREATE INDEX idx_missile_outcome_outcome_type ON missile_outcome(outcome_type);
CREATE INDEX idx_missile_outcome_time ON missile_outcome(outcome_time);

-- Seed Data: Comprehensive Military Systems from Major World Powers and Insurgency Groups

-- Attack Platforms - United States
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, fuel_consumption_rate_kgps, thrust_n) VALUES
('MGM-140 ATACMS', 'launch_platform', 'US Army Tactical Missile System', 0, 300000, 50000, 200, 230, 2000, 15.0, 450000),
('MGM-31 Pershing II', 'launch_platform', 'US Army Medium-Range Ballistic Missile', 0, 1800000, 100000, 350, 1400, 3000, 12.0, 600000),
('UGM-133 Trident II', 'launch_platform', 'US Navy Submarine-Launched Ballistic Missile', 0, 12000000, 1000000, 800, 2800, 12000, 20.0, 1200000),
('AGM-158 JASSM', 'launch_platform', 'US Air Force Joint Air-to-Surface Standoff Missile', 0, 370000, 15000, 150, 450, 1500, 1.5, 300000);

-- Attack Platforms - Russia
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, fuel_consumption_rate_kgps, thrust_n) VALUES
('9K720 Iskander-M', 'launch_platform', 'Russian Army Tactical Ballistic Missile System', 0, 500000, 100000, 250, 500, 3000, 15.0, 400000),
('RT-2PM2 Topol-M', 'launch_platform', 'Russian Strategic Ballistic Missile', 0, 11000000, 1200000, 1000, 1200, 5000, 18.0, 1000000),
('R-29RMU2 Layner', 'launch_platform', 'Russian Submarine-Launched Ballistic Missile', 0, 12000000, 1000000, 900, 2800, 12000, 22.0, 1200000),
('Kh-101', 'launch_platform', 'Russian Air-Launched Cruise Missile', 0, 5500000, 15000, 200, 400, 2000, 1.8, 350000);

-- Attack Platforms - China
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, fuel_consumption_rate_kgps, thrust_n) VALUES
('DF-21D', 'launch_platform', 'Chinese Anti-Ship Ballistic Missile', 0, 1500000, 200000, 400, 800, 4000, 16.0, 600000),
('DF-31AG', 'launch_platform', 'Chinese Road-Mobile ICBM', 0, 12000000, 1200000, 1000, 1000, 5000, 20.0, 1000000),
('JL-2', 'launch_platform', 'Chinese Submarine-Launched Ballistic Missile', 0, 8000000, 1000000, 800, 1000, 5000, 18.0, 800000),
('CJ-10', 'launch_platform', 'Chinese Land-Attack Cruise Missile', 0, 2000000, 15000, 150, 500, 2000, 1.2, 400000);

-- Attack Platforms - North Korea
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, fuel_consumption_rate_kgps, thrust_n) VALUES
('Hwasong-15', 'launch_platform', 'North Korean Intercontinental Ballistic Missile', 0, 13000000, 1200000, 1000, 1000, 5000, 18.0, 1000000),
('Hwasong-12', 'launch_platform', 'North Korean Intermediate-Range Ballistic Missile', 0, 4500000, 800000, 500, 650, 3500, 14.0, 700000),
('Pukguksong-2', 'launch_platform', 'North Korean Submarine-Launched Ballistic Missile', 0, 1200000, 500000, 400, 500, 2500, 12.0, 500000);

-- Attack Platforms - Iran
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, fuel_consumption_rate_kgps, thrust_n) VALUES
('Shahab-3', 'launch_platform', 'Iranian Medium-Range Ballistic Missile', 0, 1300000, 200000, 300, 750, 3500, 23.0, 500000),
('Ghadr-110', 'launch_platform', 'Iranian Medium-Range Ballistic Missile', 0, 2000000, 300000, 350, 800, 4000, 25.0, 600000),
('Soumar', 'launch_platform', 'Iranian Land-Attack Cruise Missile', 0, 2500000, 15000, 150, 450, 2000, 3.2, 350000);

-- Attack Platforms - Insurgency Groups
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, fuel_consumption_rate_kgps, thrust_n) VALUES
('Qassam Rocket', 'launch_platform', 'Hamas Rocket Artillery', 0, 17000, 5000, 30, 5, 50, 2.0, 10000),
('Grad Rocket', 'launch_platform', 'Insurgency Multiple Rocket Launcher', 0, 20000, 8000, 50, 20, 100, 3.0, 15000),
('Fajr-5', 'launch_platform', 'Iranian-Backed Rocket Artillery', 0, 75000, 15000, 80, 90, 300, 5.0, 25000),
('Katyusha Rocket', 'launch_platform', 'Soviet-Designed Rocket Artillery', 0, 20000, 8000, 40, 18, 80, 2.5, 12000);

-- Detection Systems - United States
INSERT INTO platform_type (nickname, category, description, detection_range_m, sweep_rate_deg_per_sec, max_altitude_m) VALUES
('AN/TPY-2', 'detection_system', 'US Army X-Band Radar', 900000, 120, 30000),
('AN/SPY-1', 'detection_system', 'US Navy Aegis Radar', 800000, 90, 25000),
('AN/FPS-132', 'detection_system', 'US Air Force Upgraded Early Warning Radar', 5000000, 360, 40000),
('SBX-1', 'detection_system', 'US Missile Defense Sea-Based X-Band Radar', 4000000, 180, 50000),
('Cobra Dane', 'detection_system', 'US Air Force Phased Array Radar', 3000000, 240, 35000);

-- Detection Systems - Russia
INSERT INTO platform_type (nickname, category, description, detection_range_m, sweep_rate_deg_per_sec, max_altitude_m) VALUES
('Voronezh-DM', 'detection_system', 'Russian Early Warning Radar', 6000000, 360, 40000),
('Daryal Radar', 'detection_system', 'Russian Over-the-Horizon Radar', 6000000, 360, 40000),
('Volga Radar', 'detection_system', 'Russian Early Warning Radar', 4800000, 300, 35000),
('Don-2N', 'detection_system', 'Russian Battle Management Radar', 3700000, 240, 30000);

-- Detection Systems - China
INSERT INTO platform_type (nickname, category, description, detection_range_m, sweep_rate_deg_per_sec, max_altitude_m) VALUES
('PESA Radar', 'detection_system', 'Chinese Phased Array Early Warning Radar', 5000000, 360, 40000),
('YLC-8B', 'detection_system', 'Chinese Long-Range Air Surveillance Radar', 4000000, 300, 35000),
('JY-27A', 'detection_system', 'Chinese 3D Air Surveillance Radar', 3000000, 240, 30000),
('SLC-7', 'detection_system', 'Chinese L-Band Air Surveillance Radar', 3500000, 270, 32000);

-- Detection Systems - NATO Allies
INSERT INTO platform_type (nickname, category, description, detection_range_m, sweep_rate_deg_per_sec, max_altitude_m) VALUES
('SAMPSON', 'detection_system', 'UK Royal Navy Multi-Function Radar', 400000, 120, 25000),
('APAR', 'detection_system', 'German/Dutch Naval Multi-Function Radar', 350000, 100, 20000),
('EMPAR', 'detection_system', 'Italian Naval Multi-Function Radar', 300000, 90, 20000),
('Herakles', 'detection_system', 'French Naval Multi-Function Radar', 250000, 80, 18000);

-- Detection Systems - Space-Based
INSERT INTO platform_type (nickname, category, description, detection_range_m, sweep_rate_deg_per_sec, max_altitude_m) VALUES
('SBIRS GEO', 'detection_system', 'US Space-Based Infrared System', 5000000, 360, 35786000),
('SBIRS HEO', 'detection_system', 'US Space-Based Infrared System High Earth Orbit', 5000000, 360, 35786000),
('Tundra Satellite', 'detection_system', 'Russian Early Warning Satellite', 5000000, 360, 35786000),
('DSP Satellite', 'detection_system', 'US Defense Support Program Satellite', 5000000, 360, 35786000);

-- Counter-Defense Systems - United States
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent) VALUES
('Aegis BMD SM-3', 'counter_defense', 'US Navy Standard Missile 3', 3500, 2500000, 150000, 50, 30, 85),
('THAAD System', 'counter_defense', 'US Army Terminal High Altitude Area Defense', 2800, 200000, 150000, 40, 45, 90),
('Patriot PAC-3 MSE', 'counter_defense', 'US Army Patriot Advanced Capability', 1700, 100000, 80000, 30, 20, 95),
('GMD System', 'counter_defense', 'US Ground-Based Midcourse Defense', 8000, 8000000, 2000000, 100, 300, 75),
('Aegis BMD SM-6', 'counter_defense', 'US Navy Standard Missile 6', 3400, 2400000, 120000, 45, 35, 88);

-- Counter-Defense Systems - Russia
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent) VALUES
('S-400 Triumf', 'counter_defense', 'Russian Air Defense System', 4800, 400000, 30000, 35, 25, 92),
('S-500 Prometheus', 'counter_defense', 'Russian Strategic Air Defense System', 7000, 600000, 200000, 60, 60, 85),
('A-135 Amur', 'counter_defense', 'Russian Anti-Ballistic Missile System', 10000, 350000, 800000, 80, 120, 80),
('S-300V4', 'counter_defense', 'Russian Army Air Defense System', 2800, 400000, 35000, 30, 30, 90);

-- Counter-Defense Systems - China
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent) VALUES
('HQ-9B', 'counter_defense', 'Chinese Air Defense System', 4200, 300000, 27000, 35, 28, 91),
('HQ-19', 'counter_defense', 'Chinese Anti-Ballistic Missile System', 8000, 3000000, 1000000, 70, 90, 82),
('HQ-26', 'counter_defense', 'Chinese Naval Air Defense System', 3600, 400000, 30000, 40, 32, 89),
('HQ-29', 'counter_defense', 'Chinese Strategic Air Defense System', 6000, 500000, 150000, 50, 50, 87);

-- Counter-Defense Systems - NATO Allies
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent) VALUES
('Aster 30', 'counter_defense', 'European Air Defense Missile', 1400, 120000, 20000, 25, 15, 96),
('MEADS', 'counter_defense', 'US/German/Italian Air Defense System', 2400, 200000, 25000, 30, 22, 93),
('NASAMS', 'counter_defense', 'Norwegian Advanced Surface-to-Air Missile', 1000, 25000, 14000, 20, 12, 97),
('IRIS-T SLM', 'counter_defense', 'German Air Defense System', 3000, 40000, 20000, 25, 18, 94);

-- Counter-Defense Systems - Israel
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent) VALUES
('Iron Dome', 'counter_defense', 'Israeli Short-Range Air Defense', 300, 70000, 10000, 15, 8, 90),
('David''s Sling', 'counter_defense', 'Israeli Medium-Range Air Defense', 2400, 300000, 15000, 25, 20, 92),
('Arrow 3', 'counter_defense', 'Israeli Exo-Atmospheric Interceptor', 9000, 2400000, 100000, 60, 120, 85);

-- Counter-Defense Systems - India
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent) VALUES
('Akash', 'counter_defense', 'Indian Medium-Range Air Defense', 850, 30000, 18000, 20, 15, 88),
('Barak 8', 'counter_defense', 'Indian-Israeli Air Defense System', 2000, 100000, 16000, 25, 25, 90),
('Prithvi Air Defense', 'counter_defense', 'Indian Exo-Atmospheric Interceptor', 5000, 2000000, 80000, 40, 90, 80);

-- Simulation Configuration
INSERT INTO simulation_config (config_key, config_value, description) VALUES
('simulation_tick_ms', '100', 'Simulation update interval in milliseconds'),
('physics_gravity_mps2', '9.81', 'Gravitational acceleration'),
('physics_air_density_sea_level', '1.225', 'Air density at sea level kg/m³'),
('physics_scale_height', '8500', 'Atmospheric scale height in meters'),
('max_engagement_retries', '3', 'Maximum number of counter-missile attempts per target'),
('radar_update_interval_ms', '1000', 'Radar detection update interval'),
('missile_position_update_ms', '100', 'Missile position update interval'),
('installation_position_update_ms', '5000', 'Mobile installation position update interval'),
('battery_reload_cooldown_multiplier', '1.5', 'Multiplier for battery cooldown after reload'),
('insurgency_accuracy_penalty', '0.3', 'Accuracy penalty for insurgency weapons'),
('military_accuracy_bonus', '1.2', 'Accuracy bonus for military systems');

-- Triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_platform_type_updated_at BEFORE UPDATE ON platform_type FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_installation_updated_at BEFORE UPDATE ON installation FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_active_missile_updated_at BEFORE UPDATE ON active_missile FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_engagement_updated_at BEFORE UPDATE ON engagement FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();