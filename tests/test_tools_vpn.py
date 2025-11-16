"""
Tests for VPN management tools

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from lab_testing.tools.vpn_manager import (
    connect_vpn,
    disconnect_vpn,
    get_vpn_statistics,
    get_vpn_status,
)


class TestVPNStatus:
    """Tests for get_vpn_status"""

    @patch("lab_testing.tools.vpn_manager.get_vpn_config")
    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_vpn_status_connected(self, mock_run, mock_config, temp_config_dir):
        """Test VPN status when connected"""
        # Mock wg show output
        mock_wg = Mock()
        mock_wg.returncode = 0
        mock_wg.stdout = "interface: wg0\npublic key: test_key\n"
        mock_wg.stderr = ""

        # Mock nmcli output
        mock_nm = Mock()
        mock_nm.returncode = 0
        mock_nm.stdout = "wg0:wireguard:wlan0:activated\n"
        mock_nm.stderr = ""

        mock_run.side_effect = [mock_wg, mock_nm]

        # Mock config
        config_file = temp_config_dir / "vpn.conf"
        config_file.write_text("[Interface]\nPrivateKey = test\n")
        mock_config.return_value = config_file

        result = get_vpn_status()

        assert result["connected"] is True
        assert len(result["wireguard_interfaces"]) > 0
        assert result["config_exists"] is True

    @patch("lab_testing.tools.vpn_manager.get_vpn_config")
    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_vpn_status_disconnected(self, mock_run, mock_config):
        """Test VPN status when disconnected"""
        # Mock wg show output (no interfaces)
        mock_wg = Mock()
        mock_wg.returncode = 0
        mock_wg.stdout = ""
        mock_wg.stderr = ""

        # Mock nmcli output (no connections)
        mock_nm = Mock()
        mock_nm.returncode = 0
        mock_nm.stdout = ""
        mock_nm.stderr = ""

        mock_run.side_effect = [mock_wg, mock_nm]
        mock_config.return_value = None

        result = get_vpn_status()

        assert result["connected"] is False
        assert len(result["wireguard_interfaces"]) == 0

    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_vpn_status_tools_not_found(self, mock_run):
        """Test VPN status when WireGuard tools not found"""
        mock_run.side_effect = FileNotFoundError("wg: command not found")

        result = get_vpn_status()

        assert result["connected"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("lab_testing.tools.vpn_manager.get_vpn_config")
    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_vpn_status_exception(self, mock_run, mock_config):
        """Test VPN status with exception"""
        mock_run.side_effect = Exception("Unexpected error")
        mock_config.return_value = None

        result = get_vpn_status()

        assert result["connected"] is False
        assert "error" in result


class TestVPNStatistics:
    """Tests for get_vpn_statistics"""

    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_vpn_statistics_success(self, mock_run):
        """Test getting VPN statistics successfully"""
        # wg show all dump format: interface\tpublic_key\tlisten_port\tfwmark
        # peer line: public_key\tpreshared_key\tendpoint\tallowed_ips\tlast_handshake\ttransfer_rx\ttransfer_tx\tpersistent_keepalive
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "wg0\ttest_public_key\t51820\t0\npeer_key\tpsk\tvpn.example.com:51820\t10.0.0.0/24\t1234567890\t1024\t2048\t25\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = get_vpn_statistics()

        # Function returns dict with "interfaces" key
        assert "interfaces" in result
        assert len(result["interfaces"]) > 0
        assert result["connected"] is True

    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_vpn_statistics_no_interfaces(self, mock_run):
        """Test VPN statistics with no active interfaces"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = get_vpn_statistics()

        # Function returns error dict when no interfaces
        assert "error" in result or "interfaces" in result
        if "interfaces" in result:
            assert len(result["interfaces"]) == 0

    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_vpn_statistics_error(self, mock_run):
        """Test VPN statistics with error"""
        mock_run.side_effect = FileNotFoundError("wg: command not found")

        result = get_vpn_statistics()

        # Function returns dict with "error" key on error
        assert "error" in result


class TestVPNConnect:
    """Tests for connect_vpn"""

    @patch("lab_testing.tools.vpn_manager.get_vpn_config")
    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_connect_vpn_success(self, mock_run, mock_config, temp_config_dir):
        """Test connecting VPN successfully"""
        config_file = temp_config_dir / "vpn.conf"
        config_file.write_text("[Interface]\nPrivateKey = test\n")
        mock_config.return_value = config_file

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Connection activated"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = connect_vpn()

        assert result["success"] is True

    @patch("lab_testing.tools.vpn_manager.get_vpn_config")
    def test_connect_vpn_no_config(self, mock_config):
        """Test connecting VPN with no config file"""
        mock_config.return_value = None

        result = connect_vpn()

        assert result["success"] is False
        assert "error" in result
        assert "config" in result["error"].lower()

    @patch("lab_testing.tools.vpn_manager.get_vpn_config")
    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_connect_vpn_failure(self, mock_run, mock_config, temp_config_dir):
        """Test VPN connection failure"""
        config_file = temp_config_dir / "vpn.conf"
        config_file.write_text("[Interface]\nPrivateKey = test\n")
        mock_config.return_value = config_file

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Connection failed"
        mock_run.return_value = mock_result

        result = connect_vpn()

        assert result["success"] is False
        assert "error" in result


class TestVPNDisconnect:
    """Tests for disconnect_vpn"""

    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_disconnect_vpn_success(self, mock_run):
        """Test disconnecting VPN successfully"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Connection deactivated"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = disconnect_vpn()

        assert result["success"] is True

    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_disconnect_vpn_failure(self, mock_run):
        """Test VPN disconnection failure"""
        # Mock nmcli (no connection found)
        mock_nm = Mock()
        mock_nm.returncode = 0
        mock_nm.stdout = ""
        mock_nm.stderr = ""

        # Mock wg show (no interfaces)
        mock_wg = Mock()
        mock_wg.returncode = 0
        mock_wg.stdout = ""
        mock_wg.stderr = ""

        mock_run.side_effect = [mock_nm, mock_wg]

        result = disconnect_vpn()

        # Should return success even if no connections found
        assert result["success"] is True

    @patch("lab_testing.tools.vpn_manager.subprocess.run")
    def test_disconnect_vpn_exception(self, mock_run):
        """Test VPN disconnection with exception"""
        mock_run.side_effect = Exception("Unexpected error")

        result = disconnect_vpn()

        assert result["success"] is False
        assert "error" in result

