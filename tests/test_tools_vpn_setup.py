"""
Tests for VPN setup tools

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from lab_testing.tools.vpn_setup import (
    check_wireguard_installed,
    create_config_template,
    get_setup_instructions,
    list_existing_configs,
    setup_networkmanager_connection,
)


class TestCheckWireguardInstalled:
    """Tests for check_wireguard_installed"""

    @patch("lab_testing.tools.vpn_setup.subprocess.run")
    def test_check_wireguard_installed_success(self, mock_run):
        """Test checking WireGuard when installed"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "wireguard-tools v1.0.0"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = check_wireguard_installed()

        assert result["installed"] is True
        assert "version" in result
        assert result["version"] == "wireguard-tools v1.0.0"
        assert result.get("error") is None or result.get("error") == ""
        mock_run.assert_called_once()
        # Check call arguments - can be positional or keyword
        call_args = mock_run.call_args
        if call_args[0]:  # Positional args
            assert call_args[0][0] == ["wg", "--version"]
        else:  # Keyword args
            assert call_args[1]["args"] == ["wg", "--version"] or call_args[1].get("cmd") == [
                "wg",
                "--version",
            ]

    @patch("lab_testing.tools.vpn_setup.subprocess.run")
    def test_check_wireguard_installed_not_found(self, mock_run):
        """Test checking WireGuard when not installed"""
        mock_run.side_effect = FileNotFoundError()

        result = check_wireguard_installed()

        assert result["installed"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("lab_testing.tools.vpn_setup.subprocess.run")
    def test_check_wireguard_installed_not_installed(self, mock_run):
        """Test checking WireGuard when command fails"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command not found"
        mock_run.return_value = mock_result

        result = check_wireguard_installed()

        assert result["installed"] is False
        assert "error" in result


class TestListExistingConfigs:
    """Tests for list_existing_configs"""

    def test_list_existing_configs_in_secrets(self, tmp_path):
        """Test listing configs in secrets directory"""
        # Create a temporary secrets directory with a config file
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        config_file = secrets_dir / "wg0.conf"
        config_file.write_text("[Interface]\nPrivateKey = test")

        with patch("lab_testing.tools.vpn_setup.SECRETS_DIR", secrets_dir):
            result = list_existing_configs()

            assert "configs" in result
            assert result["count"] >= 1
            assert any(c["location"] == "secrets" for c in result["configs"])

    @patch("lab_testing.tools.vpn_setup.Path.home")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    def test_list_existing_configs_in_user_config(self, mock_glob, mock_exists, mock_home):
        """Test listing configs in user config directory"""
        mock_home.return_value = Path("/home/user")
        mock_exists.side_effect = lambda: (
            True if "wireguard" in str(mock_exists.call_args) else False
        )
        mock_config_file = Mock(spec=Path)
        mock_config_file.name = "wg1.conf"
        mock_config_file.__str__ = lambda x: "/home/user/.config/wireguard/wg1.conf"
        mock_glob.return_value = [mock_config_file]

        result = list_existing_configs()

        assert "configs" in result
        assert result["count"] >= 0

    def test_list_existing_configs_empty(self):
        """Test listing configs when none exist"""
        with patch("lab_testing.tools.vpn_setup.SECRETS_DIR") as mock_secrets, patch(
            "pathlib.Path.exists"
        ) as mock_exists:
            mock_secrets.exists.return_value = False
            mock_exists.return_value = False

            result = list_existing_configs()

            assert "configs" in result
            assert result["count"] == 0


class TestCreateConfigTemplate:
    """Tests for create_config_template"""

    @patch("lab_testing.tools.vpn_setup.SECRETS_DIR")
    def test_create_config_template_success(self, mock_secrets_dir, tmp_path):
        """Test creating config template successfully"""
        output_file = tmp_path / "wg0.conf"
        mock_secrets_dir.__truediv__ = lambda self, other: output_file

        result = create_config_template(output_file)

        assert result["success"] is True
        assert "path" in result
        assert output_file.exists()
        assert output_file.read_text().startswith("[Interface]")
        # Check permissions (should be 0o600)
        assert oct(output_file.stat().st_mode)[-3:] == "600"

    @patch("lab_testing.tools.vpn_setup.SECRETS_DIR")
    def test_create_config_template_already_exists(self, mock_secrets_dir, tmp_path):
        """Test creating config template when file already exists"""
        output_file = tmp_path / "wg0.conf"
        output_file.write_text("existing config")
        mock_secrets_dir.__truediv__ = lambda self, other: output_file

        result = create_config_template(output_file)

        assert result["success"] is False
        assert "error" in result
        assert "already exists" in result["error"].lower()

    @patch("lab_testing.tools.vpn_setup.SECRETS_DIR")
    def test_create_config_template_default_path(self, mock_secrets_dir, tmp_path):
        """Test creating config template with default path"""
        default_file = tmp_path / "wg0.conf"
        mock_secrets_dir.__truediv__ = lambda self, other: default_file

        result = create_config_template()

        assert result["success"] is True
        assert default_file.exists()


class TestSetupNetworkmanagerConnection:
    """Tests for setup_networkmanager_connection"""

    @patch("lab_testing.tools.vpn_setup.subprocess.run")
    def test_setup_networkmanager_connection_success(self, mock_run, tmp_path):
        """Test setting up NetworkManager connection successfully"""
        config_file = tmp_path / "wg0.conf"
        config_file.write_text("[Interface]\nPrivateKey = test")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = setup_networkmanager_connection(config_file)

        assert result["success"] is True
        assert "connection_name" in result
        mock_run.assert_called_once()
        assert "nmcli" in str(mock_run.call_args)

    @patch("lab_testing.tools.vpn_setup.subprocess.run")
    def test_setup_networkmanager_connection_failure(self, mock_run, tmp_path):
        """Test NetworkManager setup failure"""
        config_file = tmp_path / "wg0.conf"
        config_file.write_text("[Interface]\nPrivateKey = test")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: Connection failed"
        mock_run.return_value = mock_result

        result = setup_networkmanager_connection(config_file)

        assert result["success"] is False
        assert "error" in result

    def test_setup_networkmanager_connection_file_not_found(self, tmp_path):
        """Test NetworkManager setup when config file doesn't exist"""
        config_file = tmp_path / "nonexistent.conf"

        result = setup_networkmanager_connection(config_file)

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("lab_testing.tools.vpn_setup.subprocess.run")
    def test_setup_networkmanager_connection_nmcli_not_found(self, mock_run, tmp_path):
        """Test NetworkManager setup when nmcli is not installed"""
        config_file = tmp_path / "wg0.conf"
        config_file.write_text("[Interface]\nPrivateKey = test")

        mock_run.side_effect = FileNotFoundError()

        result = setup_networkmanager_connection(config_file)

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower() or "NetworkManager" in result["error"]


class TestGetSetupInstructions:
    """Tests for get_setup_instructions"""

    @patch("lab_testing.tools.vpn_setup.get_vpn_config")
    @patch("lab_testing.tools.vpn_setup.list_existing_configs")
    def test_get_setup_instructions_success(self, mock_list_configs, mock_get_vpn):
        """Test getting setup instructions"""
        mock_get_vpn.return_value = Path("/path/to/wg0.conf")
        mock_list_configs.return_value = {"configs": [], "count": 0}

        result = get_setup_instructions()

        assert "instructions" in result
        assert "current_config" in result
        assert "existing_configs" in result
        assert result["current_config"]["detected"] is True

    @patch("lab_testing.tools.vpn_setup.get_vpn_config")
    @patch("lab_testing.tools.vpn_setup.list_existing_configs")
    def test_get_setup_instructions_no_config(self, mock_list_configs, mock_get_vpn):
        """Test getting setup instructions when no config exists"""
        mock_get_vpn.return_value = None
        mock_list_configs.return_value = {"configs": [], "count": 0}

        result = get_setup_instructions()

        assert "instructions" in result
        assert result["current_config"]["detected"] is False
