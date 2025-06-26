"""
Unit tests for the Attack Service main module
"""
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI

from attack_service.main import main
from attack_service.api import AttackServiceAPI
from attack_service.messaging import MessagingService


@pytest.mark.unit
class TestMain:
    """Test cases for main module"""
    
    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables"""
        return {
            "DB_DSN": "postgresql://test:test@localhost/test",
            "NATS_URL": "nats://localhost:4222"
        }
    
    @pytest.mark.asyncio
    async def test_main_success(self, mock_env_vars):
        """Test successful main function execution"""
        with patch.dict(os.environ, mock_env_vars), \
             patch('attack_service.main.MessagingService') as mock_messaging_class, \
             patch('attack_service.main.AttackServiceAPI') as mock_api_class, \
             patch('attack_service.main.uvicorn.Server') as mock_server_class, \
             patch('prometheus_client.start_http_server') as mock_prometheus:
            
            # Setup mocks
            mock_messaging = AsyncMock(spec=MessagingService)
            mock_messaging_class.return_value = mock_messaging
            
            mock_api = MagicMock(spec=AttackServiceAPI)
            mock_app = MagicMock(spec=FastAPI)
            mock_api.get_app.return_value = mock_app
            mock_api_class.return_value = mock_api
            
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server
            
            # Create a task that will be cancelled to simulate the server running
            async def mock_serve():
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError()
            
            mock_server.serve = mock_serve
            
            # Run main function
            with pytest.raises(asyncio.CancelledError):
                await main()
            
            # Verify initialization
            mock_messaging_class.assert_called_once_with(
                "postgresql://test:test@localhost/test",
                "nats://localhost:4222"
            )
            mock_messaging.initialize.assert_called_once()
            mock_api_class.assert_called_once_with(mock_messaging)
            mock_api.get_app.assert_called_once()
            
            # Verify startup and shutdown events were added
            assert len(mock_app.on_event.call_args_list) == 2
            
            # Verify uvicorn server was configured
            mock_server_class.assert_called_once()
            call_args = mock_server_class.call_args
            assert call_args[1]['app'] == mock_app
            assert call_args[1]['host'] == "0.0.0.0"
            assert call_args[1]['port'] == 9000
            assert call_args[1]['log_level'] == "info"
    
    @pytest.mark.asyncio
    async def test_main_missing_db_dsn(self):
        """Test main function with missing DB_DSN environment variable"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="DB_DSN environment variable is required"):
                await main()
    
    @pytest.mark.asyncio
    async def test_main_default_nats_url(self, mock_env_vars):
        """Test main function with default NATS URL"""
        # Remove NATS_URL from environment
        env_vars = mock_env_vars.copy()
        del env_vars["NATS_URL"]
        
        with patch.dict(os.environ, env_vars), \
             patch('attack_service.main.MessagingService') as mock_messaging_class, \
             patch('attack_service.main.AttackServiceAPI') as mock_api_class, \
             patch('attack_service.main.uvicorn.Server') as mock_server_class, \
             patch('prometheus_client.start_http_server'):
            
            # Setup mocks
            mock_messaging = AsyncMock(spec=MessagingService)
            mock_messaging_class.return_value = mock_messaging
            
            mock_api = MagicMock(spec=AttackServiceAPI)
            mock_app = MagicMock(spec=FastAPI)
            mock_api.get_app.return_value = mock_app
            mock_api_class.return_value = mock_api
            
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server
            
            async def mock_serve():
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError()
            
            mock_server.serve = mock_serve
            
            # Run main function
            with pytest.raises(asyncio.CancelledError):
                await main()
            
            # Verify default NATS URL was used
            mock_messaging_class.assert_called_once_with(
                "postgresql://test:test@localhost/test",
                "nats://nats:4222"  # Default value
            )
    
    @pytest.mark.asyncio
    async def test_main_messaging_initialization_error(self, mock_env_vars):
        """Test main function when messaging service initialization fails"""
        with patch.dict(os.environ, mock_env_vars), \
             patch('attack_service.main.MessagingService') as mock_messaging_class, \
             patch('prometheus_client.start_http_server'):
            
            # Setup mock to raise exception during initialization
            mock_messaging = AsyncMock(spec=MessagingService)
            mock_messaging.initialize.side_effect = Exception("Database connection failed")
            mock_messaging_class.return_value = mock_messaging
            
            with pytest.raises(Exception, match="Database connection failed"):
                await main()
    
    @pytest.mark.asyncio
    async def test_startup_event(self, mock_env_vars):
        """Test startup event handler"""
        with patch.dict(os.environ, mock_env_vars), \
             patch('attack_service.main.MessagingService') as mock_messaging_class, \
             patch('attack_service.main.AttackServiceAPI') as mock_api_class, \
             patch('attack_service.main.uvicorn.Server') as mock_server_class, \
             patch('prometheus_client.start_http_server'), \
             patch('builtins.print') as mock_print:
            
            # Setup mocks
            mock_messaging = AsyncMock(spec=MessagingService)
            mock_messaging_class.return_value = mock_messaging
            
            mock_api = MagicMock(spec=AttackServiceAPI)
            mock_app = MagicMock(spec=FastAPI)
            mock_api.get_app.return_value = mock_app
            mock_api_class.return_value = mock_api
            
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server
            
            async def mock_serve():
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError()
            
            mock_server.serve = mock_serve
            
            # Run main function
            with pytest.raises(asyncio.CancelledError):
                await main()
            
            # Verify startup event was added
            startup_calls = [call for call in mock_app.on_event.call_args_list if call[0][0] == "startup"]
            assert len(startup_calls) == 1
            
            # Get the startup event handler
            startup_handler = startup_calls[0][0][1]
            
            # Test the startup handler
            await startup_handler()
            mock_print.assert_called_with("Attack Service starting up...")
    
    @pytest.mark.asyncio
    async def test_shutdown_event(self, mock_env_vars):
        """Test shutdown event handler"""
        with patch.dict(os.environ, mock_env_vars), \
             patch('attack_service.main.MessagingService') as mock_messaging_class, \
             patch('attack_service.main.AttackServiceAPI') as mock_api_class, \
             patch('attack_service.main.uvicorn.Server') as mock_server_class, \
             patch('prometheus_client.start_http_server'), \
             patch('builtins.print') as mock_print:
            
            # Setup mocks
            mock_messaging = AsyncMock(spec=MessagingService)
            mock_messaging_class.return_value = mock_messaging
            
            mock_api = MagicMock(spec=AttackServiceAPI)
            mock_app = MagicMock(spec=FastAPI)
            mock_api.get_app.return_value = mock_app
            mock_api_class.return_value = mock_api
            
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server
            
            async def mock_serve():
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError()
            
            mock_server.serve = mock_serve
            
            # Run main function
            with pytest.raises(asyncio.CancelledError):
                await main()
            
            # Verify shutdown event was added
            shutdown_calls = [call for call in mock_app.on_event.call_args_list if call[0][0] == "shutdown"]
            assert len(shutdown_calls) == 1
            
            # Get the shutdown event handler
            shutdown_handler = shutdown_calls[0][0][1]
            
            # Test the shutdown handler
            await shutdown_handler()
            mock_print.assert_called_with("Attack Service shutting down...")
            mock_messaging.shutdown.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prometheus_server_started(self, mock_env_vars):
        """Test that Prometheus server is started"""
        with patch.dict(os.environ, mock_env_vars), \
             patch('attack_service.main.MessagingService') as mock_messaging_class, \
             patch('attack_service.main.AttackServiceAPI') as mock_api_class, \
             patch('attack_service.main.uvicorn.Server') as mock_server_class, \
             patch('prometheus_client.start_http_server') as mock_prometheus:
            
            # Setup mocks
            mock_messaging = AsyncMock(spec=MessagingService)
            mock_messaging_class.return_value = mock_messaging
            
            mock_api = MagicMock(spec=AttackServiceAPI)
            mock_app = MagicMock(spec=FastAPI)
            mock_api.get_app.return_value = mock_app
            mock_api_class.return_value = mock_api
            
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server
            
            async def mock_serve():
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError()
            
            mock_server.serve = mock_serve
            
            # Run main function
            with pytest.raises(asyncio.CancelledError):
                await main()
            
            # Verify Prometheus server was started
            mock_prometheus.assert_called_once_with(8000) 