-- Drop all tables to ensure a clean slate
DROP TABLE IF EXISTS scenarios, detonation_event, engagement_attempt, engagement, tracking_data, detection_event, active_missile, movement_path, installation_munition, installation, munition_type, platform_type, simulation_config, missile_outcome CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column();

CREATE EXTENSION IF NOT EXISTS postgis;

-- Platform Types (Launchers, Radars, etc.) ------------------------------------
CREATE TABLE platform_type (
    id SERIAL PRIMARY KEY,
    nickname TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('launch_platform', 'detection_system', 'counter_defense')),
    description TEXT,
    is_mobile BOOLEAN DEFAULT TRUE,
    max_speed_mps NUMERIC DEFAULT 0, -- Speed if mobile
    max_payload_kg NUMERIC, -- Max weight of munitions it can carry
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Munition Types (Missiles, Interceptors) -------------------------------------
CREATE TABLE munition_type (
    id SERIAL PRIMARY KEY,
    nickname TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('attack', 'defense')),
    description TEXT,
    max_range_m NUMERIC,
    max_altitude_m NUMERIC,
    blast_radius_m NUMERIC,
    accuracy_percent NUMERIC,
    weight_kg NUMERIC, -- Weight of a single munition unit
    fuel_capacity_kg NUMERIC,
    fuel_consumption_rate_kgps NUMERIC,
    thrust_n NUMERIC,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Deployed Instances of Platforms ---------------------------------------------
CREATE TABLE installation (
    id SERIAL PRIMARY KEY,
    platform_type_id INT REFERENCES platform_type(id),
    callsign TEXT UNIQUE NOT NULL,
    geom GEOGRAPHY(Point,4326) NOT NULL,
    altitude_m NUMERIC DEFAULT 0,
    heading_deg NUMERIC DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'damaged', 'destroyed')),
    last_position_update TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Munition loadout for each installation --------------------------------------
