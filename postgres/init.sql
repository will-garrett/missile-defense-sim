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

-- Seed Data: Comprehensive Military Systems from Major World Powers and Insurgency Groups

-- Attack Platforms - United States
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, thrust_n) VALUES
('MGM-140 ATACMS', 'launch_platform', 'US Army Tactical Missile System', 0, 300000, 50000, 150, 230, 2000, 450000),
('MGM-31 Pershing II', 'launch_platform', 'US Army Medium-Range Ballistic Missile', 0, 1800000, 100000, 200, 1400, 3000, 600000),
('UGM-133 Trident II', 'launch_platform', 'US Navy Submarine-Launched Ballistic Missile', 0, 12000000, 1000000, 500, 2800, 8000, 1200000),
('AGM-158 JASSM', 'launch_platform', 'US Air Force Joint Air-to-Surface Standoff Missile', 0, 370000, 15000, 100, 450, 1500, 300000);

-- Attack Platforms - Russia
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, thrust_n) VALUES
('9K720 Iskander-M', 'launch_platform', 'Russian Army Tactical Ballistic Missile System', 0, 500000, 100000, 200, 500, 3000, 400000),
('RT-2PM2 Topol-M', 'launch_platform', 'Russian Strategic Ballistic Missile', 0, 11000000, 1200000, 800, 1200, 5000, 1000000),
('R-29RMU2 Layner', 'launch_platform', 'Russian Submarine-Launched Ballistic Missile', 0, 12000000, 1000000, 600, 2800, 8000, 1200000),
('Kh-101', 'launch_platform', 'Russian Air-Launched Cruise Missile', 0, 5500000, 15000, 150, 400, 2000, 350000);

-- Attack Platforms - China
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, thrust_n) VALUES
('DF-21D', 'launch_platform', 'Chinese Anti-Ship Ballistic Missile', 0, 1500000, 200000, 300, 800, 4000, 600000),
('DF-31AG', 'launch_platform', 'Chinese Road-Mobile ICBM', 0, 12000000, 1200000, 800, 1000, 5000, 1000000),
('JL-2', 'launch_platform', 'Chinese Submarine-Launched Ballistic Missile', 0, 8000000, 1000000, 500, 1000, 5000, 800000),
('CJ-10', 'launch_platform', 'Chinese Land-Attack Cruise Missile', 0, 2000000, 15000, 100, 500, 2000, 400000);

-- Attack Platforms - North Korea
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, thrust_n) VALUES
('Hwasong-15', 'launch_platform', 'North Korean Intercontinental Ballistic Missile', 0, 13000000, 1200000, 800, 1000, 5000, 1000000),
('Hwasong-12', 'launch_platform', 'North Korean Intermediate-Range Ballistic Missile', 0, 4500000, 800000, 400, 650, 3500, 700000),
('Pukguksong-2', 'launch_platform', 'North Korean Submarine-Launched Ballistic Missile', 0, 1200000, 500000, 300, 500, 2500, 500000);

-- Attack Platforms - Iran
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, thrust_n) VALUES
('Shahab-3', 'launch_platform', 'Iranian Medium-Range Ballistic Missile', 0, 1300000, 200000, 250, 750, 3500, 500000),
('Ghadr-110', 'launch_platform', 'Iranian Medium-Range Ballistic Missile', 0, 2000000, 300000, 300, 800, 4000, 600000),
('Soumar', 'launch_platform', 'Iranian Land-Attack Cruise Missile', 0, 2500000, 15000, 100, 450, 2000, 350000);

