"""
Unit tests for the Attack Service Messaging
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import asyncpg
import nats
from nats.aio.client import Client as NATS

from attack_service.messaging import MessagingService, MissileState


@pytest.mark.unit
class TestMissileState:
    """Test cases for MissileState class"""
    
    def test_missile_state_creation(self):
        """Test creating a MissileState instance"""
        position = [100, 200, 1000]
        velocity = [50, 25, 0]
        target = [150, 225, 0]
        
        missile = MissileState(
            missile_id="MISSILE-001",
            position=position,
            velocity=velocity,
            target=target,
            fuel_remaining=100.0
        )
        
        assert missile.missile_id == "MISSILE-001"
        assert missile.position == position
        assert missile.velocity == velocity
        assert missile.target == target
        assert missile.fuel_remaining == 100.0
        assert missile.status == "active"  # default value
    
    def test_missile_state_with_custom_status(self):
        """Test creating a MissileState with custom status"""
        missile = MissileState(
            missile_id="MISSILE-001",
            position=[0, 0, 0],
            velocity=[0, 0, 0],
            target=[0, 0, 0],
            fuel_remaining=0.0,
            status="destroyed"
        )
        
        assert missile.status == "destroyed"


@pytest.mark.unit
class TestMessagingService:
    """Test cases for MessagingService"""
    
    @pytest.fixture
    def messaging_service(self):
        """Create a MessagingService instance"""
        return MessagingService("postgresql://test:test@localhost/test", "nats://localhost:4222")
    
    @pytest.fixture
    def mock_db_pool(self):
        """Create a mock database pool"""
        return AsyncMock(spec=asyncpg.Pool)
    
    @pytest.fixture
    def mock_nats_client(self):
        """Create a mock NATS client"""
        return AsyncMock(spec=NATS)
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, messaging_service, mock_db_pool, mock_nats_client):
        """Test successful initialization"""
        with patch('asyncpg.create_pool', return_value=mock_db_pool), \
             patch('nats.aio.client.Client', return_value=mock_nats_client):
            
            await messaging_service.initialize()
            
            assert messaging_service.db_pool == mock_db_pool
            assert messaging_service.nats_client == mock_nats_client
            mock_nats_client.connect.assert_called_once_with("nats://localhost:4222")
            assert messaging_service.simulation_task is not None
    
    @pytest.mark.asyncio
    async def test_initialize_db_retry_success(self, messaging_service, mock_db_pool, mock_nats_client):
        """Test database connection with retry logic"""
        with patch('asyncpg.create_pool', side_effect=[Exception("Connection failed"), mock_db_pool]), \
             patch('nats.aio.client.Client', return_value=mock_nats_client), \
             patch('asyncio.sleep', new_callable=AsyncMock):
            
            await messaging_service.initialize()
            
            assert messaging_service.db_pool == mock_db_pool
    
    @pytest.mark.asyncio
    async def test_initialize_db_retry_failure(self, messaging_service):
        """Test database connection retry failure"""
        with patch('asyncpg.create_pool', side_effect=Exception("Connection failed")), \
             patch('asyncio.sleep', new_callable=AsyncMock):
            
            with pytest.raises(Exception, match="Failed to connect to database after all retries"):
                await messaging_service.initialize()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, messaging_service, mock_db_pool, mock_nats_client):
        """Test shutdown method"""
        messaging_service.db_pool = mock_db_pool
        messaging_service.nats_client = mock_nats_client
        messaging_service.simulation_task = asyncio.create_task(asyncio.sleep(1))
        
        await messaging_service.shutdown()
        
        mock_nats_client.close.assert_called_once()
        mock_db_pool.close.assert_called_once()
        assert messaging_service.simulation_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_get_platforms(self, messaging_service, mock_db_pool):
        """Test getting platforms from database"""
        messaging_service.db_pool = mock_db_pool
        
        expected_platforms = [
            {"id": 1, "nickname": "Patriot", "category": "SAM"},
            {"id": 2, "nickname": "THAAD", "category": "ABM"}
        ]
        
        mock_con = AsyncMock()
        mock_con.fetch.return_value = [
            MagicMock(**platform) for platform in expected_platforms
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.get_platforms()
        
        assert result == expected_platforms
        mock_con.fetch.assert_called_once_with(
            "SELECT * FROM platform_type ORDER BY category, nickname"
        )
    
    @pytest.mark.asyncio
    async def test_get_installations(self, messaging_service, mock_db_pool):
        """Test getting installations from database"""
        messaging_service.db_pool = mock_db_pool
        
        expected_installations = [
            {"id": 1, "callsign": "ALPHA-1", "platform_nickname": "Patriot"},
            {"id": 2, "callsign": "BRAVO-1", "platform_nickname": "THAAD"}
        ]
        
        mock_con = AsyncMock()
        mock_con.fetch.return_value = [
            MagicMock(**installation) for installation in expected_installations
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.get_installations()
        
        assert result == expected_installations
        mock_con.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_installation_success(self, messaging_service, mock_db_pool):
        """Test successful installation creation"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.side_effect = [1, None, 123]  # platform_id, existing_check, installation_id
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.create_installation(
            platform_nickname="Patriot",
            callsign="ALPHA-1",
            lat=40.7128,
            lon=-74.0060,
            altitude_m=100
        )
        
        expected_result = {
            "installation_id": 123,
            "callsign": "ALPHA-1",
            "status": "created"
        }
        assert result == expected_result
        
        # Verify database calls
        assert mock_con.fetchval.call_count == 3
        mock_con.fetchval.assert_any_call(
            "SELECT id FROM platform_type WHERE nickname = $1", "Patriot"
        )
        mock_con.fetchval.assert_any_call(
            "SELECT id FROM installation WHERE callsign = $1", "ALPHA-1"
        )
    
    @pytest.mark.asyncio
    async def test_create_installation_platform_not_found(self, messaging_service, mock_db_pool):
        """Test installation creation with invalid platform"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.return_value = None  # Platform not found
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        with pytest.raises(ValueError, match="Platform InvalidPlatform not found"):
            await messaging_service.create_installation(
                platform_nickname="InvalidPlatform",
                callsign="ALPHA-1",
                lat=40.7128,
                lon=-74.0060
            )
    
    @pytest.mark.asyncio
    async def test_create_installation_callsign_exists(self, messaging_service, mock_db_pool):
        """Test installation creation with existing callsign"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.side_effect = [1, 456]  # platform_id, existing_installation_id
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        with pytest.raises(ValueError, match="Installation with callsign ALPHA-1 already exists"):
            await messaging_service.create_installation(
                platform_nickname="Patriot",
                callsign="ALPHA-1",
                lat=40.7128,
                lon=-74.0060
            )
    
    @pytest.mark.asyncio
    async def test_delete_installation_success(self, messaging_service, mock_db_pool):
        """Test successful installation deletion"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.return_value = 123  # Installation exists
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.delete_installation("ALPHA-1")
        
        expected_result = {
            "callsign": "ALPHA-1",
            "status": "deleted"
        }
        assert result == expected_result
        
        mock_con.fetchval.assert_called_once_with(
            "SELECT id FROM installation WHERE callsign = $1", "ALPHA-1"
        )
        mock_con.execute.assert_called_once_with(
            "DELETE FROM installation WHERE callsign = $1", "ALPHA-1"
        )
    
    @pytest.mark.asyncio
    async def test_delete_installation_not_found(self, messaging_service, mock_db_pool):
        """Test deletion of non-existent installation"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.return_value = None  # Installation not found
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        with pytest.raises(ValueError, match="Installation ALPHA-1 not found"):
            await messaging_service.delete_installation("ALPHA-1")
    
    @pytest.mark.asyncio
    async def test_delete_all_installations(self, messaging_service, mock_db_pool):
        """Test deletion of all installations"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.return_value = 5  # Count before deletion
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.delete_all_installations()
        
        expected_result = {
            "deleted_count": 5,
            "status": "all_deleted"
        }
        assert result == expected_result
        
        mock_con.fetchval.assert_called_once_with("SELECT COUNT(*) FROM installation")
        mock_con.execute.assert_called_once_with("DELETE FROM installation")
    
    @pytest.mark.asyncio
    async def test_arm_launcher_success(self, messaging_service, mock_db_pool):
        """Test successful launcher arming"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.side_effect = [123, 456]  # launcher_id, munition_id
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.arm_launcher(
            launcher_callsign="ALPHA-1",
            munition_nickname="PAC-3",
            quantity=5
        )
        
        expected_result = {
            "launcher_callsign": "ALPHA-1",
            "munition_nickname": "PAC-3",
            "status": "armed",
            "added_quantity": 5
        }
        assert result == expected_result
        
        # Verify database calls
        assert mock_con.fetchval.call_count == 2
        mock_con.fetchval.assert_any_call(
            "SELECT id FROM installation WHERE callsign = $1", "ALPHA-1"
        )
        mock_con.fetchval.assert_any_call(
            "SELECT id FROM munition_type WHERE nickname = $1", "PAC-3"
        )
        mock_con.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_arm_launcher_launcher_not_found(self, messaging_service, mock_db_pool):
        """Test arming non-existent launcher"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.return_value = None  # Launcher not found
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        with pytest.raises(ValueError, match="Launcher with callsign INVALID-1 not found"):
            await messaging_service.arm_launcher(
                launcher_callsign="INVALID-1",
                munition_nickname="PAC-3",
                quantity=5
            )
    
    @pytest.mark.asyncio
    async def test_arm_launcher_munition_not_found(self, messaging_service, mock_db_pool):
        """Test arming with non-existent munition"""
        messaging_service.db_pool = mock_db_pool
        
        mock_con = AsyncMock()
        mock_con.fetchval.side_effect = [123, None]  # launcher_id, munition_not_found
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        with pytest.raises(ValueError, match="Munition with nickname INVALID-MUNITION not found"):
            await messaging_service.arm_launcher(
                launcher_callsign="ALPHA-1",
                munition_nickname="INVALID-MUNITION",
                quantity=5
            )
    
    @pytest.mark.asyncio
    async def test_get_active_missiles(self, messaging_service):
        """Test getting active missiles"""
        # Add some test missiles
        missile1 = MissileState("MISSILE-001", [100, 200, 1000], [50, 25, 0], [150, 225, 0], 80.0)
        missile2 = MissileState("MISSILE-002", [150, 250, 1200], [60, 30, 0], [210, 280, 0], 60.0)
        
        messaging_service.active_missiles = {
            "MISSILE-001": missile1,
            "MISSILE-002": missile2
        }
        
        result = await messaging_service.get_active_missiles()
        
        assert len(result) == 2
        assert result[0]["missile_id"] == "MISSILE-001"
        assert result[1]["missile_id"] == "MISSILE-002"
        assert result[0]["status"] == "active"
        assert result[1]["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_get_recent_detections(self, messaging_service, mock_db_pool):
        """Test getting recent detections"""
        messaging_service.db_pool = mock_db_pool
        
        expected_detections = [
            {"id": 1, "event_type": "detection", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": 2, "event_type": "detection", "timestamp": "2024-01-01T12:01:00Z"}
        ]
        
        mock_con = AsyncMock()
        mock_con.fetch.return_value = [
            MagicMock(**detection) for detection in expected_detections
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.get_recent_detections(limit=10)
        
        assert result == expected_detections
        mock_con.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_recent_engagements(self, messaging_service, mock_db_pool):
        """Test getting recent engagements"""
        messaging_service.db_pool = mock_db_pool
        
        expected_engagements = [
            {"id": 1, "event_type": "engagement", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": 2, "event_type": "engagement", "timestamp": "2024-01-01T12:01:00Z"}
        ]
        
        mock_con = AsyncMock()
        mock_con.fetch.return_value = [
            MagicMock(**engagement) for engagement in expected_engagements
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.get_recent_engagements(limit=20)
        
        assert result == expected_engagements
        mock_con.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_recent_detonations(self, messaging_service, mock_db_pool):
        """Test getting recent detonations"""
        messaging_service.db_pool = mock_db_pool
        
        expected_detonations = [
            {"id": 1, "event_type": "detonation", "timestamp": "2024-01-01T12:00:00Z"},
            {"id": 2, "event_type": "detonation", "timestamp": "2024-01-01T12:01:00Z"}
        ]
        
        mock_con = AsyncMock()
        mock_con.fetch.return_value = [
            MagicMock(**detonation) for detonation in expected_detonations
        ]
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_con
        
        result = await messaging_service.get_recent_detonations(limit=15)
        
        assert result == expected_detonations
        mock_con.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, messaging_service, mock_db_pool, mock_nats_client):
        """Test health check when all services are healthy"""
        messaging_service.db_pool = mock_db_pool
        messaging_service.nats_client = mock_nats_client
        
        # Mock healthy connections
        mock_db_pool.acquire.return_value.__aenter__.return_value = AsyncMock()
        mock_nats_client.is_connected.return_value = True
        
        result = await messaging_service.health_check()
        
        expected_result = {
            "status": "healthy",
            "database": "connected",
            "nats": "connected"
        }
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_health_check_database_unhealthy(self, messaging_service, mock_db_pool, mock_nats_client):
        """Test health check when database is unhealthy"""
        messaging_service.db_pool = mock_db_pool
        messaging_service.nats_client = mock_nats_client
        
        # Mock database failure
        mock_db_pool.acquire.side_effect = Exception("Database connection failed")
        mock_nats_client.is_connected.return_value = True
        
        result = await messaging_service.health_check()
        
        expected_result = {
            "status": "unhealthy",
            "database": "disconnected",
            "nats": "connected"
        }
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_health_check_nats_unhealthy(self, messaging_service, mock_db_pool, mock_nats_client):
        """Test health check when NATS is unhealthy"""
        messaging_service.db_pool = mock_db_pool
        messaging_service.nats_client = mock_nats_client
        
        # Mock healthy database, unhealthy NATS
        mock_db_pool.acquire.return_value.__aenter__.return_value = AsyncMock()
        mock_nats_client.is_connected.return_value = False
        
        result = await messaging_service.health_check()
        
        expected_result = {
            "status": "unhealthy",
            "database": "connected",
            "nats": "disconnected"
        }
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_simulate_missiles_loop(self, messaging_service):
        """Test missile simulation loop"""
        # Add a test missile
        missile = MissileState("MISSILE-001", [100, 200, 1000], [50, 25, 0], [150, 225, 0], 100.0)
        messaging_service.active_missiles["MISSILE-001"] = missile
        
        # Create a task that will be cancelled
        task = asyncio.create_task(messaging_service.simulate_missiles_loop())
        
        # Let it run for a short time
        await asyncio.sleep(0.1)
        
        # Cancel the task
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected
        
        # Verify the missile was updated (position should have changed)
        assert "MISSILE-001" in messaging_service.active_missiles
        # The missile should have moved from its initial position
        assert messaging_service.active_missiles["MISSILE-001"].position != [100, 200, 1000] 