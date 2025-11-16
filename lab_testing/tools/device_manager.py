"""
Device Management Tools for MCP Server
"""

import json
import subprocess
from typing import Any, Dict, Optional

from lab_testing.config import get_lab_devices_config
from lab_testing.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    SSHError,
)
from lab_testing.utils.logger import get_logger

logger = get_logger()


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
        friendly_name = device_info.get("friendly_name") or device_info.get("name", device_id)
        by_type[device_type].append({
            "id": device_id,
            "friendly_name": friendly_name,
            "name": device_info.get("name", "Unknown"),
            "hostname": device_info.get("hostname"),  # Unique ID from hostname
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


def test_device(device_id_or_name: str) -> Dict[str, Any]:
    """
    Test connectivity to a specific device.
    
    Supports both device_id and friendly_name lookup.

    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)

    Returns:
        Dictionary with test results
    """
    # Resolve to actual device_id
    device_id = resolve_device_identifier(device_id_or_name)
    if not device_id:
        error_msg = f"Device '{device_id_or_name}' not found in configuration"
        logger.error(error_msg)
        raise DeviceNotFoundError(error_msg, device_id=device_id_or_name)
    
    config = load_device_config()
    devices = config.get("devices", {})

    device = devices[device_id]
    ip = device.get("ip")

    if not ip:
        error_msg = f"Device '{device_id}' has no IP address configured"
        logger.error(error_msg)
        raise DeviceConnectionError(error_msg, device_id=device_id)

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

        friendly_name = device.get("friendly_name") or device.get("name", device_id)
        
        return {
            "success": True,
            "device_id": device_id,
            "friendly_name": friendly_name,
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


def ssh_to_device(device_id_or_name: str, command: str, username: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute an SSH command on a device.
    
    Supports both device_id and friendly_name lookup.

    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)
        command: Command to execute
        username: SSH username (optional, uses device default if not specified)

    Returns:
        Dictionary with command results
    """
    # Resolve to actual device_id
    device_id = resolve_device_identifier(device_id_or_name)
    if not device_id:
        error_msg = f"Device '{device_id_or_name}' not found"
        logger.error(error_msg)
        raise DeviceNotFoundError(error_msg, device_id=device_id_or_name)
    
    config = load_device_config()
    devices = config.get("devices", {})

    device = devices[device_id]
    ip = device.get("ip")
    ssh_port = device.get("ports", {}).get("ssh", 22)

    if not ip:
        error_msg = f"Device '{device_id}' has no IP address"
        logger.error(error_msg)
        raise DeviceConnectionError(error_msg, device_id=device_id)

    logger.debug(f"Executing SSH command on {device_id} ({ip}): {command}")

    # Determine username
    if not username:
        username = device.get("ssh_user", "root")

    # Record change for tracking
    from lab_testing.utils.change_tracker import record_ssh_command
    change_id = record_ssh_command(device_id, command)

    # Execute SSH command with preferred authentication
    # Try connection pool first, fallback to direct connection
    try:
        from lab_testing.utils.process_manager import ensure_single_process
        from lab_testing.utils.ssh_pool import execute_via_pool

        # Check if this command might conflict with existing processes
        # Extract process name from command for conflict detection
        process_pattern = None
        if command.strip():
            # Simple heuristic: use first word as process name
            first_word = command.strip().split()[0]
            if first_word and "/" not in first_word and first_word not in ["echo", "test", "cat", "grep"]:
                process_pattern = first_word
                # Ensure no conflicting process is running
                ensure_single_process(ip, username, device_id, process_pattern, command, kill_existing=True, force_kill=False)

        # Try using connection pool
        try:
            result = execute_via_pool(ip, username, command, device_id, ssh_port)
            logger.debug(f"Executed via connection pool: {device_id}")
        except Exception as pool_error:
            logger.debug(f"Connection pool failed for {device_id}, using direct connection: {pool_error}")
            # Fallback to direct connection
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

        friendly_name = device.get("friendly_name") or device.get("name", device_id)
        
        return {
            "success": result.returncode == 0,
            "device_id": device_id,
            "friendly_name": friendly_name,
            "device_name": device.get("name", "Unknown"),
            "ip": ip,
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "change_id": change_id  # Include change tracking ID
        }

    except subprocess.TimeoutExpired:
        error_msg = "SSH command timed out"
        logger.warning(f"SSH timeout for {device_id}: {command}")
        raise DeviceTimeoutError(error_msg, device_id=device_id)
    except Exception as e:
        error_msg = f"SSH execution failed: {e!s}"
        logger.error(f"SSH error for {device_id}: {e}", exc_info=True)
        raise SSHError(error_msg, device_id=device_id, command=command)


def resolve_device_identifier(identifier: str) -> Optional[str]:
    """
    Resolve a device identifier (device_id or friendly_name) to the actual device_id.
    
    Devices can be referenced by:
    - device_id (unique ID, typically from hostname/SOC ID)
    - friendly_name (user-friendly name configured in device config)
    
    Args:
        identifier: Device identifier (device_id or friendly_name)
        
    Returns:
        Actual device_id if found, None otherwise
    """
    config = load_device_config()
    devices = config.get("devices", {})
    
    # First, check if it's a direct device_id match
    if identifier in devices:
        return identifier
    
    # Then, search by friendly_name
    for device_id, device_info in devices.items():
        friendly_name = device_info.get("friendly_name") or device_info.get("name")
        if friendly_name and friendly_name.lower() == identifier.lower():
            return device_id
        
        # Also check if identifier matches the "name" field
        if device_info.get("name", "").lower() == identifier.lower():
            return device_id
    
    return None


def get_device_info(device_id_or_name: str) -> Optional[Dict[str, Any]]:
    """
    Get device information from configuration.
    
    Supports both device_id and friendly_name lookup.
    
    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)
        
    Returns:
        Device information dictionary or None if not found
    """
    # Resolve to actual device_id
    device_id = resolve_device_identifier(device_id_or_name)
    if not device_id:
        return None
    
    config = load_device_config()
    devices = config.get("devices", {})
    
    if device_id in devices:
        device = devices[device_id].copy()
        device["device_id"] = device_id
        # Ensure friendly_name is set (use name if friendly_name not set)
        if "friendly_name" not in device:
            device["friendly_name"] = device.get("name", device_id)
        return device
    return None

