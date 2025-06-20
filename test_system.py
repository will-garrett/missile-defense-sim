#!/usr/bin/env python3
"""
Simple test script for the missile defense system
"""
import requests
import time
import json

def test_missile_launch():
    """Test launching a missile"""
    print("Testing missile launch...")
    
    # Launch coordinates (Los Angeles area)
    launch_data = {
        "lat": 34.0522,
        "lon": -118.2437,
        "targetLat": 33.7490,
        "targetLon": -84.3880,
        "missileType": "SCUD-C"
    }
    
    try:
        response = requests.post("http://localhost:9000/launch", params=launch_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Missile launched successfully: {result}")
            return result.get("missile_id")
        else:
            print(f"❌ Failed to launch missile: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error launching missile: {e}")
        return None

def test_metrics():
    """Test that metrics endpoints are working"""
    print("\nTesting metrics endpoints...")
    
    services = [
        ("api_launcher", "http://localhost:8003/metrics"),
        ("track_sim", "http://localhost:8004/metrics"),
        ("command_center", "http://localhost:8005/metrics"),
        ("battery_sim", "http://localhost:8006/metrics"),
        ("interceptor_sim", "http://localhost:8007/metrics"),
    ]
    
    for service_name, url in services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {service_name}: metrics available")
            else:
                print(f"❌ {service_name}: metrics failed ({response.status_code})")
        except Exception as e:
            print(f"❌ {service_name}: metrics error - {e}")

def main():
    print("🚀 Missile Defense System Test")
    print("=" * 40)
    
    # Wait a bit for services to start
    print("Waiting for services to be ready...")
    time.sleep(5)
    
    # Test metrics first
    test_metrics()
    
    # Test missile launch
    missile_id = test_missile_launch()
    
    if missile_id:
        print(f"\n🎯 Missile {missile_id} launched! Watch the logs for:")
        print("  - Track simulation updates")
        print("  - Radar detections")
        print("  - Command center intercept orders")
        print("  - Battery firing")
        print("  - Interceptor detonations")
        
        print(f"\n📊 Check metrics at:")
        print("  - Prometheus: http://localhost:9090")
        print("  - Grafana: http://localhost:3000 (admin/admin)")
        print("  - PgAdmin: http://localhost:8080 (admin@missilesim.com/admin123)")
        
        print(f"\n🔍 Monitor logs with: docker-compose logs -f")
    else:
        print("\n❌ System test failed. Check docker-compose logs for errors.")

if __name__ == "__main__":
    main() 