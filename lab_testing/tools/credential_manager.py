"""
Credential Management Tools for MCP Server

Tools for managing SSH credentials and keys.
"""

from typing import Any, Dict, Optional

from lab_testing.exceptions import DeviceNotFoundError
from lab_testing.tools.device_manager import load_device_config, resolve_device_identifier
from lab_testing.utils.credentials import (
    cache_credential,
    check_ssh_key_installed,
    get_credential,
    install_ssh_key,
)
from lab_testing.utils.logger import get_logger

logger = get_logger()


def cache_device_credentials(
    device_id: str,
    username: str,
    password: Optional[str] = None,
    credential_type: str = "ssh",
) -> Dict[str, Any]:
    """
    Cache SSH credentials (username/password) for a device.
    Credentials are stored securely in ~/.cache/ai-lab-testing/credentials.json.
    Prefer SSH keys over passwords when possible.

    Args:
        device_id: Device identifier (device_id or friendly_name)
        username: SSH username
        password: SSH password (optional, prefer SSH keys)
        credential_type: Type of credential (ssh, sudo)

    Returns:
        Dictionary with operation results
    """
    # Resolve to actual device_id
    resolved_device_id = resolve_device_identifier(device_id)
    if not resolved_device_id:
        error_msg = f"Device '{device_id}' not found"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
        }

    try:
        # Cache the credential
        cache_credential(resolved_device_id, username, password, credential_type)

        logger.info(
            f"Cached {credential_type} credentials for {resolved_device_id} (username: {username})"
        )

        return {
            "success": True,
            "device_id": resolved_device_id,
            "friendly_name": device_id,
            "username": username,
            "credential_type": credential_type,
            "message": f"Credentials cached successfully for {resolved_device_id}",
        }

    except Exception as e:
        error_msg = f"Failed to cache credentials: {e!s}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }


def check_ssh_key_status(device_id: str, username: Optional[str] = None) -> Dict[str, Any]:
    """
    Check if SSH key authentication is working for a device.

    Args:
        device_id: Device identifier (device_id or friendly_name)
        username: SSH username (optional, uses device default)

    Returns:
        Dictionary with SSH key status
    """
    # Resolve to actual device_id
    resolved_device_id = resolve_device_identifier(device_id)
    if not resolved_device_id:
        error_msg = f"Device '{device_id}' not found"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
        }

    config = load_device_config()
    devices = config.get("devices", {})
    device = devices.get(resolved_device_id)

    if not device:
        error_msg = f"Device '{resolved_device_id}' not found in config"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }

    ip = device.get("ip")
    if not ip:
        error_msg = f"Device '{resolved_device_id}' has no IP address"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }

    # Determine username
    if not username:
        username = device.get("ssh_user", "root")

    # Check if SSH key is installed
    try:
        key_installed = check_ssh_key_installed(ip, username)

        # Check for default SSH keys
        from pathlib import Path

        ssh_key_paths = [
            Path.home() / ".ssh" / "id_rsa.pub",
            Path.home() / ".ssh" / "id_ed25519.pub",
        ]
        default_key_exists = any(path.exists() for path in ssh_key_paths)

        return {
            "success": True,
            "device_id": resolved_device_id,
            "friendly_name": device.get("friendly_name") or device.get("name", resolved_device_id),
            "ip": ip,
            "username": username,
            "key_installed": key_installed,
            "default_key_exists": default_key_exists,
            "message": (
                "SSH key authentication is working"
                if key_installed
                else "SSH key authentication is not working (use install_ssh_key to install)"
            ),
        }

    except Exception as e:
        error_msg = f"Failed to check SSH key status: {e!s}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }


def install_ssh_key_on_device(
    device_id: str, username: Optional[str] = None, password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Install SSH public key on target device for passwordless access.
    Uses default SSH key from ~/.ssh/id_rsa.pub or ~/.ssh/id_ed25519.pub.
    Requires password for initial access if key not already installed.

    Args:
        device_id: Device identifier (device_id or friendly_name)
        username: SSH username (optional, uses device default)
        password: Password for initial access (if key not installed, uses cached/default if available)

    Returns:
        Dictionary with installation results
    """
    # Resolve to actual device_id
    resolved_device_id = resolve_device_identifier(device_id)
    if not resolved_device_id:
        error_msg = f"Device '{device_id}' not found"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
        }

    config = load_device_config()
    devices = config.get("devices", {})
    device = devices.get(resolved_device_id)

    if not device:
        error_msg = f"Device '{resolved_device_id}' not found in config"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }

    ip = device.get("ip")
    if not ip:
        error_msg = f"Device '{resolved_device_id}' has no IP address"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }

    # Determine username
    if not username:
        username = device.get("ssh_user", "root")

    # Get password if not provided (try cached/default credentials)
    if not password:
        cred = get_credential(resolved_device_id, "ssh")
        if cred and cred.get("password"):
            password = cred["password"]
            # Use username from credential if available
            if cred.get("username"):
                username = cred["username"]

    try:
        # Check if key already installed
        if check_ssh_key_installed(ip, username):
            return {
                "success": True,
                "device_id": resolved_device_id,
                "friendly_name": device.get("friendly_name") or device.get("name", resolved_device_id),
                "ip": ip,
                "username": username,
                "key_already_installed": True,
                "message": "SSH key is already installed and working",
            }

        # Install the key
        if not password:
            return {
                "success": False,
                "error": "Password required for initial SSH key installation. Provide password parameter or cache credentials first.",
                "device_id": resolved_device_id,
                "suggestion": "Use cache_device_credentials to cache password, or provide password parameter",
            }

        key_installed = install_ssh_key(ip, username, password)

        if key_installed:
            logger.info(f"Successfully installed SSH key on {resolved_device_id} ({ip})")
            return {
                "success": True,
                "device_id": resolved_device_id,
                "friendly_name": device.get("friendly_name") or device.get("name", resolved_device_id),
                "ip": ip,
                "username": username,
                "key_installed": True,
                "message": "SSH key installed successfully",
            }
        else:
            return {
                "success": False,
                "error": "Failed to install SSH key. Check password and device connectivity.",
                "device_id": resolved_device_id,
                "ip": ip,
                "username": username,
            }

    except Exception as e:
        error_msg = f"Failed to install SSH key: {e!s}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }

