# Updates

Still working out the bugs of this portfolio project, still very much a WIP

# Missile Defense Simulator

A distributed missile defense simulation system using NATS, ZeroMQ, PostgreSQL with PostGIS, and Prometheus/Grafana for monitoring.

## System Architecture

```mermaid
graph TB
    %% External Interfaces
    subgraph "External Interfaces"
        UI[Web Browser<br/>User Interface]
        API[API Client<br/>REST Requests]
    end
    
    %% Core Services
    subgraph "Core Services"
        AL[api_launcher<br/>REST API Server<br/>Port: 9000<br/>Function: Launch missiles<br/>Metrics: /metrics:8003]
        TS[track_sim<br/>Trajectory Simulator<br/>Port: 5556/5557<br/>Function: Physics simulation<br/>Metrics: /metrics:8004]
    end
    
    %% Detection System
    subgraph "Detection System"
        RS1[radar_site-1<br/>Radar Detection<br/>Call Sign: RAD_VBG<br/>Function: Missile detection<br/>Metrics: /metrics:8000]
        RS2[radar_site-2<br/>Radar Detection<br/>Call Sign: RAD_VBG<br/>Function: Missile detection<br/>Metrics: /metrics:8000]
        RS3[radar_site-3<br/>Radar Detection<br/>Call Sign: RAD_VBG<br/>Function: Missile detection<br/>Metrics: /metrics:8000]
    end
    
    %% Command & Control
    subgraph "Command & Control"
        CC[command_center<br/>Correlation Engine<br/>Port: 5558<br/>Function: Threat correlation<br/>Metrics: /metrics:8005]
        BS[battery_sim<br/>Missile Battery<br/>Call Sign: BAT_LA<br/>Function: Interceptor firing<br/>Metrics: /metrics:8006]
        IS[interceptor_sim<br/>Interceptor Simulator<br/>Function: Intercept simulation<br/>Metrics: /metrics:8007]
    end
    
    %% Infrastructure
    subgraph "Infrastructure"
        NATS[NATS Server<br/>Message Broker<br/>Port: 4222<br/>Function: Pub/Sub messaging]
        PG[(PostgreSQL<br/>Database<br/>Port: 5432<br/>Function: Spatial data storage<br/>Extension: PostGIS)]
        PROM[Prometheus<br/>Metrics Collector<br/>Port: 9090<br/>Function: Time series data]
        GRAF[Grafana<br/>Visualization<br/>Port: 3000<br/>Function: Metrics dashboard]
        PGA[PgAdmin<br/>DB Admin<br/>Port: 8080<br/>Function: Database management]
    end
    
    %% Load Testing
    subgraph "Load Testing"
        LM[locust-master<br/>Load Test Master<br/>Port: 8089<br/>Function: Test coordination<br/>UI: Web interface]
        LW1[locust-worker-1<br/>Load Test Worker<br/>Function: Request generation]
        LW2[locust-worker-2<br/>Load Test Worker<br/>Function: Request generation]
        LW3[locust-worker-3<br/>Load Test Worker<br/>Function: Request generation]
    end
    
    %% Message Flow
    %% External to Core
    API -->|POST /launch<br/>lat, lon, targetLat, targetLon| AL
    UI -->|HTTP GET| LM
    
    %% Core Service Communication
    AL -->|ZeroMQ PUB<br/>missile_id, lat, lon, alt_m| TS
    TS -->|ZeroMQ PUB<br/>track updates| RS1
    TS -->|ZeroMQ PUB<br/>track updates| RS2
    TS -->|ZeroMQ PUB<br/>track updates| RS3
    
    %% Detection to Command
    RS1 -->|NATS PUB<br/>radar.detection| NATS
    RS2 -->|NATS PUB<br/>radar.detection| NATS
    RS3 -->|NATS PUB<br/>radar.detection| NATS
    NATS -->|NATS SUB<br/>radar.detection| CC
    
    %% Command to Battery
    CC -->|ZeroMQ PUB<br/>intercept command| BS
    BS -->|NATS PUB<br/>command.intercept| NATS
    NATS -->|NATS SUB<br/>command.intercept| IS
    
    %% Interceptor Results
    IS -->|NATS PUB<br/>interceptor.detonation| NATS
    
    %% Database Connections
    AL -->|SQL<br/>INSERT missile_flight| PG
    TS -->|SQL<br/>SELECT missile data| PG
    RS1 -->|SQL<br/>SELECT radar range| PG
    RS2 -->|SQL<br/>SELECT radar range| PG
    RS3 -->|SQL<br/>SELECT radar range| PG
    CC -->|SQL<br/>SELECT battery, UPDATE ammo| PG
    BS -->|SQL<br/>SELECT ammo count| PG
    
    %% Metrics Collection
    AL -->|HTTP<br/>Prometheus metrics| PROM
    TS -->|HTTP<br/>Prometheus metrics| PROM
    RS1 -->|HTTP<br/>Prometheus metrics| PROM
    RS2 -->|HTTP<br/>Prometheus metrics| PROM
    RS3 -->|HTTP<br/>Prometheus metrics| PROM
    CC -->|HTTP<br/>Prometheus metrics| PROM
    BS -->|HTTP<br/>Prometheus metrics| PROM
    IS -->|HTTP<br/>Prometheus metrics| PROM
    
    %% Load Testing
    LM -->|HTTP<br/>test requests| AL
    LW1 -->|HTTP<br/>test requests| AL
    LW2 -->|HTTP<br/>test requests| AL
    LW3 -->|HTTP<br/>test requests| AL
    
    %% Visualization
    PROM -->|HTTP<br/>metrics data| GRAF
    PG -->|HTTP<br/>database access| PGA
    
    %% Styling
    classDef service fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef infrastructure fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef external fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef detection fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef command fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef loadtest fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    
    class AL,TS service
    class NATS,PG,PROM,GRAF,PGA infrastructure
    class UI,API external
    class RS1,RS2,RS3 detection
    class CC,BS,IS command
    class LM,LW1,LW2,LW3 loadtest
```

