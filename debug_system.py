#!/usr/bin/env python3
"""
Debug script for the missile defense system
"""
import requests
import time
import json
import subprocess
import sys

def check_service_health():
    """Check if all services are responding"""
    print("🔍 Checking service health...")
    
    services = [
        ("simulation_service", "http://localhost:8001/health", "GET"),
        ("attack_service", "http://localhost:9000/health", "GET"),
        ("command_center", "http://localhost:8005/health", "GET"),
        ("radar_service", "http://localhost:8006/health", "GET"),
        ("battery_sim", "http://localhost:8007/health", "GET"),
        ("dashboard", "http://localhost:8089/health", "GET"),
    ]
    
    healthy_services = []
    failed_services = []
    
    for service_name, url, method in services:
        try:
            if method == "GET":
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, params={"lat": 0, "lon": 0, "targetLat": 0, "targetLon": 0}, timeout=5)
            
            if response.status_code in [200, 405]:  # 405 is OK for POST to GET endpoint
                print(f"✅ {service_name}: Healthy")
                healthy_services.append(service_name)
            else:
                print(f"❌ {service_name}: HTTP {response.status_code}")
                failed_services.append(service_name)
        except Exception as e:
            print(f"❌ {service_name}: {e}")
            failed_services.append(service_name)
    
    return healthy_services, failed_services

def check_docker_services():
    """Check Docker service status"""
    print("\n🐳 Checking Docker services...")
    
    try:
        result = subprocess.run(
            ["docker-compose", "ps"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            print("Docker services status:")
            print(result.stdout)
        else:
            print(f"Error checking Docker services: {result.stderr}")
            
    except Exception as e:
        print(f"Error running docker-compose: {e}")

def check_database():
    """Check database connectivity"""
    print("\n🗄️ Checking database connectivity...")
    
    try:
        result = subprocess.run(
            ["docker-compose", "exec", "-T", "postgres", "pg_isready", "-U", "missiles", "-d", "missilesim"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Database is ready")
        else:
            print(f"❌ Database not ready: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")

def check_nats():
    """Check NATS connectivity"""
    print("\n📡 Checking NATS connectivity...")
    
    try:
        result = subprocess.run(
            ["docker-compose", "exec", "-T", "nats", "nats-server", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ NATS is running")
        else:
            print(f"❌ NATS not responding: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error checking NATS: {e}")

def check_prometheus_metrics():
    """Check Prometheus metrics endpoints"""
    print("\n📊 Checking Prometheus metrics endpoints...")
    
    metrics_services = [
        ("simulation_service", "http://localhost:8001/metrics"),
        ("attack_service", "http://localhost:8003/metrics"),
        ("command_center", "http://localhost:8005/metrics"),
        ("radar_service", "http://localhost:8006/metrics"),
        ("battery_sim", "http://localhost:8007/metrics"),
        ("dashboard", "http://localhost:8089/metrics"),
    ]
    
    for service_name, url in metrics_services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {service_name}: Metrics available")
            else:
                print(f"⚠️ {service_name}: Metrics returned HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {service_name}: Metrics not accessible - {e}")

def main():
    print("🚀 Missile Defense System Debug")
    print("=" * 40)
    
    # Check Docker services
    check_docker_services()
    
    # Check infrastructure
    check_database()
    check_nats()
    
    # Check application services
    healthy, failed = check_service_health()
    
    # Check Prometheus metrics
    check_prometheus_metrics()
    
    print(f"\n📊 Summary:")
    print(f"✅ Healthy services: {len(healthy)}")
    print(f"❌ Failed services: {len(failed)}")
    
    if failed:
        print(f"\n🔧 Failed services: {', '.join(failed)}")
        print("\n💡 Troubleshooting tips:")
        print("1. Check logs: docker-compose logs -f <service_name>")
        print("2. Restart services: docker-compose restart <service_name>")
        print("3. Rebuild services: docker-compose build <service_name>")
        print("4. Check resource usage: docker stats")
    else:
        print("\n🎉 All services are healthy!")
        print("You can now test the system with: python test_system.py")
        print("Access Prometheus UI at: http://localhost:8001/metrics")
        print("Access test runner at: http://localhost:8089")

if __name__ == "__main__":
    main() 