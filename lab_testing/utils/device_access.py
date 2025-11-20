"""
Unified Device Access Helper

Provides a unified interface for accessing both Foundries devices (via VPN IP)
and local config devices. Automatically detects device type and uses appropriate
access method.

For Foundries devices, if direct connection fails, automatically falls back to
connecting through the VPN server (device-to-device communication).

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from lab_testing.config import get_foundries_vpn_config, get_lab_devices_config
from lab_testing.tools.device_manager import load_device_config, resolve_device_identifier
from lab_testing.utils.credentials import get_ssh_command
from lab_testing.utils.foundries_vpn_cache import get_vpn_ip
from lab_testing.utils.logger import get_logger

logger = get_logger()


def get_unified_device_info(device_id_or_name: str) -> Dict[str, Any]:
    """
    Get device information for both Foundries and local devices.

    Checks:
    1. Foundries VPN IP cache (for Foundries devices)
    2. Local device config (for configured devices)

    Args:
        device_id_or_name: Device identifier or friendly name

    Returns:
        Dictionary with device info including:
        - device_id: Resolved device ID
        - ip: IP address (VPN IP for Foundries, config IP for local)
        - username: SSH username
        - ssh_port: SSH port
        - device_type: "foundries" or "local"
        - source: "vpn_cache" or "config"
    """
    # First check Foundries VPN IP cache
    vpn_ip = get_vpn_ip(device_id_or_name)
    if vpn_ip:
        logger.debug(f"Found Foundries device {device_id_or_name} in VPN cache: {vpn_ip}")
        return {
            "device_id": device_id_or_name,
            "ip": vpn_ip,
            "username": "fio",  # Default Foundries SSH user
            "ssh_port": 22,
            "device_type": "foundries",
            "source": "vpn_cache",
        }

    # Fall back to local device config
    try:
        device_id = resolve_device_identifier(device_id_or_name)
        if device_id:
            config = load_device_config()
            devices = config.get("devices", {})
            if device_id in devices:
                device = devices[device_id]
                ip = device.get("ip")
                if ip:
                    logger.debug(f"Found local device {device_id} in config: {ip}")
                    return {
                        "device_id": device_id,
                        "ip": ip,
                        "username": device.get("ssh_user", "root"),
                        "ssh_port": device.get("ports", {}).get("ssh", 22),
                        "device_type": "local",
                        "source": "config",
                    }
    except Exception as e:
        logger.debug(f"Error checking local config for {device_id_or_name}: {e}")

    # Not found in either source
    return {
        "error": f"Device '{device_id_or_name}' not found in VPN cache or local config",
    }


def _get_vpn_server_connection_info() -> Dict[str, Any]:
    """
    Get VPN server connection details for SSH fallback.

    Returns:
        Dictionary with server_host, server_port, server_user, server_password
    """
    server_host = None
    server_port = 5025  # Default SSH port for VPN server
    server_user = "root"
    server_password = None

    # Try to get server endpoint from VPN config
    # Note: Endpoint in VPN config is WireGuard port (e.g., 5555), not SSH port
    config_path = get_foundries_vpn_config()
    if config_path and config_path.exists():
        try:
            config_content = config_path.read_text()
            for line in config_content.split("\n"):
                line = line.strip()
                if line.startswith("Endpoint =") or line.startswith("Endpoint="):
                    endpoint = line.split("=", 1)[1].strip()
                    # Extract host from endpoint (e.g., "144.76.167.54:5555" -> "144.76.167.54")
                    # Note: The port in endpoint is WireGuard port, not SSH port
                    if ":" in endpoint:
                        server_host = endpoint.split(":")[0]
                    else:
                        server_host = endpoint
                    break
        except Exception:
            pass

    # Default server host if not found in config
    if not server_host:
        server_host = "proxmox.dynamicdevices.co.uk"

    # SSH port is always 5025 for our VPN server (not the WireGuard port from config)
    # This is hardcoded because SSH port is different from WireGuard port

    # Try to get password from environment or use default
    # In production, this should use SSH keys, but we support password as fallback
    import os

    server_password = os.getenv("FOUNDRIES_VPN_SERVER_PASSWORD", "decafbad00")

    return {
        "server_host": server_host,
        "server_port": server_port,
        "server_user": server_user,
        "server_password": server_password,
    }


def ssh_to_unified_device(
    device_id_or_name: str, command: str, username: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute SSH command on device (Foundries or local).

    Automatically detects device type and uses appropriate access method.
    For Foundries devices, if direct connection fails, falls back to
    connecting through the VPN server.

    Args:
        device_id_or_name: Device identifier or friendly name
        command: Command to execute
        username: Optional SSH username (overrides default)

    Returns:
        Dictionary with command results (success, stdout, stderr)
    """
    device_info = get_unified_device_info(device_id_or_name)
    if "error" in device_info:
        return {"success": False, "error": device_info["error"]}

    ip = device_info["ip"]
    ssh_port = device_info["ssh_port"]
    default_username = device_info["username"]
    device_type = device_info["device_type"]

    # Use provided username or device default
    ssh_username = username if username else default_username

    logger.debug(
        f"Executing SSH command on {device_type} device {device_id_or_name} ({ip}): {command}"
    )

    # Build SSH command for direct connection
    ssh_cmd = get_ssh_command(ip, ssh_username, command, device_id_or_name, use_password=False)

    # Add port if not default
    if ssh_port != 22:
        # Insert port option before username@ip
        username_ip = f"{ssh_username}@{ip}"
        if username_ip in ssh_cmd:
            port_idx = ssh_cmd.index(username_ip)
            ssh_cmd.insert(port_idx, "-p")
            ssh_cmd.insert(port_idx + 1, str(ssh_port))

    # Execute command - try direct connection first
    try:
        result = subprocess.run(
            ssh_cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,  # Shorter timeout for direct connection attempt
        )

        # If direct connection succeeds, return result
        if result.returncode == 0:
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "device_id": device_info["device_id"],
                "device_type": device_type,
                "ip": ip,
                "connection_method": "direct",
            }

        # If direct connection fails and this is a Foundries device, try server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct connection failed for Foundries device {device_id_or_name}, trying server fallback"
            )
            return _ssh_through_vpn_server(device_info, command, ssh_username)

        # For local devices or if fallback not applicable, return direct connection result
        return {
            "success": False,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "error": result.stderr.strip() if result.stderr else "SSH connection failed",
            "device_id": device_info["device_id"],
            "device_type": device_type,
            "ip": ip,
            "connection_method": "direct",
        }

    except subprocess.TimeoutExpired:
        # If timeout and Foundries device, try server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct connection timed out for Foundries device {device_id_or_name}, trying server fallback"
            )
            return _ssh_through_vpn_server(device_info, command, ssh_username)

        return {
            "success": False,
            "error": "SSH command timed out after 10 seconds",
            "device_id": device_info["device_id"],
            "device_type": device_type,
            "ip": ip,
            "connection_method": "direct",
        }
    except Exception as e:
        # If exception and Foundries device, try server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct connection exception for Foundries device {device_id_or_name}, trying server fallback: {e}"
            )
            return _ssh_through_vpn_server(device_info, command, ssh_username)

        return {
            "success": False,
            "error": f"SSH command failed: {e!s}",
            "device_id": device_info["device_id"],
            "device_type": device_type,
            "ip": ip,
            "connection_method": "direct",
        }


