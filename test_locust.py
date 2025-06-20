#!/usr/bin/env python3
"""
Test script for Locust load testing
"""
import requests
import time
import subprocess

def check_locust_ui():
    """Check if Locust UI is accessible"""
    print("🔍 Checking Locust UI...")
    
    try:
        response = requests.get("http://localhost:8089/", timeout=10)
        if response.status_code == 200:
            print("✅ Locust UI is accessible")
            return True
        else:
            print(f"❌ Locust UI returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Locust UI not accessible: {e}")
        return False

def check_locust_services():
    """Check Locust Docker services"""
    print("\n🐳 Checking Locust services...")
    
    try:
        result = subprocess.run(
            ["docker-compose", "ps", "locust-master", "locust-worker"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            print("Locust services status:")
            print(result.stdout)
            
            # Check if services are running
            if "Up" in result.stdout:
                print("✅ Locust services are running")
                return True
            else:
                print("❌ Locust services are not running")
                return False
        else:
            print(f"Error checking Locust services: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error running docker-compose: {e}")
        return False

def test_api_endpoint():
    """Test the API endpoint that Locust will target"""
    print("\n🚀 Testing API endpoint...")
    
    try:
        response = requests.post(
            "http://localhost:9000/launch",
            params={
                "lat": 36.5,
                "lon": -123.1,
                "targetLat": 34.05,
                "targetLon": -118.25,
                "missileType": "SCUD-C"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API endpoint working: {result}")
            return True
        else:
            print(f"❌ API endpoint failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ API endpoint error: {e}")
        return False

def main():
    print("🚀 Locust Load Testing Debug")
    print("=" * 40)
    
    # Check if API is working
    api_ok = test_api_endpoint()
    
    # Check Locust services
    services_ok = check_locust_services()
    
    # Check Locust UI
    ui_ok = check_locust_ui()
    
    print(f"\n📊 Summary:")
    print(f"✅ API endpoint: {'Working' if api_ok else 'Failed'}")
    print(f"✅ Locust services: {'Running' if services_ok else 'Failed'}")
    print(f"✅ Locust UI: {'Accessible' if ui_ok else 'Failed'}")
    
    if not ui_ok:
        print(f"\n🔧 Troubleshooting Locust UI:")
        print("1. Check if services are running: docker-compose ps")
        print("2. Check Locust logs: docker-compose logs -f locust-master")
        print("3. Restart Locust: docker-compose restart locust-master locust-worker")
        print("4. Rebuild Locust: docker-compose build locust-master locust-worker")
        print("5. Check if port 8089 is available: netstat -an | grep 8089")
        
        print(f"\n💡 Manual Locust start:")
        print("docker-compose exec locust-master locust -f locustfile.py --host=http://api_launcher:9000")
    
    if api_ok and services_ok and ui_ok:
        print(f"\n🎉 Locust is ready!")
        print("Access the UI at: http://localhost:8089")
        print("Default settings: 1 user, 1 spawn rate")

if __name__ == "__main__":
    main() 