-- Attack Platforms - Insurgency Groups
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, max_payload_kg, fuel_capacity_kg, thrust_n) VALUES
('Qassam Rocket', 'launch_platform', 'Hamas Rocket Artillery', 0, 17000, 5000, 50, 5, 50, 10000),
('Grad Rocket', 'launch_platform', 'Insurgency Multiple Rocket Launcher', 0, 20000, 8000, 75, 20, 100, 15000),
('Fajr-5', 'launch_platform', 'Iranian-Backed Rocket Artillery', 0, 75000, 15000, 100, 90, 300, 25000),
('Katyusha Rocket', 'launch_platform', 'Soviet-Designed Rocket Artillery', 0, 20000, 8000, 60, 18, 80, 12000);

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
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent, ammo_capacity, cooldown_sec) VALUES
('Aegis BMD SM-3', 'counter_defense', 'US Navy Standard Missile 3', 3500, 2500000, 150000, 200, 30, 85, 32, 15),
('THAAD System', 'counter_defense', 'US Army Terminal High Altitude Area Defense', 2800, 200000, 150000, 150, 45, 90, 8, 20),
('Patriot PAC-3 MSE', 'counter_defense', 'US Army Patriot Advanced Capability', 1700, 100000, 80000, 100, 20, 95, 16, 10),
('GMD System', 'counter_defense', 'US Ground-Based Midcourse Defense', 8000, 8000000, 2000000, 500, 300, 75, 44, 120),
('Aegis BMD SM-6', 'counter_defense', 'US Navy Standard Missile 6', 3400, 2400000, 120000, 180, 35, 88, 24, 18);

-- Counter-Defense Systems - Russia
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent, ammo_capacity, cooldown_sec) VALUES
('S-400 Triumf', 'counter_defense', 'Russian Air Defense System', 4800, 400000, 30000, 120, 25, 92, 8, 12),
('S-500 Prometheus', 'counter_defense', 'Russian Strategic Air Defense System', 7000, 600000, 200000, 300, 60, 85, 4, 30),
('A-135 Amur', 'counter_defense', 'Russian Anti-Ballistic Missile System', 10000, 350000, 800000, 800, 120, 80, 68, 60),
('S-300V4', 'counter_defense', 'Russian Army Air Defense System', 2800, 400000, 35000, 100, 30, 90, 12, 15);

-- Counter-Defense Systems - China
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent, ammo_capacity, cooldown_sec) VALUES
('HQ-9B', 'counter_defense', 'Chinese Air Defense System', 4200, 300000, 27000, 110, 28, 91, 8, 14),
('HQ-19', 'counter_defense', 'Chinese Anti-Ballistic Missile System', 8000, 3000000, 1000000, 400, 90, 82, 12, 45),
('HQ-26', 'counter_defense', 'Chinese Naval Air Defense System', 3600, 400000, 30000, 120, 32, 89, 16, 16),
('HQ-29', 'counter_defense', 'Chinese Strategic Air Defense System', 6000, 500000, 150000, 250, 50, 87, 6, 25);

-- Counter-Defense Systems - NATO Allies
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent, ammo_capacity, cooldown_sec) VALUES
('Aster 30', 'counter_defense', 'European Air Defense Missile', 1400, 120000, 20000, 80, 15, 96, 32, 8),
('MEADS', 'counter_defense', 'US/German/Italian Air Defense System', 2400, 200000, 25000, 100, 22, 93, 12, 11),
('NASAMS', 'counter_defense', 'Norwegian Advanced Surface-to-Air Missile', 1000, 25000, 14000, 60, 12, 97, 24, 6),
('IRIS-T SLM', 'counter_defense', 'German Air Defense System', 3000, 40000, 20000, 70, 18, 94, 16, 9);

-- Counter-Defense Systems - Israel
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent, ammo_capacity, cooldown_sec) VALUES
('Iron Dome', 'counter_defense', 'Israeli Short-Range Air Defense', 300, 70000, 10000, 50, 8, 90, 20, 4),
('David''s Sling', 'counter_defense', 'Israeli Medium-Range Air Defense', 2400, 300000, 15000, 80, 20, 92, 12, 10),
('Arrow 3', 'counter_defense', 'Israeli Exo-Atmospheric Interceptor', 9000, 2400000, 100000, 300, 120, 85, 6, 60);