CREATE TABLE installation_munition (
    id SERIAL PRIMARY KEY,
    installation_id INT REFERENCES installation(id) ON DELETE CASCADE,
    munition_type_id INT REFERENCES munition_type(id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity >= 0),
    UNIQUE (installation_id, munition_type_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Active Missiles (In-flight) ------------------------------------------------
CREATE TABLE active_missile (
    id TEXT PRIMARY KEY, -- Callsign will be used as ID
    munition_type_id INT REFERENCES munition_type(id),
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
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Scenario Actions -----------------------------------------------------------
CREATE TABLE scenarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_name VARCHAR(255) NOT NULL,
    time_from_start_seconds INT NOT NULL,
    action JSONB NOT NULL
);

-- Auto-update 'updated_at' column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_platform_type_updated_at BEFORE UPDATE ON platform_type FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_munition_type_updated_at BEFORE UPDATE ON munition_type FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_installation_updated_at BEFORE UPDATE ON installation FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_active_missile_updated_at BEFORE UPDATE ON active_missile FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed Data: Platform Types (The launchers and systems)
INSERT INTO platform_type (nickname, category, description, is_mobile, max_speed_mps) VALUES
('Ticonderoga-class cruiser', 'counter_defense', 'US Navy guided-missile cruiser with Aegis Combat System.', true, 16.9), -- 32.5 knots
('THAAD Launcher', 'counter_defense', 'US Army road-mobile launcher for Terminal High Altitude Area Defense interceptors.', true, 26.8), -- 60 mph
('Generic TEL', 'launch_platform', 'Generic Transporter Erector Launcher for various ballistic missiles.', true, 20.1), -- 45 mph
('AN/TPY-2', 'detection_system', 'X-band, high-resolution, phased-array radar for ballistic missile detection and tracking.', true, 18),
('AN/SPY-1', 'detection_system', 'Naval phased-array radar at the heart of the Aegis Combat System.', false, 0);

-- Seed Data: Munition Types (The missiles and interceptors)
INSERT INTO munition_type (nickname, category, description, max_range_m, max_altitude_m, blast_radius_m, weight_kg) VALUES
('SM-3', 'defense', 'Aegis Ballistic Missile Defense interceptor.', 700000, 250000, 5000, 1500),
('THAAD Interceptor', 'defense', 'Hit-to-kill interceptor for the THAAD system.', 200000, 150000, 50, 900),
('DF-21D', 'attack', 'Chinese Anti-Ship Ballistic Missile, "carrier-killer".', 1500000, 200000, 400, 600),
('Hwasong-15', 'attack', 'North Korean Intercontinental Ballistic Missile.', 13000000, 1200000, 1000, 1000),
('CJ-10', 'attack', 'Chinese Land-Attack Cruise Missile.', 2000000, 15000, 150, 500);

-- Seed Scenario Data: A more structured approach
-- This test scenario deploys systems, arms them, and then launches attacks.

-- 1. Deploy all platforms and systems
INSERT INTO scenarios (scenario_name, time_from_start_seconds, action) VALUES
('Hawaii Test Bravo', 1, '{"deploy_radar": {"platform_nickname": "AN/TPY-2", "callsign": "RADAR-PEARL", "lat": 21.35, "lon": -157.98, "alt": 150}}'),
('Hawaii Test Bravo', 1, '{"deploy_radar": {"platform_nickname": "AN/SPY-1", "callsign": "RADAR-LAKE-ERIE", "lat": 21.40, "lon": -158.20, "alt": 25}}'),
('Hawaii Test Bravo', 1, '{"deploy_defense_battery": {"platform_nickname": "Ticonderoga-class cruiser", "callsign": "USS-LAKE-ERIE", "lat": 21.40, "lon": -158.20, "alt": 25}}'),
('Hawaii Test Bravo', 1, '{"deploy_defense_battery": {"platform_nickname": "THAAD Launcher", "callsign": "THAAD-ALPHA", "lat": 21.32, "lon": -157.85, "alt": 200}}'),
('Hawaii Test Bravo', 1, '{"deploy_launcher": {"platform_nickname": "Generic TEL", "callsign": "NK-TEL-1", "lat": 39.02, "lon": 125.75, "alt": 50}}'),
('Hawaii Test Bravo', 1, '{"deploy_launcher": {"platform_nickname": "Generic TEL", "callsign": "CN-TEL-1", "lat": 25.0, "lon": -155.0, "alt": 100}}');

-- 2. Arm the defense batteries
INSERT INTO scenarios (scenario_name, time_from_start_seconds, action) VALUES
('Hawaii Test Bravo', 5, '{"arm_battery": {"launcher_callsign": "USS-LAKE-ERIE", "munition_nickname": "SM-3", "quantity": 12}}'),
('Hawaii Test Bravo', 5, '{"arm_battery": {"launcher_callsign": "THAAD-ALPHA", "munition_nickname": "THAAD Interceptor", "quantity": 8}}');

-- 3. Arm the attack launchers
INSERT INTO scenarios (scenario_name, time_from_start_seconds, action) VALUES
('Hawaii Test Bravo', 10, '{"arm_launcher": {"launcher_callsign": "NK-TEL-1", "munition_nickname": "Hwasong-15", "quantity": 1}}'),
('Hawaii Test Bravo', 10, '{"arm_launcher": {"launcher_callsign": "CN-TEL-1", "munition_nickname": "DF-21D", "quantity": 2}}');

-- 4. Launch the attacks
INSERT INTO scenarios (scenario_name, time_from_start_seconds, action) VALUES
('Hawaii Test Bravo', 30, '{"launch_missile": {"launcher_callsign": "CN-TEL-1", "munition_nickname": "DF-21D", "target_lat": 21.30, "target_lon": -157.86, "target_alt": 0}}'),
('Hawaii Test Bravo', 120, '{"launch_missile": {"launcher_callsign": "NK-TEL-1", "munition_nickname": "Hwasong-15", "target_lat": 21.44, "target_lon": -158.05, "target_alt": 0}}');