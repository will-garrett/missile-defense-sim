#!/usr/bin/env python3
"""
Build script for the missile defense system
"""
import subprocess
import sys
import time

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔨 {description}...")
    print(f"Running: {command}")
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def main():
    print("🚀 Missile Defense System Build")
    print("=" * 40)
    
    # Step 1: Stop any running containers
    print("\n📋 Step 1: Stopping existing containers...")
    run_command("docker-compose down", "Stopping containers")
    
    # Step 2: Build Locust first (since it was failing)
    print("\n📋 Step 2: Building Locust services...")
    if not run_command("docker-compose build locust-master locust-worker", "Building Locust services"):
        print("❌ Locust build failed. Trying alternative approach...")
        
        # Try building without cache
        if not run_command("docker-compose build --no-cache locust-master locust-worker", "Building Locust services (no cache)"):
            print("❌ Locust build still failed. Check the error messages above.")
            return False
    
    # Step 3: Build all other services
    print("\n📋 Step 3: Building all other services...")
    if not run_command("docker-compose build", "Building all services"):
        print("❌ Build failed. Check the error messages above.")
        return False
    
    # Step 4: Start the system
    print("\n📋 Step 4: Starting the system...")
    if not run_command("docker-compose up -d", "Starting system"):
        print("❌ Failed to start system. Check the error messages above.")
        return False
    
    # Step 5: Wait for services to start
    print("\n📋 Step 5: Waiting for services to start...")
    print("Waiting 30 seconds for services to initialize...")
    time.sleep(30)
    
    # Step 6: Check system health
    print("\n📋 Step 6: Checking system health...")
    if not run_command("python debug_system.py", "Checking system health"):
        print("⚠️ System health check failed. Some services may still be starting.")
    
    print("\n🎉 Build process completed!")
    print("\n📊 Next steps:")
    print("1. Check system status: python debug_system.py")
    print("2. Test the system: python test_system.py")
    print("3. Access Locust UI: http://localhost:8089")
    print("4. View logs: docker-compose logs -f")

if __name__ == "__main__":
    main() 