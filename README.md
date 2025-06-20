# Missile Defense Simulation System

A comprehensive, physics-based missile defense simulation system that models realistic missile attacks, detection, and counter-defense coordination using distributed microservices.

## 🎯 Overview

This system simulates a complete missile defense scenario including:

- **Attack Scenarios**: Launch missile attacks from various platforms.
- **Detection Systems**: Radar installations for tracking and detection.
- **Counter-Defense**: Anti-ballistic missile batteries for interception.
- **Command & Control**: Centralized threat assessment and engagement coordination.
- **Realistic Physics**: Atmospheric effects, gravity, and trajectory calculations.
- **Web Interface**: A comprehensive UI for testing, monitoring, and real-time visualization.

## 🏗️ Architecture

The system is built on a microservices architecture, with each service responsible for a specific domain. Communication between services is handled by a NATS message broker, and system metrics are collected by Prometheus.

### System Architecture Diagram

```mermaid
graph TD
    subgraph "User Interface"
        WebApp[Test Runner UI<br/>(Flask & TailwindCSS)]
    end

    subgraph "Core Services"
        AttackSvc[attack_service<br/>Manages missile launches]
        SimSvc[simulation_service<br/>Physics & trajectory engine]
        RadarSvc[radar_service<br/>Detects and tracks missiles]
        CommandSvc[command_center<br/>Coordinates defense]
        BatterySvc[battery_sim<br/>Fires interceptors]
    end

    subgraph "Infrastructure"
        NATS[NATS<br/>Message Broker]
        Postgres[PostgreSQL<br/>Spatial Database]
        Prometheus[Prometheus<br/>Metrics & Monitoring]
    end

    WebApp -->|HTTP API| AttackSvc
    AttackSvc -->|NATS| SimSvc
    SimSvc -->|NATS| RadarSvc
    RadarSvc -->|NATS| CommandSvc
    CommandSvc -->|NATS| BatterySvc
    BatterySvc -->|NATS| SimSvc

    SimSvc -->|DB| Postgres
    RadarSvc -->|DB| Postgres
    CommandSvc -->|DB| Postgres
    
    AttackSvc -->|Metrics| Prometheus
    SimSvc -->|Metrics| Prometheus
    RadarSvc -->|Metrics| Prometheus
    CommandSvc -->|Metrics| Prometheus
    BatterySvc -->|Metrics| Prometheus
```

### Services

-   **`test_running`**: A Flask-based web interface for running test scenarios, monitoring system status, and visualizing engagements in real-time.
-   **`attack_service`**: Manages missile launch scenarios and communicates launch events to the simulation service.
-   **`simulation_service`**: The core physics engine that calculates missile trajectories and outcomes.
-   **`radar_service`**: Simulates radar installations that detect and track missiles.
-   **`command_center`**: Assesses threats detected by the radar service and coordinates defensive actions.
-   **`battery_sim`**: Simulates missile defense batteries that fire interceptors based on commands from the command center.

## 🚀 Getting Started

To run the simulation, use Docker Compose:

```bash
docker-compose up --build
```

This will build and start all the services. You can then access the web interface at `http://localhost:8080`.

## 🖥️ Web Interface

The web interface provides a centralized platform for interacting with the simulation.

### Features

-   **Dashboard**: An overview of the system's status and recent activity.
-   **Scenarios**: A list of available test scenarios that can be launched with a single click.
-   **Status**: A detailed view of the system's health, running tests, and performance metrics.
-   **Real-time Map**: A live map that visualizes missile trajectories, intercepts, and other key events.
-   **Theme Switching**: A light/dark mode theme switcher for improved usability.