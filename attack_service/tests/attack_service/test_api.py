"""
Unit tests for the Attack Service API
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from attack_service.api import AttackServiceAPI, ArmRequest, LaunchRequest, InstallationRequest
from attack_service.messaging import MessagingService


@pytest.mark.unit
class TestAttackServiceAPI:
    """Test cases for AttackServiceAPI"""
    
    @pytest.fixture
    def mock_messaging_service(self):
        """Create a mock messaging service"""
        mock = AsyncMock(spec=MessagingService)
        return mock
    
    @pytest.fixture
    def api_service(self, mock_messaging_service):
        """Create API service with mocked messaging"""
        return AttackServiceAPI(mock_messaging_service)
    
    @pytest.fixture
    def client(self, api_service):
        """Create test client"""
        return TestClient(api_service.app)
    
    def test_root_endpoint(self, client):
        """Test the root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Missile Defense Attack Service v2.0"
        assert data["status"] == "operational"
    
    @pytest.mark.asyncio
    async def test_get_platforms(self, api_service, mock_messaging_service):
        """Test getting platforms"""
        expected_platforms = [
            {"id": 1, "nickname": "Patriot", "category": "SAM"},
            {"id": 2, "nickname": "THAAD", "category": "ABM"}
        ]
        mock_messaging_service.get_platforms.return_value = expected_platforms
        
        response = await api_service.app.get("/platforms")
        assert response.status_code == 200
        assert response.json() == expected_platforms
        mock_messaging_service.get_platforms.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_installations(self, api_service, mock_messaging_service):
        """Test getting installations"""
        expected_installations = [
            {"id": 1, "callsign": "ALPHA-1", "platform_nickname": "Patriot"},
            {"id": 2, "callsign": "BRAVO-1", "platform_nickname": "THAAD"}
        ]
        mock_messaging_service.get_installations.return_value = expected_installations
        
        response = await api_service.app.get("/installations")
        assert response.status_code == 200
        assert response.json() == expected_installations
        mock_messaging_service.get_installations.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_installation_success(self, api_service, mock_messaging_service):
        """Test successful installation creation"""
        request_data = {
            "platform_nickname": "Patriot",
            "callsign": "ALPHA-1",
            "lat": 40.7128,
            "lon": -74.0060,
            "altitude_m": 100,
            "is_mobile": False,
            "ammo_count": 10
        }
        expected_response = {
            "installation_id": 1,
            "callsign": "ALPHA-1",
            "status": "created"
        }
        mock_messaging_service.create_installation.return_value = expected_response
        
        response = await api_service.app.post("/installations", json=request_data)
        assert response.status_code == 200
        assert response.json() == expected_response
        mock_messaging_service.create_installation.assert_called_once_with(
            platform_nickname="Patriot",
            callsign="ALPHA-1",
            lat=40.7128,
            lon=-74.0060,
            altitude_m=100,
            is_mobile=False,
            ammo_count=10
        )
    
    @pytest.mark.asyncio
    async def test_create_installation_validation_error(self, api_service, mock_messaging_service):
        """Test installation creation with validation error"""
        request_data = {
            "platform_nickname": "InvalidPlatform",
            "callsign": "ALPHA-1",
            "lat": 40.7128,
            "lon": -74.0060
        }
        mock_messaging_service.create_installation.side_effect = ValueError("Platform InvalidPlatform not found")
        
        response = await api_service.app.post("/installations", json=request_data)
        assert response.status_code == 400
        assert "Platform InvalidPlatform not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_create_installation_server_error(self, api_service, mock_messaging_service):
        """Test installation creation with server error"""
        request_data = {
            "platform_nickname": "Patriot",
            "callsign": "ALPHA-1",
            "lat": 40.7128,
            "lon": -74.0060
        }
        mock_messaging_service.create_installation.side_effect = Exception("Database error")
        
        response = await api_service.app.post("/installations", json=request_data)
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_delete_installation_success(self, api_service, mock_messaging_service):
        """Test successful installation deletion"""
        expected_response = {
            "callsign": "ALPHA-1",
            "status": "deleted"
        }
        mock_messaging_service.delete_installation.return_value = expected_response
        
        response = await api_service.app.delete("/installations/ALPHA-1")
        assert response.status_code == 200
        assert response.json()["message"] == "Installation ALPHA-1 deleted successfully"
        mock_messaging_service.delete_installation.assert_called_once_with("ALPHA-1")
    
    @pytest.mark.asyncio
    async def test_delete_installation_not_found(self, api_service, mock_messaging_service):
        """Test deletion of non-existent installation"""
        mock_messaging_service.delete_installation.side_effect = ValueError("Installation ALPHA-1 not found")
        
        response = await api_service.app.delete("/installations/ALPHA-1")
        assert response.status_code == 404
        assert "Installation ALPHA-1 not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_delete_all_installations(self, api_service, mock_messaging_service):
        """Test deletion of all installations"""
        mock_messaging_service.delete_all_installations.return_value = {
            "deleted_count": 5,
            "status": "all_deleted"
        }
        
        response = await api_service.app.delete("/installations")
        assert response.status_code == 200
        assert response.json()["message"] == "All installations deleted successfully"
        mock_messaging_service.delete_all_installations.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_arm_launcher_success(self, api_service, mock_messaging_service):
        """Test successful launcher arming"""
        request_data = {
            "launcher_callsign": "ALPHA-1",
            "munition_nickname": "PAC-3",
            "quantity": 5
        }
        expected_response = {
            "launcher_callsign": "ALPHA-1",
            "munition_nickname": "PAC-3",
            "status": "armed",
            "added_quantity": 5
        }
        mock_messaging_service.arm_launcher.return_value = expected_response
        
        response = await api_service.app.post("/arm", json=request_data)
        assert response.status_code == 200
        assert response.json() == expected_response
        mock_messaging_service.arm_launcher.assert_called_once_with(
            launcher_callsign="ALPHA-1",
            munition_nickname="PAC-3",
            quantity=5
        )
    
    @pytest.mark.asyncio
    async def test_arm_launcher_validation_error(self, api_service, mock_messaging_service):
        """Test launcher arming with validation error"""
        request_data = {
            "launcher_callsign": "INVALID-1",
            "munition_nickname": "PAC-3",
            "quantity": 5
        }
        mock_messaging_service.arm_launcher.side_effect = ValueError("Launcher with callsign INVALID-1 not found")
        
        response = await api_service.app.post("/arm", json=request_data)
        assert response.status_code == 400
        assert "Launcher with callsign INVALID-1 not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_launch_missile_success(self, api_service, mock_messaging_service):
        """Test successful missile launch"""
        request_data = {
            "launcher_callsign": "ALPHA-1",
            "munition_nickname": "PAC-3",
            "target_lat": 40.7128,
            "target_lon": -74.0060,
            "target_alt": 1000
        }
        expected_response = {
            "missile_id": "MISSILE-001",
            "status": "launched",
            "target": [40.7128, -74.0060, 1000]
        }
        mock_messaging_service.launch_missile.return_value = expected_response
        
        response = await api_service.app.post("/launch", json=request_data)
        assert response.status_code == 200
        assert response.json() == expected_response
        mock_messaging_service.launch_missile.assert_called_once_with(
            launcher_callsign="ALPHA-1",
            munition_nickname="PAC-3",
            target_lat=40.7128,
            target_lon=-74.0060,
            target_alt=1000
        )
    
    @pytest.mark.asyncio
    async def test_launch_missile_validation_error(self, api_service, mock_messaging_service):
        """Test missile launch with validation error"""
        request_data = {
            "launcher_callsign": "ALPHA-1",
            "munition_nickname": "PAC-3",
            "target_lat": 40.7128,
            "target_lon": -74.0060
        }
        mock_messaging_service.launch_missile.side_effect = ValueError("Insufficient ammunition")
        
        response = await api_service.app.post("/launch", json=request_data)
        assert response.status_code == 400
        assert "Insufficient ammunition" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_active_missiles(self, api_service, mock_messaging_service):
        """Test getting active missiles"""
        expected_missiles = [
            {"missile_id": "MISSILE-001", "status": "active", "position": [100, 200, 1000]},
            {"missile_id": "MISSILE-002", "status": "active", "position": [150, 250, 1200]}
        ]
        mock_messaging_service.get_active_missiles.return_value = expected_missiles
        
        response = await api_service.app.get("/missiles/active")
        assert response.status_code == 200
        assert response.json() == expected_missiles
        mock_messaging_service.get_active_missiles.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_recent_detections(self, api_service, mock_messaging_service):
        """Test getting recent detections"""
        expected_detections = [
            {"id": 1, "event_type": "detection", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": 2, "event_type": "detection", "timestamp": "2024-01-01T12:01:00Z"}
        ]
        mock_messaging_service.get_recent_detections.return_value = expected_detections
        
        response = await api_service.app.get("/detections/recent?limit=10")
        assert response.status_code == 200
        assert response.json() == expected_detections
        mock_messaging_service.get_recent_detections.assert_called_once_with(10)
    
    @pytest.mark.asyncio
    async def test_get_recent_engagements(self, api_service, mock_messaging_service):
        """Test getting recent engagements"""
        expected_engagements = [
            {"id": 1, "event_type": "engagement", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": 2, "event_type": "engagement", "timestamp": "2024-01-01T12:01:00Z"}
        ]
        mock_messaging_service.get_recent_engagements.return_value = expected_engagements
        
        response = await api_service.app.get("/engagements/recent?limit=20")
        assert response.status_code == 200
        assert response.json() == expected_engagements
        mock_messaging_service.get_recent_engagements.assert_called_once_with(20)
    
    @pytest.mark.asyncio
    async def test_get_recent_detonations(self, api_service, mock_messaging_service):
        """Test getting recent detonations"""
        expected_detonations = [
            {"id": 1, "event_type": "detonation", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": 2, "event_type": "detonation", "timestamp": "2024-01-01T12:01:00Z"}
        ]
        mock_messaging_service.get_recent_detonations.return_value = expected_detonations
        
        response = await api_service.app.get("/detonations/recent")
        assert response.status_code == 200
        assert response.json() == expected_detonations
        mock_messaging_service.get_recent_detonations.assert_called_once_with(50)  # default limit
    
    @pytest.mark.asyncio
    async def test_health_check(self, api_service, mock_messaging_service):
        """Test health check endpoint"""
        expected_health = {
            "status": "healthy",
            "database": "connected",
            "nats": "connected"
        }
        mock_messaging_service.health_check.return_value = expected_health
        
        response = await api_service.app.get("/health")
        assert response.status_code == 200
        assert response.json() == expected_health
        mock_messaging_service.health_check.assert_called_once()


@pytest.mark.unit
class TestPydanticModels:
    """Test cases for Pydantic models"""
    
    def test_arm_request_valid(self):
        """Test valid ArmRequest"""
        data = {
            "launcher_callsign": "ALPHA-1",
            "munition_nickname": "PAC-3",
            "quantity": 5
        }
        request = ArmRequest(**data)
        assert request.launcher_callsign == "ALPHA-1"
        assert request.munition_nickname == "PAC-3"
        assert request.quantity == 5
    
    def test_launch_request_valid(self):
        """Test valid LaunchRequest"""
        data = {
            "launcher_callsign": "ALPHA-1",
            "munition_nickname": "PAC-3",
            "target_lat": 40.7128,
            "target_lon": -74.0060,
            "target_alt": 1000
        }
        request = LaunchRequest(**data)
        assert request.launcher_callsign == "ALPHA-1"
        assert request.munition_nickname == "PAC-3"
        assert request.target_lat == 40.7128
        assert request.target_lon == -74.0060
        assert request.target_alt == 1000
    
    def test_launch_request_default_altitude(self):
        """Test LaunchRequest with default altitude"""
        data = {
            "launcher_callsign": "ALPHA-1",
            "munition_nickname": "PAC-3",
            "target_lat": 40.7128,
            "target_lon": -74.0060
        }
        request = LaunchRequest(**data)
        assert request.target_alt == 0  # default value
    
    def test_installation_request_valid(self):
        """Test valid InstallationRequest"""
        data = {
            "platform_nickname": "Patriot",
            "callsign": "ALPHA-1",
            "lat": 40.7128,
            "lon": -74.0060,
            "altitude_m": 100,
            "is_mobile": False,
            "ammo_count": 10
        }
        request = InstallationRequest(**data)
        assert request.platform_nickname == "Patriot"
        assert request.callsign == "ALPHA-1"
        assert request.lat == 40.7128
        assert request.lon == -74.0060
        assert request.altitude_m == 100
        assert request.is_mobile is False
        assert request.ammo_count == 10
    
    def test_installation_request_defaults(self):
        """Test InstallationRequest with default values"""
        data = {
            "platform_nickname": "Patriot",
            "callsign": "ALPHA-1",
            "lat": 40.7128,
            "lon": -74.0060
        }
        request = InstallationRequest(**data)
        assert request.altitude_m == 0
        assert request.is_mobile is False
        assert request.ammo_count == 0 