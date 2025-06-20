#!/usr/bin/env python3
"""
Simple health check script for Locust
"""
import requests
import sys

def check_locust_health():
    """Check if Locust web interface is responding"""
    try:
        response = requests.get("http://localhost:8089/", timeout=5)
        if response.status_code == 200:
            print("Locust is healthy")
            return 0
        else:
            print(f"Locust returned status code: {response.status_code}")
            return 1
    except Exception as e:
        print(f"Locust health check failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(check_locust_health()) 