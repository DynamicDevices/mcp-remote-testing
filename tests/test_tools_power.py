"""
Tests for power monitoring tools

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from lab_testing.tools.power_monitor import (
    start_power_monitoring,
    get_power_logs,
    _start_dmm_power_monitoring,
    _start_tasmota_power_monitoring
)


class TestStartPowerMonitoring:
    """Tests for start_power_monitoring"""

    @patch("lab_testing.tools.power_monitor.get_lab_devices_config")
    @patch("lab_testing.tools.power_monitor._start_dmm_power_monitoring")
    def test_start_dmm_monitoring(self, mock_dmm, mock_config, sample_device_config):
        """Test starting DMM power monitoring"""
        mock_config.return_value = sample_device_config
        
        with open(sample_device_config) as f:
            devices = json.load(f)["devices"]
        
        mock_dmm.return_value = {
            "success": True,
            "monitor_type": "dmm",
            "process_id": 12345
        }
        
        result = start_power_monitoring(monitor_type="dmm")
        
        assert result["success"] is True
        assert result["monitor_type"] == "dmm"
        mock_dmm.assert_called_once()

    @patch("lab_testing.tools.power_monitor.get_lab_devices_config")
    @patch("lab_testing.tools.power_monitor._start_tasmota_power_monitoring")
    def test_start_tasmota_monitoring(self, mock_tasmota, mock_config, sample_device_config):
        """Test starting Tasmota power monitoring"""
        mock_config.return_value = sample_device_config
        
        with open(sample_device_config) as f:
            devices = json.load(f)["devices"]
        
        mock_tasmota.return_value = {
            "success": True,
            "monitor_type": "tasmota",
            "device_id": "tasmota_switch_1"
        }
        
        result = start_power_monitoring("tasmota_switch_1", monitor_type="tasmota")
        
        assert result["success"] is True
        assert result["monitor_type"] == "tasmota"
        mock_tasmota.assert_called_once()

    @patch("lab_testing.tools.power_monitor.get_lab_devices_config")
    def test_auto_detect_tasmota(self, mock_config, sample_device_config):
        """Test auto-detection of Tasmota device"""
        mock_config.return_value = sample_device_config
        
        with patch("lab_testing.tools.power_monitor._start_tasmota_power_monitoring") as mock_tasmota:
            mock_tasmota.return_value = {"success": True, "monitor_type": "tasmota"}
            
            result = start_power_monitoring("tasmota_switch_1")
            
            mock_tasmota.assert_called_once()


class TestDMMPowerMonitoring:
    """Tests for DMM power monitoring"""

    @patch("lab_testing.tools.power_monitor.get_scripts_dir")
    @patch("lab_testing.tools.power_monitor.subprocess.Popen")
    def test_dmm_monitoring_success(self, mock_popen, mock_scripts_dir, tmp_path):
        """Test successful DMM monitoring start"""
        mock_scripts_dir.return_value = tmp_path
        monitor_script = tmp_path / "current_monitor.py"
        monitor_script.write_text("# DMM monitor script")
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        result = _start_dmm_power_monitoring(None, "test", 300, {})
        
        assert result["success"] is True
        assert result["monitor_type"] == "dmm"
        assert result["process_id"] == 12345

    @patch("lab_testing.tools.power_monitor.get_scripts_dir")
    def test_dmm_monitoring_script_not_found(self, mock_scripts_dir, tmp_path):
        """Test DMM monitoring when script not found"""
        mock_scripts_dir.return_value = tmp_path
        
        result = _start_dmm_power_monitoring(None, "test", 300, {})
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestTasmotaPowerMonitoring:
    """Tests for Tasmota power monitoring"""

    @patch("lab_testing.tools.power_monitor.tasmota_control")
    def test_tasmota_monitoring_success(self, mock_tasmota_control):
        """Test successful Tasmota monitoring start"""
        mock_tasmota_control.return_value = {
            "success": True,
            "result": {"Energy": {"Total": 1.5, "Today": 0.1, "Power": 5.2}}
        }
        
        devices = {
            "tasmota_switch_1": {
                "device_type": "tasmota_device",
                "name": "Power Switch 1"
            }
        }
        
        result = _start_tasmota_power_monitoring("tasmota_switch_1", "test", 300, devices)
        
        assert result["success"] is True
        assert result["monitor_type"] == "tasmota"
        assert result["device_id"] == "tasmota_switch_1"

    def test_tasmota_monitoring_no_device_id(self):
        """Test Tasmota monitoring without device ID"""
        result = _start_tasmota_power_monitoring(None, "test", 300, {})
        
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_tasmota_monitoring_invalid_device(self):
        """Test Tasmota monitoring with invalid device"""
        devices = {
            "other_device": {
                "device_type": "embedded_board"
            }
        }
        
        result = _start_tasmota_power_monitoring("other_device", "test", 300, devices)
        
        assert result["success"] is False
        assert "not a Tasmota device" in result["error"]

    @patch("lab_testing.tools.power_monitor.tasmota_control")
    def test_tasmota_monitoring_no_energy_support(self, mock_tasmota_control):
        """Test Tasmota monitoring when energy not supported"""
        mock_tasmota_control.return_value = {
            "success": False,
            "error": "Energy monitoring not available"
        }
        
        devices = {
            "tasmota_switch_1": {
                "device_type": "tasmota_device"
            }
        }
        
        result = _start_tasmota_power_monitoring("tasmota_switch_1", "test", 300, devices)
        
        assert result["success"] is False
        assert "energy monitoring" in result["error"].lower()


class TestGetPowerLogs:
    """Tests for get_power_logs"""

    @patch("lab_testing.tools.power_monitor.get_logs_dir")
    def test_get_power_logs_success(self, mock_logs_dir, tmp_path):
        """Test getting power logs"""
        logs_dir = tmp_path / "power_logs"
        logs_dir.mkdir()
        
        # Create test log files
        (logs_dir / "test_20250101_120000.csv").write_text("timestamp,power\n")
        (logs_dir / "test_20250101_130000.csv").write_text("timestamp,power\n")
        
        mock_logs_dir.return_value = tmp_path
        
        result = get_power_logs(limit=10)
        
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["log_files"]) == 2

    @patch("lab_testing.tools.power_monitor.get_logs_dir")
    def test_get_power_logs_not_found(self, mock_logs_dir, tmp_path):
        """Test getting logs when directory doesn't exist"""
        mock_logs_dir.return_value = tmp_path
        
        result = get_power_logs()
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()