-- Counter-Defense Systems - India
INSERT INTO platform_type (nickname, category, description, max_speed_mps, max_range_m, max_altitude_m, blast_radius_m, reload_time_sec, accuracy_percent, ammo_capacity, cooldown_sec) VALUES
('Akash', 'counter_defense', 'Indian Medium-Range Air Defense', 850, 30000, 18000, 60, 15, 88, 16, 8),
('Barak 8', 'counter_defense', 'Indian-Israeli Air Defense System', 2000, 100000, 16000, 70, 25, 90, 8, 12),
('Prithvi Air Defense', 'counter_defense', 'Indian Exo-Atmospheric Interceptor', 5000, 2000000, 80000, 200, 90, 80, 4, 45);

-- Sample Installations - United States
INSERT INTO installation (platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count) VALUES
-- Attack Platforms
((SELECT id FROM platform_type WHERE nickname = 'MGM-140 ATACMS'), 'ATK_ATACMS_01', ST_GeogFromText('POINT(-118.25 34.05)'), 0, TRUE, 4),
((SELECT id FROM platform_type WHERE nickname = 'UGM-133 Trident II'), 'ATK_TRIDENT_01', ST_GeogFromText('POINT(-120.57 34.73)'), -200, FALSE, 24),

-- Detection Systems
((SELECT id FROM platform_type WHERE nickname = 'AN/TPY-2'), 'DET_TPY2_01', ST_GeogFromText('POINT(-117.15 32.71)'), 100, FALSE, 0),
((SELECT id FROM platform_type WHERE nickname = 'AN/SPY-1'), 'DET_SPY1_01', ST_GeogFromText('POINT(-119.70 36.78)'), 50, FALSE, 0),
((SELECT id FROM platform_type WHERE nickname = 'SBIRS GEO'), 'DET_SBIRS_01', ST_GeogFromText('POINT(-120.00 35.00)'), 35786000, FALSE, 0),

-- Counter-Defense Systems
((SELECT id FROM platform_type WHERE nickname = 'Aegis BMD SM-3'), 'DEF_AEGIS_01', ST_GeogFromText('POINT(-118.50 34.20)'), 0, FALSE, 32),
((SELECT id FROM platform_type WHERE nickname = 'THAAD System'), 'DEF_THAAD_01', ST_GeogFromText('POINT(-117.80 33.50)'), 0, TRUE, 8),
((SELECT id FROM platform_type WHERE nickname = 'Patriot PAC-3 MSE'), 'DEF_PATRIOT_01', ST_GeogFromText('POINT(-118.00 34.10)'), 0, FALSE, 16);

-- Sample Installations - Russia
INSERT INTO installation (platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count) VALUES
-- Attack Platforms
((SELECT id FROM platform_type WHERE nickname = '9K720 Iskander-M'), 'ATK_ISKANDER_01', ST_GeogFromText('POINT(37.62 55.75)'), 0, TRUE, 2),
((SELECT id FROM platform_type WHERE nickname = 'RT-2PM2 Topol-M'), 'ATK_TOPOL_01', ST_GeogFromText('POINT(37.90 55.80)'), 0, TRUE, 1),

-- Detection Systems
((SELECT id FROM platform_type WHERE nickname = 'Voronezh-DM'), 'DET_VORONEZH_01', ST_GeogFromText('POINT(37.50 55.70)'), 150, FALSE, 0),
((SELECT id FROM platform_type WHERE nickname = 'Don-2N'), 'DET_DON2N_01', ST_GeogFromText('POINT(37.40 55.60)'), 200, FALSE, 0),

-- Counter-Defense Systems
((SELECT id FROM platform_type WHERE nickname = 'S-400 Triumf'), 'DEF_S400_01', ST_GeogFromText('POINT(37.70 55.75)'), 0, TRUE, 8),
((SELECT id FROM platform_type WHERE nickname = 'A-135 Amur'), 'DEF_AMUR_01', ST_GeogFromText('POINT(37.30 55.65)'), 0, FALSE, 68);

