"""
Tests for device management tools

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from lab_testing.tools.device_manager import (
    list_devices,
    test_device,
    ssh_to_device,
    resolve_device_identifier,
    get_device_info
)


class TestListDevices:
    """Tests for list_devices"""

    @patch("lab_testing.tools.device_manager.load_device_config")
    def test_list_devices_success(self, mock_load_config, sample_device_config):
        """Test successful device listing"""
        with open(sample_device_config) as f:
            mock_load_config.return_value = {"devices": json.load(f)["devices"], "lab_infrastructure": {}}
        
        result = list_devices()
        
        assert result["total_devices"] == 3
        assert "devices_by_type" in result
        assert "embedded_board" in result["devices_by_type"]
        assert "tasmota_device" in result["devices_by_type"]


class TestTestDevice:
    """Tests for test_device"""

    @patch("lab_testing.tools.device_manager.load_device_config")
    @patch("lab_testing.tools.device_manager.subprocess.run")
    def test_test_device_success(self, mock_run, mock_load_config, sample_device_config, mock_device_test_result):
        """Test successful device test"""
        with open(sample_device_config) as f:
            config = json.load(f)
            mock_load_config.return_value = config
        
        # Mock ping success
        mock_ping = MagicMock()
        mock_ping.returncode = 0
        mock_ping.stdout = "64 bytes from 192.168.1.100"
        
        # Mock SSH success
        mock_ssh = MagicMock()
        mock_ssh.returncode = 0
        
        mock_run.side_effect = [mock_ping, mock_ssh]
        
        result = test_device("test_device_1")
        
        assert result["device_id"] == "test_device_1"
        assert result.get("ping_reachable") or result.get("ping", {}).get("success")


class TestResolveDeviceIdentifier:
    """Tests for resolve_device_identifier"""

    @patch("lab_testing.tools.device_manager.load_device_config")
    def test_resolve_by_device_id(self, mock_load_config, sample_device_config):
        """Test resolving by device_id"""
        with open(sample_device_config) as f:
            config = json.load(f)
            mock_load_config.return_value = config
        
        result = resolve_device_identifier("test_device_1")
        assert result == "test_device_1"

    @patch("lab_testing.tools.device_manager.load_device_config")
    def test_resolve_by_friendly_name(self, mock_load_config, sample_device_config):
        """Test resolving by friendly_name"""
        with open(sample_device_config) as f:
            config = json.load(f)
            mock_load_config.return_value = config
        
        result = resolve_device_identifier("Test Board 1")
        assert result == "test_device_1"

    @patch("lab_testing.tools.device_manager.load_device_config")
    def test_resolve_not_found(self, mock_load_config, sample_device_config):
        """Test resolving non-existent device"""
        with open(sample_device_config) as f:
            config = json.load(f)
            mock_load_config.return_value = config
        
        result = resolve_device_identifier("nonexistent")
        assert result is None


class TestSSHToDevice:
    """Tests for ssh_to_device"""

    @patch("lab_testing.tools.device_manager.load_device_config")
    @patch("lab_testing.tools.device_manager.subprocess.run")
    def test_ssh_success(self, mock_run, mock_load_config, sample_device_config):
        """Test successful SSH command"""
        with open(sample_device_config) as f:
            config = json.load(f)
            mock_load_config.return_value = config
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "command output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = ssh_to_device("test_device_1", "uptime")
        
        assert result["success"] is True
        assert "output" in result or "stdout" in result

