#!/usr/bin/env python3
"""
Test runner for Attack Service
"""
import sys
import subprocess
import os
from pathlib import Path


def run_tests():
    """Run all tests for the attack service"""
    print("🚀 Running Attack Service Tests")
    print("=" * 50)
    
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Run pytest with coverage using pyproject.toml configuration
    cmd = [
        sys.executable, "-m", "pytest",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-report=xml:coverage.xml",
        "-v",
        "--tb=short"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ All tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code {e.returncode}")
        return e.returncode


def run_unit_tests():
    """Run only unit tests"""
    print("🧪 Running Unit Tests")
    print("=" * 30)
    
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "unit",
        "-v",
        "--tb=short"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ Unit tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Unit tests failed with exit code {e.returncode}")
        return e.returncode


def run_integration_tests():
    """Run only integration tests"""
    print("🔗 Running Integration Tests")
    print("=" * 35)
    
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "integration",
        "-v",
        "--tb=short"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ Integration tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Integration tests failed with exit code {e.returncode}")
        return e.returncode


def run_lint():
    """Run linting checks"""
    print("🔍 Running Linting Checks")
    print("=" * 30)
    
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    cmd = [
        sys.executable, "-m", "tox", "-e", "lint"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ Linting passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Linting failed with exit code {e.returncode}")
        return e.returncode


def run_tox():
    """Run tox for all environments"""
    print("🧪 Running Tox Tests")
    print("=" * 25)
    
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    cmd = [
        sys.executable, "-m", "tox"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ Tox tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tox tests failed with exit code {e.returncode}")
        return e.returncode


def install_dev():
    """Install the package in development mode"""
    print("📦 Installing in Development Mode")
    print("=" * 35)
    
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    cmd = [
        sys.executable, "-m", "pip", "install", "-e", ".[test]"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ Development installation complete!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Installation failed with exit code {e.returncode}")
        return e.returncode


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "unit":
            return run_unit_tests()
        elif command == "integration":
            return run_integration_tests()
        elif command == "lint":
            return run_lint()
        elif command == "tox":
            return run_tox()
        elif command == "install":
            return install_dev()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: unit, integration, lint, tox, install")
            return 1
    else:
        return run_tests()


if __name__ == "__main__":
    sys.exit(main()) 