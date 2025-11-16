"""
Device Management Tools for MCP Server
"""

import json
import subprocess
from typing import Any, Dict, Optional

from mcp_remote_testing.config import get_lab_devices_config


def load_device_config() -> Dict[str, Any]:
    """Load device configuration from JSON file"""
    config_path = get_lab_devices_config()
    try:
        with open(config_path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"devices": {}, "lab_infrastructure": {}}
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parsing device configuration: {e}")


def list_devices() -> Dict[str, Any]:
    """
    List all configured lab devices with their status and details.

    Returns:
        Dictionary containing device list and summary information
    """
    config = load_device_config()
    devices = config.get("devices", {})

    # Organize devices by type
    by_type = {}
    for device_id, device_info in devices.items():
        device_type = device_info.get("device_type", "other")
        if device_type not in by_type:
            by_type[device_type] = []
        by_type[device_type].append({
            "id": device_id,
            "name": device_info.get("name", "Unknown"),
            "ip": device_info.get("ip", "Unknown"),
            "status": device_info.get("status", "unknown"),
            "last_tested": device_info.get("last_tested")
        })

    # Get infrastructure info
    infrastructure = config.get("lab_infrastructure", {})
    vpn_info = infrastructure.get("wireguard_vpn", {})

    return {
        "total_devices": len(devices),
        "devices_by_type": by_type,
        "vpn_gateway": vpn_info.get("gateway_host", "Unknown"),
        "lab_networks": infrastructure.get("network_access", {}).get("lab_networks", []),
        "summary": f"Found {len(devices)} configured devices across {len(by_type)} categories"
    }


def test_device(device_id: str) -> Dict[str, Any]:
    """
    Test connectivity to a specific device.

    Args:
        device_id: Identifier of the device to test

    Returns:
        Dictionary with test results
    """
    config = load_device_config()
    devices = config.get("devices", {})

    if device_id not in devices:
        return {
            "success": False,
            "error": f"Device '{device_id}' not found in configuration"
        }

    device = devices[device_id]
    ip = device.get("ip")

    if not ip:
        return {
            "success": False,
            "error": f"Device '{device_id}' has no IP address configured"
        }

    # Test connectivity
    try:
        result = subprocess.run(
            ["ping", "-c", "3", "-W", "2", ip],
            check=False, capture_output=True,
            text=True,
            timeout=10
        )

        reachable = result.returncode == 0

        # Test SSH if device has SSH port
        ssh_available = False
        if device.get("ports", {}).get("ssh"):
            ssh_result = subprocess.run(
                ["nc", "-z", "-w", "2", ip, str(device["ports"]["ssh"])],
                check=False, capture_output=True,
                timeout=5
            )
            ssh_available = ssh_result.returncode == 0

        return {
            "success": True,
            "device_id": device_id,
            "device_name": device.get("name", "Unknown"),
            "ip": ip,
            "ping_reachable": reachable,
            "ssh_available": ssh_available,
            "ping_output": result.stdout if reachable else result.stderr
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "device_id": device_id,
            "ip": ip,
            "error": "Connection test timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "device_id": device_id,
            "ip": ip,
            "error": f"Test failed: {e!s}"
        }


def ssh_to_device(device_id: str, command: str, username: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute an SSH command on a device.

    Args:
        device_id: Identifier of the device
        command: Command to execute
        username: SSH username (optional, uses device default if not specified)

    Returns:
        Dictionary with command results
    """
    config = load_device_config()
    devices = config.get("devices", {})

    if device_id not in devices:
        return {
            "success": False,
            "error": f"Device '{device_id}' not found"
        }

    device = devices[device_id]
    ip = device.get("ip")
    ssh_port = device.get("ports", {}).get("ssh", 22)

    if not ip:
        return {
            "success": False,
            "error": f"Device '{device_id}' has no IP address"
        }

    # Determine username
    if not username:
        username = device.get("ssh_user", "root")

    # Execute SSH command with preferred authentication
    try:
        # Prefer SSH key authentication, fallback to password if needed
        ssh_cmd = get_ssh_command(ip, username, command, device_id, use_password=False)

        # Add port if not default
        if ssh_port != 22:
            # Insert port option before username@ip
            port_idx = ssh_cmd.index(f"{username}@{ip}")
            ssh_cmd.insert(port_idx, "-p")
            ssh_cmd.insert(port_idx + 1, str(ssh_port))

        result = subprocess.run(
            ssh_cmd,
            check=False, capture_output=True,
            text=True,
            timeout=30
        )

        return {
            "success": result.returncode == 0,
            "device_id": device_id,
            "device_name": device.get("name", "Unknown"),
            "ip": ip,
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "device_id": device_id,
            "error": "SSH command timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "device_id": device_id,
            "error": f"SSH execution failed: {e!s}"
        }

