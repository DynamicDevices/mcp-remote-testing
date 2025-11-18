"""
Tests for device management tools

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
from unittest.mock import MagicMock, patch

from lab_testing.tools.device_manager import (
    list_devices,
    resolve_device_identifier,
    ssh_to_device,
)
from lab_testing.tools.device_manager import (
    test_device as test_device_func,  # Rename to avoid pytest collection
)


class TestListDevices:
    """Tests for list_devices"""

    @patch("lab_testing.tools.device_manager.load_device_config")
    @patch("lab_testing.tools.network_mapper._scan_network_range")
    @patch("lab_testing.utils.device_cache.get_cached_device_info")
    @patch("lab_testing.utils.device_cache.identify_and_cache_device")
    @patch("lab_testing.tools.device_detection.detect_tasmota_device")
    @patch("lab_testing.tools.device_detection.detect_test_equipment")
    @patch("lab_testing.tools.vpn_manager.get_vpn_status")
    @patch("lab_testing.config.get_target_network")
    def test_list_devices_success(
        self,
        mock_target_network,
        mock_vpn,
        mock_detect_test,
        mock_detect_tasmota,
        mock_identify,
        mock_cache,
        mock_scan,
        mock_load_config,
        sample_device_config,
    ):
        """Test successful device listing"""
        with open(sample_device_config) as f:
            config_data = json.load(f)
            mock_load_config.return_value = {
                "devices": config_data["devices"],
                "lab_infrastructure": config_data.get("lab_infrastructure", {}),
            }

        # Mock target network to match sample config
        mock_target_network.return_value = "192.168.1.0/24"
        # Mock VPN status
        mock_vpn.return_value = {"connected": False}
        # Mock network scan to return IPs from configured devices
        # list_devices only processes devices in active_hosts, so we need to include them
        mock_scan.return_value = [
            {"ip": "192.168.1.100"},  # test_device_1
            {"ip": "192.168.1.101"},  # test_device_2
            {"ip": "192.168.1.88"},   # tasmota_switch_1
        ]
        # Mock cache to return empty (no cached devices)
        mock_cache.return_value = None
        # Mock detection to return None (no auto-detected devices)
        mock_detect_tasmota.return_value = None
        mock_detect_test.return_value = None

        result = list_devices()

        assert result["total_devices"] == 3
        assert "devices_by_type" in result
        assert "embedded_board" in result["devices_by_type"]
        assert "tasmota_device" in result["devices_by_type"]


class TestTestDevice:
    """Tests for test_device"""

    @patch("lab_testing.tools.device_manager.load_device_config")
    @patch("lab_testing.tools.device_manager.subprocess.run")
    def test_test_device_success(
        self, mock_run, mock_load_config, sample_device_config, mock_device_test_result
    ):
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

        result = test_device_func("test_device_1")

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