def _ssh_through_vpn_server(
    device_info: Dict[str, Any], command: str, username: str
) -> Dict[str, Any]:
    """
    Execute SSH command on Foundries device through VPN server.

    This is a fallback when direct connection fails. It SSHs to the VPN server,
    then from there SSHs to the device.

    Args:
        device_info: Device information dictionary
        command: Command to execute on device
        username: SSH username for device

    Returns:
        Dictionary with command results
    """
    device_ip = device_info["ip"]
    device_id = device_info["device_id"]
    device_password = "fio"  # Default Foundries device password

    # Get VPN server connection info
    server_info = _get_vpn_server_connection_info()
    server_host = server_info["server_host"]
    server_port = server_info["server_port"]
    server_user = server_info["server_user"]
    server_password = server_info["server_password"]

    logger.debug(
        f"Connecting to Foundries device {device_id} ({device_ip}) through VPN server {server_host}:{server_port}"
    )

    # Escape command for nested SSH
    # Escape single quotes by replacing ' with '\'' (end quote, escaped quote, start quote)
    command_escaped = command.replace("'", "'\\''")

    # Build nested SSH command: SSH to server, then SSH to device
    # Format: ssh server "sshpass -p 'password' ssh device 'command'"
    device_ssh_cmd = f"sshpass -p '{device_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {username}@{device_ip} '{command_escaped}'"

    # Build server SSH command
    if server_password:
        server_ssh_cmd = [
            "sshpass",
            "-p",
            server_password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-p",
            str(server_port),
            f"{server_user}@{server_host}",
            device_ssh_cmd,
        ]
    else:
        server_ssh_cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-p",
            str(server_port),
            f"{server_user}@{server_host}",
            device_ssh_cmd,
        ]

    try:
        result = subprocess.run(
            server_ssh_cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "device_id": device_info["device_id"],
            "device_type": device_info["device_type"],
            "ip": device_ip,
            "connection_method": "through_vpn_server",
            "server_host": server_host,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "SSH command through VPN server timed out after 60 seconds",
            "device_id": device_info["device_id"],
            "device_type": device_info["device_type"],
            "ip": device_ip,
            "connection_method": "through_vpn_server",
            "server_host": server_host,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"SSH command through VPN server failed: {e!s}",
            "device_id": device_info["device_id"],
            "device_type": device_info["device_type"],
            "ip": device_ip,
            "connection_method": "through_vpn_server",
            "server_host": server_host,
        }