-- Sample Installations - China
INSERT INTO installation (platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count) VALUES
-- Attack Platforms
((SELECT id FROM platform_type WHERE nickname = 'DF-21D'), 'ATK_DF21D_01', ST_GeogFromText('POINT(116.41 39.90)'), 0, TRUE, 4),
((SELECT id FROM platform_type WHERE nickname = 'DF-31AG'), 'ATK_DF31AG_01', ST_GeogFromText('POINT(116.50 39.95)'), 0, TRUE, 3),

-- Detection Systems
((SELECT id FROM platform_type WHERE nickname = 'PESA Radar'), 'DET_PESA_01', ST_GeogFromText('POINT(116.30 39.85)'), 120, FALSE, 0),
((SELECT id FROM platform_type WHERE nickname = 'YLC-8B'), 'DET_YLC8B_01', ST_GeogFromText('POINT(116.35 39.88)'), 100, FALSE, 0),

-- Counter-Defense Systems
((SELECT id FROM platform_type WHERE nickname = 'HQ-9B'), 'DEF_HQ9B_01', ST_GeogFromText('POINT(116.45 39.92)'), 0, TRUE, 8),
((SELECT id FROM platform_type WHERE nickname = 'HQ-19'), 'DEF_HQ19_01', ST_GeogFromText('POINT(116.40 39.87)'), 0, FALSE, 12);

-- Sample Installations - NATO Allies
INSERT INTO installation (platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count) VALUES
-- Detection Systems
((SELECT id FROM platform_type WHERE nickname = 'SAMPSON'), 'DET_SAMPSON_01', ST_GeogFromText('POINT(-0.13 51.51)'), 0, FALSE, 0),
((SELECT id FROM platform_type WHERE nickname = 'APAR'), 'DET_APAR_01', ST_GeogFromText('POINT(4.90 52.37)'), 0, FALSE, 0),

-- Counter-Defense Systems
((SELECT id FROM platform_type WHERE nickname = 'Aster 30'), 'DEF_ASTER_01', ST_GeogFromText('POINT(-0.10 51.50)'), 0, FALSE, 32),
((SELECT id FROM platform_type WHERE nickname = 'MEADS'), 'DEF_MEADS_01', ST_GeogFromText('POINT(13.41 52.52)'), 0, TRUE, 12);

-- Sample Installations - Israel
INSERT INTO installation (platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count) VALUES
-- Counter-Defense Systems
((SELECT id FROM platform_type WHERE nickname = 'Iron Dome'), 'DEF_IRONDOME_01', ST_GeogFromText('POINT(34.78 32.09)'), 0, TRUE, 20),
((SELECT id FROM platform_type WHERE nickname = 'David''s Sling'), 'DEF_DAVIDSLING_01', ST_GeogFromText('POINT(34.80 32.10)'), 0, TRUE, 12),
((SELECT id FROM platform_type WHERE nickname = 'Arrow 3'), 'DEF_ARROW3_01', ST_GeogFromText('POINT(34.75 32.08)'), 0, FALSE, 6);

-- Sample Installations - Insurgency Groups
INSERT INTO installation (platform_type_id, callsign, geom, altitude_m, is_mobile, ammo_count) VALUES
-- Attack Platforms
((SELECT id FROM platform_type WHERE nickname = 'Qassam Rocket'), 'ATK_QASSAM_01', ST_GeogFromText('POINT(34.45 31.50)'), 0, TRUE, 50),
((SELECT id FROM platform_type WHERE nickname = 'Grad Rocket'), 'ATK_GRAD_01', ST_GeogFromText('POINT(34.50 31.55)'), 0, TRUE, 40),
((SELECT id FROM platform_type WHERE nickname = 'Fajr-5'), 'ATK_FAJR5_01', ST_GeogFromText('POINT(34.40 31.45)'), 0, TRUE, 12);

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