## Message Flow Details

### 1. Missile Launch Sequence
```mermaid
sequenceDiagram
    participant Client
    participant API as api_launcher
    participant DB as PostgreSQL
    participant Track as track_sim
    participant Radar as radar_site
    
    Client->>API: POST /launch (lat, lon, target)
    API->>DB: INSERT missile_flight
    API->>Track: ZeroMQ: missile data
    Track->>Track: Physics simulation
    Track->>Radar: ZeroMQ: track updates
    Radar->>Radar: Range calculation
    alt Missile in range
        Radar->>NATS: radar.detection
    end
```

### 2. Intercept Sequence
```mermaid
sequenceDiagram
    participant Radar1 as radar_site-1
    participant Radar2 as radar_site-2
    participant NATS
    participant CC as command_center
    participant DB as PostgreSQL
    participant Battery as battery_sim
    participant Interceptor as interceptor_sim
    
    Radar1->>NATS: radar.detection
    Radar2->>NATS: radar.detection
    NATS->>CC: radar.detection (correlated)
    CC->>DB: SELECT battery, UPDATE ammo
    CC->>Battery: ZeroMQ: intercept command
    Battery->>NATS: command.intercept
    NATS->>Interceptor: command.intercept
    Interceptor->>Interceptor: Flight simulation
    Interceptor->>NATS: interceptor.detonation
```

## Component Functions

### Core Services
- **api_launcher**: REST API for missile launches, stores flight data in PostgreSQL
- **track_sim**: Physics simulation of missile trajectories, publishes track updates via ZeroMQ

### Detection System
- **radar_site** (3 replicas): Geographic missile detection using PostGIS spatial queries
- **Functions**: Range calculation, signal-to-noise ratio simulation, detection correlation

### Command & Control
- **command_center**: Correlates multiple radar detections, selects optimal battery for intercept
- **battery_sim**: Manages ammunition, fires interceptors based on command center orders
- **interceptor_sim**: Simulates interceptor missile flight and detonation

### Infrastructure
- **NATS**: Message broker for asynchronous communication between services
- **PostgreSQL**: Spatial database with PostGIS extension for geographic calculations
- **Prometheus**: Metrics collection and time-series storage
- **Grafana**: Metrics visualization and dashboards
- **PgAdmin**: Database administration interface

### Load Testing
- **locust-master**: Coordinates distributed load testing, provides web UI
- **locust-worker** (3 replicas): Generate HTTP requests to test system performance

## Architecture

The system consists of several microservices:

- **api_launcher**: REST API for launching missiles
- **track_sim**: Simulates missile trajectories using ZeroMQ
- **radar_site**: Radar detection system (3 replicas)
- **command_center**: Correlates radar detections and orders intercepts
- **battery_sim**: Missile battery that fires interceptors
- **interceptor_sim**: Simulates interceptor missiles
- **nats**: Message broker for inter-service communication
- **postgres**: Database with PostGIS for spatial data
- **prometheus**: Metrics collection
- **grafana**: Metrics visualization
- **pgadmin**: Database administration

## Recent Fixes Applied

### 1. SQL Syntax Error in radar_site.py
- **Issue**: Malformed SQL query with inline comments causing syntax errors
- **Fix**: Properly formatted multi-line SQL query with comments outside the string

### 2. Database Connection Timing Issues
- **Issue**: Services trying to connect to PostgreSQL before it's ready
- **Fix**: Added health checks to PostgreSQL and retry logic to all services
- **Fix**: Updated docker-compose.yml with proper service dependencies

### 3. Missing asyncio Import
- **Issue**: track_sim.py missing asyncio import
- **Fix**: Added proper import and restructured the main execution

### 4. ZeroMQ Async Operations
- **Issue**: Services using blocking ZeroMQ operations in async contexts
- **Fix**: Updated all services to use proper async ZeroMQ methods (`await sock.recv()`, `await pub.send_json()`)
- **Fix**: Added proper error handling and timeouts for ZeroMQ operations

### 5. Service Dependencies
- **Issue**: Services starting before dependencies are ready
- **Fix**: Added health checks and proper dependency conditions in docker-compose.yml

