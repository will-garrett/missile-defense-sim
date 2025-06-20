CREATE EXTENSION IF NOT EXISTS postgis;

-- Lookup tables --------------------------------------------------------------
CREATE TABLE missile_type   (
  id SERIAL PRIMARY KEY, name TEXT UNIQUE, speed_mps NUMERIC, blast_m NUMERIC );
CREATE TABLE battery_type   (
  id SERIAL PRIMARY KEY, name TEXT UNIQUE,
  max_range_m NUMERIC, max_speed_mps NUMERIC, blast_m NUMERIC );
CREATE TABLE radar_type     (
  id SERIAL PRIMARY KEY, name TEXT UNIQUE,
  max_range_m NUMERIC, sweep_rate_deg NUMERIC );

-- Installations --------------------------------------------------------------
CREATE TABLE battery (
  id SERIAL PRIMARY KEY, type_id INT REFERENCES battery_type,
  geom GEOGRAPHY(Point,4326), ammo_count INT, call_sign TEXT UNIQUE );
CREATE INDEX battery_gix ON battery USING GIST (geom);

CREATE TABLE radar_site (
  id SERIAL PRIMARY KEY, type_id INT REFERENCES radar_type,
  geom GEOGRAPHY(Point,4326), call_sign TEXT UNIQUE );
CREATE INDEX radar_gix ON radar_site USING GIST (geom);

-- Missiles in flight ---------------------------------------------------------
CREATE TABLE missile_flight (
  id TEXT PRIMARY KEY, type_id INT REFERENCES missile_type,
  launch_ts TIMESTAMP, launch_geom GEOGRAPHY(Point,4326),
  target_geom GEOGRAPHY(Point,4326),
  vx NUMERIC, vy NUMERIC, vz NUMERIC, destroyed BOOLEAN DEFAULT FALSE );

-- Seed data ------------------------------------------------------------------
INSERT INTO missile_type (name,speed_mps,blast_m)
VALUES ('SCUD-C',1700,250);

INSERT INTO battery_type (name,max_range_m,max_speed_mps,blast_m)
VALUES ('SM-6 Battery',200000,3500,200);

INSERT INTO radar_type (name,max_range_m,sweep_rate_deg)
VALUES ('AN/TPY-2',900000,120);

INSERT INTO battery (type_id,geom,ammo_count,call_sign)
VALUES
 (1,ST_GeogFromText('POINT(-118.25 34.05)'),32,'BAT_LA'),
 (1,ST_GeogFromText('POINT(-117.15 32.71)'),16,'BAT_SD');

INSERT INTO radar_site (type_id,geom,call_sign)
VALUES (1,ST_GeogFromText('POINT(-120.57 34.73)'),'RAD_VBG');