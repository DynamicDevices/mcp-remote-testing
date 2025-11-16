"""
Tests for Tasmota control tools

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
from unittest.mock import MagicMock, mock_open, patch

from lab_testing.tools.tasmota_control import (
    get_power_switch_for_device,
    list_tasmota_devices,
    power_cycle_device,
    tasmota_control,
)


class TestTasmotaControl:
    """Tests for tasmota_control"""

    @patch("lab_testing.tools.tasmota_control.get_scripts_dir")
    @patch("lab_testing.tools.tasmota_control.get_lab_devices_config")
    @patch("lab_testing.tools.tasmota_control.subprocess.run")
    @patch("pathlib.Path.exists")
    def test_tasmota_control_on(self, mock_exists, mock_run, mock_config, mock_scripts_dir, sample_device_config):
        """Test turning Tasmota device on"""
        # Mock scripts directory and script existence
        from pathlib import Path
        mock_scripts_dir.return_value = Path("/fake/scripts")
        mock_exists.return_value = True  # Script exists
        
        # Mock config file reading - use mock_open with read_data
        with open(sample_device_config) as f:
            config_json = f.read()
        mock_config.return_value = sample_device_config
        
        with patch("builtins.open", mock_open(read_data=config_json)):
            # Mock subprocess result
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps({"POWER": "ON"})
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = tasmota_control("tasmota_switch_1", "on")

            assert result["success"] is True
            assert result["action"] == "on"

    @patch("lab_testing.tools.tasmota_control.get_lab_devices_config")
    def test_tasmota_control_invalid_device(self, mock_config, sample_device_config):
        """Test control with invalid device"""
        mock_config.return_value = sample_device_config

        result = tasmota_control("nonexistent", "on")

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestListTasmotaDevices:
    """Tests for list_tasmota_devices"""

    @patch("lab_testing.tools.tasmota_control.get_lab_devices_config")
    def test_list_tasmota_devices(self, mock_config, sample_device_config):
        """Test listing Tasmota devices"""
        mock_config.return_value = sample_device_config

        result = list_tasmota_devices()

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["devices"]) == 1
        assert result["devices"][0]["id"] == "tasmota_switch_1"
        assert "controls_devices" in result["devices"][0]
        assert len(result["devices"][0]["controls_devices"]) == 1


class TestGetPowerSwitchForDevice:
    """Tests for get_power_switch_for_device"""

    @patch("lab_testing.tools.tasmota_control.get_lab_devices_config")
    @patch("lab_testing.tools.device_manager.resolve_device_identifier")
    def test_get_power_switch_success(self, mock_resolve, mock_config, sample_device_config):
        """Test getting power switch for device"""
        mock_config.return_value = sample_device_config
        mock_resolve.return_value = "test_device_1"

        result = get_power_switch_for_device("test_device_1")

        assert result is not None
        assert result["tasmota_device_id"] == "tasmota_switch_1"
        assert "tasmota_friendly_name" in result

    @patch("lab_testing.tools.tasmota_control.get_lab_devices_config")
    @patch("lab_testing.tools.device_manager.resolve_device_identifier")
    def test_get_power_switch_no_mapping(self, mock_resolve, mock_config, sample_device_config):
        """Test getting power switch when device has no mapping"""
        mock_config.return_value = sample_device_config
        mock_resolve.return_value = "test_device_2"

        result = get_power_switch_for_device("test_device_2")

        assert result is None


class TestPowerCycleDevice:
    """Tests for power_cycle_device"""

    @patch("lab_testing.tools.tasmota_control.get_power_switch_for_device")
    @patch("lab_testing.tools.tasmota_control.tasmota_control")
    @patch("lab_testing.tools.device_manager.resolve_device_identifier")
    @patch("time.sleep")
    def test_power_cycle_success(self, mock_sleep, mock_resolve, mock_control, mock_get_switch):
        """Test successful power cycle"""
        mock_resolve.return_value = "test_device_1"
        mock_get_switch.return_value = {
            "tasmota_device_id": "tasmota_switch_1",
            "tasmota_friendly_name": "Lab Power Switch 1"
        }
        mock_control.side_effect = [
            {"success": True},  # off
            {"success": True}   # on
        ]

        result = power_cycle_device("test_device_1", off_duration=5)

        assert result["success"] is True
        assert mock_control.call_count == 2
        mock_sleep.assert_called_once_with(5)

    @patch("lab_testing.tools.device_manager.resolve_device_identifier")
    def test_power_cycle_no_switch(self, mock_resolve):
        """Test power cycle when device has no power switch"""
        mock_resolve.return_value = "test_device_2"

        with patch("lab_testing.tools.tasmota_control.get_power_switch_for_device") as mock_get:
            mock_get.return_value = None

            result = power_cycle_device("test_device_2")

            assert result["success"] is False
            assert "power switch" in result["error"].lower()