## Quick Start

1. **Build and start the system**:
   ```bash
   python build_system.py
   ```
   
   Or manually:
   ```bash
   docker-compose up -d
   ```

2. **Wait for services to initialize** (check logs):
   ```bash
   docker-compose logs -f
   ```

3. **Debug the system** (if needed):
   ```bash
   python debug_system.py
   ```

4. **Test the system**:
   ```bash
   python test_system.py
   ```

5. **Monitor the system**:
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (admin/admin)
   - PgAdmin: http://localhost:8080 (admin@missilesim.com/admin123)
   - Locust: http://localhost:8089

## API Usage

### Launch a Missile
```bash
curl -X POST "http://localhost:9000/launch?lat=34.0522&lon=-118.2437&targetLat=33.7490&targetLon=-84.3880&missileType=SCUD-C"
```

### Check Metrics
```bash
curl http://localhost:8003/metrics  # api_launcher
curl http://localhost:8004/metrics  # track_sim
curl http://localhost:8005/metrics  # command_center
curl http://localhost:8006/metrics  # battery_sim
curl http://localhost:8007/metrics  # interceptor_sim
```

## Environment Variables

Copy `env-example` to `.env` and modify as needed:

- `RADAR_CALL_SIGN`: Radar site call sign (default: RAD_VBG)
- `BATTERY_CALL_SIGN`: Battery call sign (default: BAT_LA)

## Troubleshooting

### Common Issues

1. **Database connection errors**: Wait for PostgreSQL to fully initialize (check health status)
2. **Service startup failures**: Check logs with `docker-compose logs <service_name>`
3. **ZeroMQ connection issues**: Ensure services start in the correct order
4. **Async operation errors**: All ZeroMQ operations now use proper async methods
5. **Locust UI not loading**: Check if Locust services are running and port 8089 is available

### Debug Commands

```bash
# Check system health
python debug_system.py

# Check service status
docker-compose ps

# View logs for specific service
docker-compose logs -f api_launcher

# Restart specific service
docker-compose restart api_launcher

# Check database connectivity
docker-compose exec postgres pg_isready -U missiles -d missilesim

# Rebuild and restart all services
docker-compose down
docker-compose build
docker-compose up -d
```

### ZeroMQ Debugging

If you see ZeroMQ-related errors:

1. **Check socket connections**: Ensure services are binding/connecting to correct ports
2. **Verify async usage**: All ZeroMQ operations should use `await`
3. **Check timeouts**: Services use 100ms timeouts for non-blocking operations

### Locust Debugging

If Locust UI is not loading:

1. **Check Locust services**: `docker-compose ps locust-master locust-worker`
2. **Check Locust logs**: `docker-compose logs -f locust-master`
3. **Restart Locust**: `docker-compose restart locust-master locust-worker`
4. **Rebuild Locust**: `docker-compose build locust-master locust-worker`
5. **Check port availability**: `netstat -an | grep 8089`
6. **Test Locust specifically**: `python test_locust.py`

Common Locust issues:
- **Port 8089 already in use**: Stop other services using this port
- **Workers not connecting**: Check network connectivity between master and workers
- **API endpoint unreachable**: Ensure api_launcher is running and accessible

### Build Issues

If you encounter build failures:

1. **Locust build fails**: The Locust image doesn't support `apt-get` operations
   - **Solution**: Use the simplified Dockerfile (already fixed)
   - **Alternative**: `docker-compose build --no-cache locust-master locust-worker`

2. **Permission errors**: Some Docker images run as non-root users
   - **Solution**: Avoid using `apt-get` in Dockerfiles
   - **Alternative**: Use Python-based alternatives for system tools

3. **Port conflicts**: Services trying to bind to already-used ports
   - **Solution**: Stop conflicting services or change ports
   - **Check**: `netstat -an | grep <port_number>`

4. **Memory issues**: Docker running out of memory during build
   - **Solution**: Increase Docker memory allocation
   - **Alternative**: Build services individually: `docker-compose build <service_name>`

## System Flow

1. **Launch**: API receives missile launch request
2. **Track**: track_sim receives missile data via ZeroMQ and simulates trajectory
3. **Detect**: radar_site detects missiles within range and publishes to NATS
4. **Correlate**: command_center correlates multiple radar detections
5. **Intercept**: command_center orders battery to fire interceptor
6. **Destroy**: interceptor_sim simulates intercept and publishes detonation

## Metrics

The system exposes Prometheus metrics for:
- Missile launches
- Radar detections
- Intercept orders
- Battery fires
- Successful intercepts
- Correlation latency

## Development

To modify the system:

1. Edit the Python files in each service directory
2. Rebuild the affected service: `docker-compose build <service_name>`
3. Restart the service: `docker-compose restart <service_name>`

## Load Testing

The system includes Locust for load testing:
- Master: http://localhost:8089
- Workers: 3 replicas for distributed load testing

## ZeroMQ Ports

- **5556**: api_launcher → track_sim (missile launches)
- **5557**: track_sim → radar_site (track updates)
- **5558**: command_center → battery_sim (intercept orders) 