"""
Pytest configuration and fixtures for MCP Remote Testing tests

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, MagicMock, patch

import pytest


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create temporary config directory"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_device_config(temp_config_dir: Path) -> Path:
    """Create sample device configuration file"""
    config_file = temp_config_dir / "lab_devices.json"
    config = {
        "devices": {
            "test_device_1": {
                "device_type": "embedded_board",
                "friendly_name": "Test Board 1",
                "name": "Test Board 1",
                "hostname": "test-board-1",
                "ip": "192.168.1.100",
                "username": "root",
                "status": "online",
                "power_switch": "tasmota_switch_1"
            },
            "test_device_2": {
                "device_type": "embedded_board",
                "friendly_name": "Test Board 2",
                "name": "Test Board 2",
                "hostname": "test-board-2",
                "ip": "192.168.1.101",
                "username": "root",
                "status": "online"
            },
            "tasmota_switch_1": {
                "device_type": "tasmota_device",
                "friendly_name": "Lab Power Switch 1",
                "name": "Power Switch 1",
                "ip": "192.168.1.88",
                "tasmota_type": "power_switch"
            }
        },
        "lab_infrastructure": {
            "network_access": {
                "lab_networks": ["192.168.1.0/24"]
            },
            "wireguard_vpn": {
                "gateway_host": "vpn.example.com"
            }
        }
    }
    config_file.write_text(json.dumps(config, indent=2))
    return config_file


@pytest.fixture
def mock_ssh_connection():
    """Mock SSH connection"""
    mock = MagicMock()
    mock.exec_command.return_value = (
        Mock(read=lambda: b""),
        Mock(read=lambda: b"output"),
        Mock(read=lambda: b"")
    )
    mock.get_transport.return_value.is_active.return_value = True
    return mock


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for command execution"""
    with patch("subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_vpn_status():
    """Mock VPN status (connected)"""
    return {
        "connected": True,
        "interface": "wg0",
        "public_key": "test_key",
        "endpoint": "vpn.example.com:51820"
    }


@pytest.fixture
def mock_device_test_result():
    """Mock device test result"""
    return {
        "device_id": "test_device_1",
        "ping_reachable": True,
        "ssh_available": True,
        "ping": {"success": True, "latency_ms": 5.2},
        "ssh": {"success": True}
    }


@pytest.fixture
def mock_tasmota_response():
    """Mock Tasmota device response"""
    return {
        "success": True,
        "device_id": "tasmota_switch_1",
        "action": "on",
        "result": {"POWER": "ON"}
    }


@pytest.fixture
def mock_ota_status():
    """Mock OTA status"""
    return {
        "device_id": "test_device_1",
        "registered": True,
        "connected": True,
        "current_version": "1.0.0",
        "target_version": "1.0.0",
        "update_available": False
    }


@pytest.fixture
def mock_system_status():
    """Mock system status"""
    return {
        "device_id": "test_device_1",
        "uptime": "2 days, 3 hours",
        "load": [0.5, 0.6, 0.7],
        "memory": {"total_mb": 1024, "used_mb": 512, "free_mb": 512},
        "disk": {"total_gb": 16, "used_gb": 8, "free_gb": 8},
        "kernel": "5.10.0"
    }

