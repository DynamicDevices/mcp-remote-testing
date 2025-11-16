"""
Tests for remote access tools (SSH tunnels and serial port access)

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import socket
from unittest.mock import MagicMock, Mock, patch

import pytest

from lab_testing.exceptions import DeviceConnectionError, DeviceNotFoundError
from lab_testing.tools.remote_access import (
    create_ssh_tunnel,
    get_device_info,
    list_serial_devices,
)


class TestSSHTunnel:
    """Tests for create_ssh_tunnel"""

    @patch("lab_testing.tools.remote_access.get_ssh_command")
    @patch("lab_testing.tools.remote_access.subprocess.run")
    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_create_ssh_tunnel_success(self, mock_get_device, mock_run, mock_ssh_cmd):
        """Test creating SSH tunnel successfully"""
        # Mock device info
        mock_get_device.return_value = {
            "device_id": "test_device",
            "ip": "192.168.1.100",
            "ssh_user": "root",
        }

        # Mock SSH command
        mock_ssh_cmd.return_value = ["ssh", "-o", "StrictHostKeyChecking=no", "root@192.168.1.100"]

        # Mock subprocess success
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Mock socket for port finding
        with patch("socket.socket") as mock_socket:
            mock_sock = Mock()
            mock_sock.getsockname.return_value = ("", 22222)
            mock_socket.return_value = mock_sock

            result = create_ssh_tunnel("test_device", local_port=None, remote_port=22)

        assert result["success"] is True
        assert "local_port" in result
        assert "tunnel_type" in result

    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_create_ssh_tunnel_device_not_found(self, mock_get_device):
        """Test creating tunnel with non-existent device"""
        mock_get_device.return_value = None

        with pytest.raises(DeviceNotFoundError):
            create_ssh_tunnel("nonexistent_device")

    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_create_ssh_tunnel_no_ip(self, mock_get_device):
        """Test creating tunnel with device that has no IP"""
        mock_get_device.return_value = {
            "device_id": "test_device",
            "ip": None,
            "ssh_user": "root",
        }

        with pytest.raises(DeviceConnectionError):
            create_ssh_tunnel("test_device")

    @patch("lab_testing.tools.remote_access.get_ssh_command")
    @patch("lab_testing.tools.remote_access.subprocess.run")
    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_create_ssh_tunnel_failure(self, mock_get_device, mock_run, mock_ssh_cmd):
        """Test SSH tunnel creation failure"""
        from lab_testing.exceptions import SSHError

        mock_get_device.return_value = {
            "device_id": "test_device",
            "ip": "192.168.1.100",
            "ssh_user": "root",
        }
        # get_ssh_command returns a list, we need to modify it
        mock_ssh_cmd.return_value = ["ssh", "-o", "StrictHostKeyChecking=no", "root@192.168.1.100"]

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Connection refused"
        mock_run.return_value = mock_result

        # Function raises SSHError on failure
        with pytest.raises(SSHError):
            create_ssh_tunnel("test_device", local_port=22222)

    @patch("lab_testing.tools.remote_access.get_ssh_command")
    @patch("lab_testing.tools.remote_access.subprocess.run")
    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_create_ssh_tunnel_remote_type(self, mock_get_device, mock_run, mock_ssh_cmd):
        """Test creating remote port forwarding tunnel"""
        mock_get_device.return_value = {
            "device_id": "test_device",
            "ip": "192.168.1.100",
            "ssh_user": "root",
        }
        mock_ssh_cmd.return_value = ["ssh", "root@192.168.1.100"]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = create_ssh_tunnel("test_device", local_port=22222, tunnel_type="remote")

        assert result["success"] is True
        assert result["tunnel_type"] == "remote"


class TestSerialDevices:
    """Tests for list_serial_devices"""

    @patch("lab_testing.tools.remote_access.get_ssh_command")
    @patch("lab_testing.tools.remote_access.subprocess.run")
    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_list_serial_devices_success(self, mock_get_device, mock_run, mock_ssh_cmd):
        """Test listing serial devices successfully"""
        mock_get_device.return_value = {
            "device_id": "remote_laptop",
            "ip": "192.168.1.50",
            "device_type": "remote_laptop",
            "ssh_user": "root",
        }

        mock_ssh_cmd.return_value = ["ssh", "root@192.168.1.50", "ls -la /dev/tty{ACM,USB}*"]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/dev/ttyUSB0 188 0\n/dev/ttyACM0 166 0\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = list_serial_devices("remote_laptop")

        assert result["success"] is True
        assert "devices" in result
        assert len(result["devices"]) > 0

    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_list_serial_devices_not_found(self, mock_get_device):
        """Test listing serial devices for non-existent device"""
        mock_get_device.return_value = None

        with pytest.raises(DeviceNotFoundError):
            list_serial_devices("nonexistent")

    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_list_serial_devices_no_ip(self, mock_get_device):
        """Test listing serial devices for device with no IP"""
        mock_get_device.return_value = {
            "device_id": "remote_laptop",
            "ip": None,
            "device_type": "remote_laptop",
        }

        with pytest.raises(DeviceConnectionError):
            list_serial_devices("remote_laptop")

    @patch("lab_testing.tools.remote_access.get_ssh_command")
    @patch("lab_testing.tools.remote_access.subprocess.run")
    @patch("lab_testing.tools.remote_access.get_device_info")
    def test_list_serial_devices_no_devices(self, mock_get_device, mock_run, mock_ssh_cmd):
        """Test listing serial devices when none found"""
        mock_get_device.return_value = {
            "device_id": "remote_laptop",
            "ip": "192.168.1.50",
            "device_type": "remote_laptop",
            "ssh_user": "root",
        }

        mock_ssh_cmd.return_value = ["ssh", "root@192.168.1.50", "ls -la /dev/tty{ACM,USB}*"]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "NONE"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = list_serial_devices("remote_laptop")

        assert result["success"] is True
        assert len(result["devices"]) == 0


class TestGetDeviceInfo:
    """Tests for get_device_info wrapper"""

    @patch("lab_testing.tools.remote_access._get_device_info")
    def test_get_device_info_success(self, mock_get):
        """Test getting device info"""
        mock_get.return_value = {"device_id": "test", "ip": "192.168.1.100"}

        result = get_device_info("test")

        assert result == {"device_id": "test", "ip": "192.168.1.100"}

    @patch("lab_testing.tools.remote_access._get_device_info")
    def test_get_device_info_not_found(self, mock_get):
        """Test getting device info for non-existent device"""
        mock_get.return_value = None

        result = get_device_info("nonexistent")

        assert result is None

