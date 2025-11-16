"""
Tests for network mapping and device verification tools

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from lab_testing.tools.network_mapper import create_network_map
from lab_testing.tools.device_verification import (
    verify_device_identity,
    verify_device_by_ip
)


class TestCreateNetworkMap:
    """Tests for create_network_map"""

    @patch("lab_testing.tools.network_mapper.get_lab_devices_config")
    @patch("lab_testing.tools.network_mapper.test_device")
    @patch("lab_testing.tools.network_mapper.ssh_to_device")
    @patch("lab_testing.tools.tasmota_control.get_power_switch_for_device")
    def test_create_network_map_with_devices(
        self, mock_get_switch, mock_ssh, mock_test, mock_config, sample_device_config
    ):
        """Test creating network map with configured devices"""
        with open(sample_device_config) as f:
            config = json.load(f)
            mock_config.return_value = sample_device_config
        
        mock_test.return_value = {
            "device_id": "test_device_1",
            "ping_reachable": True,
            "ssh_available": True
        }
        mock_ssh.return_value = {
            "success": True,
            "stdout": "up 2 days, 3 hours"
        }
        mock_get_switch.return_value = {
            "tasmota_device_id": "tasmota_switch_1",
            "tasmota_friendly_name": "Lab Power Switch 1"
        }
        
        result = create_network_map(
            networks=None,
            scan_networks=False,
            test_configured_devices=True
        )
        
        assert "configured_devices" in result
        assert "summary" in result
        assert len(result["configured_devices"]) > 0
        
        # Check that device info includes required fields
        device = list(result["configured_devices"].values())[0]
        assert "friendly_name" in device
        assert "type" in device
        assert "uptime" in device or device.get("status") != "online"
        assert "power_switch" in device


class TestVerifyDeviceIdentity:
    """Tests for verify_device_identity"""

    @patch("lab_testing.tools.device_verification.get_device_info")
    @patch("lab_testing.tools.device_verification.get_device_hostname_from_ip")
    def test_verify_identity_match(self, mock_get_hostname, mock_get_info):
        """Test verifying device identity when it matches"""
        mock_get_info.return_value = {
            "device_id": "test_device_1",
            "hostname": "test-board-1",
            "ip": "192.168.1.100"
        }
        mock_get_hostname.return_value = "test-board-1"
        
        result = verify_device_identity("test_device_1", "192.168.1.100")
        
        assert result["verified"] is True
        assert result["device_id"] == "test_device_1"

    @patch("lab_testing.tools.device_verification.get_device_info")
    @patch("lab_testing.tools.device_verification.get_device_hostname_from_ip")
    def test_verify_identity_mismatch(self, mock_get_hostname, mock_get_info):
        """Test verifying device identity when it doesn't match"""
        mock_get_info.return_value = {
            "device_id": "test_device_1",
            "hostname": "test-board-1",
            "ip": "192.168.1.100"
        }
        mock_get_hostname.return_value = "different-board"
        
        result = verify_device_identity("test_device_1", "192.168.1.100")
        
        assert result["verified"] is False
        assert "mismatch" in result["error"].lower()

