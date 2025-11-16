"""
Tests for credential management utilities

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from lab_testing.utils.credentials import (
    CREDENTIAL_CACHE_DIR,
    CREDENTIAL_CACHE_FILE,
    cache_credential,
    check_ssh_key_installed,
    ensure_cache_dir,
    get_credential,
    get_ssh_command,
    install_ssh_key,
    load_credentials,
    save_credentials,
)


class TestCredentialCache:
    """Tests for credential caching"""

    @patch("lab_testing.utils.credentials.CREDENTIAL_CACHE_DIR")
    def test_ensure_cache_dir(self, mock_cache_dir, tmp_path):
        """Test creating cache directory"""
        # Use tmp_path for testing
        test_cache_dir = tmp_path / "cache"
        mock_cache_dir.__truediv__ = lambda _, other: test_cache_dir / other
        mock_cache_dir.mkdir = test_cache_dir.mkdir
        mock_cache_dir.exists = lambda: test_cache_dir.exists()
        mock_cache_dir.is_dir = lambda: test_cache_dir.is_dir()
        mock_cache_dir.stat = test_cache_dir.stat

        # Mock os.chmod
        with patch("lab_testing.utils.credentials.os.chmod") as mock_chmod:
            ensure_cache_dir()

            assert test_cache_dir.exists()
            assert test_cache_dir.is_dir()
            # Verify chmod was called with correct permissions
            mock_chmod.assert_called()

    def test_load_credentials_empty(self, tmp_path, monkeypatch):
        """Test loading credentials when cache doesn't exist"""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        cache_file = mock_home / ".cache" / "ai-lab-testing" / "credentials.json"
        # Ensure parent exists but file doesn't
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Mock the module-level constant
        with patch("lab_testing.utils.credentials.CREDENTIAL_CACHE_FILE", cache_file):
            result = load_credentials()

        assert result == {}

    def test_load_credentials_existing(self, tmp_path, monkeypatch):
        """Test loading existing credentials"""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        cache_file = mock_home / ".cache" / "ai-lab-testing" / "credentials.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        test_creds = {
            "device1:ssh": {"username": "root", "password": "secret"},
            "device2:ssh": {"username": "user", "password": None},
        }
        cache_file.write_text(json.dumps(test_creds))

        with patch("lab_testing.utils.credentials.CREDENTIAL_CACHE_FILE", cache_file):
            result = load_credentials()

        assert result == test_creds

    def test_load_credentials_invalid_json(self, tmp_path, monkeypatch):
        """Test loading credentials with invalid JSON"""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        cache_file = mock_home / ".cache" / "ai-lab-testing" / "credentials.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("invalid json{")

        with patch("lab_testing.utils.credentials.CREDENTIAL_CACHE_FILE", cache_file):
            result = load_credentials()

        assert result == {}

    def test_save_credentials(self, tmp_path, monkeypatch):
        """Test saving credentials"""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        cache_file = mock_home / ".cache" / "ai-lab-testing" / "credentials.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        test_creds = {"device1:ssh": {"username": "root", "password": "secret"}}

        with patch("lab_testing.utils.credentials.CREDENTIAL_CACHE_FILE", cache_file):
            save_credentials(test_creds)

        assert cache_file.exists()
        loaded = json.loads(cache_file.read_text())
        assert loaded == test_creds
        # Check permissions (0o600 = 384 in decimal)
        assert (cache_file.stat().st_mode & 0o777) == 0o600

    def test_get_credential(self, tmp_path, monkeypatch):
        """Test getting a credential"""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        cache_file = mock_home / ".cache" / "ai-lab-testing" / "credentials.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        test_creds = {"device1:ssh": {"username": "root", "password": "secret"}}
        cache_file.write_text(json.dumps(test_creds))

        with patch("lab_testing.utils.credentials.CREDENTIAL_CACHE_FILE", cache_file):
            result = get_credential("device1", "ssh")

        assert result == {"username": "root", "password": "secret"}

    def test_get_credential_not_found(self, tmp_path, monkeypatch):
        """Test getting non-existent credential"""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        cache_file = mock_home / ".cache" / "ai-lab-testing" / "credentials.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("{}")

        with patch("lab_testing.utils.credentials.CREDENTIAL_CACHE_FILE", cache_file):
            result = get_credential("nonexistent", "ssh")

        assert result is None

    def test_cache_credential(self, tmp_path, monkeypatch):
        """Test caching a credential"""
        mock_home = tmp_path / "home"
        mock_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        cache_file = mock_home / ".cache" / "ai-lab-testing" / "credentials.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("lab_testing.utils.credentials.CREDENTIAL_CACHE_FILE", cache_file):
            cache_credential("device1", "root", "secret", "ssh")

        assert cache_file.exists()
        loaded = json.loads(cache_file.read_text())
        assert loaded["device1:ssh"] == {"username": "root", "password": "secret"}


class TestSSHKeyManagement:
    """Tests for SSH key management"""

    @patch("lab_testing.utils.credentials.subprocess.run")
    def test_check_ssh_key_installed_success(self, mock_run):
        """Test checking SSH key when installed"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = check_ssh_key_installed("192.168.1.100", "root")

        assert result is True
        mock_run.assert_called_once()
        # Check that ssh command was called with correct args
        call_args = mock_run.call_args[0][0]
        assert "ssh" in call_args
        assert "192.168.1.100" in " ".join(call_args)

    @patch("lab_testing.utils.credentials.subprocess.run")
    def test_check_ssh_key_installed_failure(self, mock_run):
        """Test checking SSH key when not installed"""
        mock_result = Mock()
        mock_result.returncode = 255  # SSH connection failed
        mock_result.stdout = ""
        mock_result.stderr = "Permission denied"
        mock_run.return_value = mock_result

        result = check_ssh_key_installed("192.168.1.100", "root")

        assert result is False

    @patch("lab_testing.utils.credentials.check_ssh_key_installed")
    @patch("lab_testing.utils.credentials.subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("builtins.open", create=True)
    def test_install_ssh_key_success(self, mock_open, mock_exists, mock_run, mock_check_key):
        """Test installing SSH key successfully"""
        # Mock key file exists
        mock_exists.return_value = True
        mock_open.return_value.read.return_value = "ssh-rsa test_key"
        mock_open.return_value.__enter__.return_value = mock_open.return_value

        # Mock ssh-copy-id success
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Key installed"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Mock key check after installation
        mock_check_key.side_effect = [False, True]  # Not installed, then installed

        result = install_ssh_key("192.168.1.100", "root", "password123")

        assert result is True

    @patch("lab_testing.utils.credentials.check_ssh_key_installed")
    @patch("lab_testing.utils.credentials.subprocess.run")
    @patch("pathlib.Path.exists")
    def test_install_ssh_key_failure(self, mock_exists, mock_run, mock_check_key):
        """Test installing SSH key with failure"""
        # Mock key file exists
        mock_exists.return_value = True

        # Mock ssh-copy-id failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Installation failed"
        mock_run.return_value = mock_result

        # Mock key check - not installed
        mock_check_key.return_value = False

        result = install_ssh_key("192.168.1.100", "root", "password123")

        assert result is False


class TestSSHCommand:
    """Tests for get_ssh_command"""

    @patch("lab_testing.utils.credentials.check_ssh_key_installed")
    @patch("lab_testing.utils.credentials.get_credential")
    def test_get_ssh_command_with_key(self, mock_get_cred, mock_check_key):
        """Test getting SSH command with key-based auth"""
        mock_check_key.return_value = True
        mock_get_cred.return_value = None

        result = get_ssh_command("192.168.1.100", "root", "uptime", "device1")

        assert isinstance(result, list)
        assert "ssh" in result
        assert "192.168.1.100" in " ".join(result)
        assert "uptime" in " ".join(result)

    @patch("lab_testing.utils.credentials.check_ssh_key_installed")
    @patch("lab_testing.utils.credentials.get_credential")
    @patch("lab_testing.utils.credentials.subprocess.run")
    def test_get_ssh_command_with_password(self, mock_run, mock_get_cred, mock_check_key):
        """Test getting SSH command with password"""
        mock_check_key.return_value = False
        mock_get_cred.return_value = {"username": "root", "password": "secret"}

        # Mock sshpass availability
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = get_ssh_command("192.168.1.100", "root", "uptime", "device1")

        assert isinstance(result, list)
        # Should use sshpass when password is available
        assert any("sshpass" in str(arg) or "ssh" in str(arg) for arg in result)

    @patch("lab_testing.utils.credentials.check_ssh_key_installed")
    @patch("lab_testing.utils.credentials.get_credential")
    def test_get_ssh_command_no_auth(self, mock_get_cred, mock_check_key):
        """Test getting SSH command with no authentication"""
        mock_check_key.return_value = False
        mock_get_cred.return_value = None

        result = get_ssh_command("192.168.1.100", "root", "uptime", "device1")

        assert isinstance(result, list)
        assert "ssh" in result
