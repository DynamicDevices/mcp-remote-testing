"""
VPN Management Tools for MCP Server
"""

import subprocess
from typing import Any, Dict

from mcp_remote_testing.config import get_vpn_config


def get_vpn_status() -> Dict[str, Any]:
    """
    Get current WireGuard VPN connection status.

    Returns:
        Dictionary with VPN status information
    """
    try:
        # Check for active WireGuard interfaces
        result = subprocess.run(
            ["wg", "show"],
            check=False, capture_output=True,
            text=True,
            timeout=5
        )

        interfaces = []
        if result.returncode == 0 and result.stdout.strip():
            # Parse wg show output
            current_interface = None
            for line in result.stdout.split("\n"):
                if line.startswith("interface:"):
                    current_interface = line.split(":")[1].strip()
                    interfaces.append({
                        "name": current_interface,
                        "status": "active"
                    })

        # Check NetworkManager connections
        nm_result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,STATE", "connection", "show", "--active"],
            check=False, capture_output=True,
            text=True,
            timeout=5
        )

        nm_connections = []
        if nm_result.returncode == 0:
            for line in nm_result.stdout.strip().split("\n"):
                if line and "wireguard" in line.lower():
                    parts = line.split(":")
                    if len(parts) >= 4:
                        nm_connections.append({
                            "name": parts[0],
                            "type": parts[1],
                            "device": parts[2],
                            "state": parts[3]
                        })

        vpn_config = get_vpn_config()

        return {
            "connected": len(interfaces) > 0 or len(nm_connections) > 0,
            "wireguard_interfaces": interfaces,
            "networkmanager_connections": nm_connections,
            "config_file": str(vpn_config) if vpn_config else None,
            "config_exists": vpn_config is not None and vpn_config.exists()
        }

    except FileNotFoundError:
        return {
            "connected": False,
            "error": "WireGuard tools not found. Install wireguard-tools package."
        }
    except Exception as e:
        return {
            "connected": False,
            "error": f"Failed to check VPN status: {e!s}"
        }


def connect_vpn() -> Dict[str, Any]:
    """
    Connect to WireGuard VPN.

    Note: This typically requires root privileges. The MCP server should
    be configured to allow this, or use NetworkManager GUI method instead.

    Returns:
        Dictionary with connection results
    """
    vpn_config = get_vpn_config()

    if not vpn_config or not vpn_config.exists():
        return {
            "success": False,
            "error": "VPN configuration file not found"
        }

    try:
        # Try using NetworkManager first (doesn't require root for user connections)
        nm_result = subprocess.run(
            ["nmcli", "connection", "up", "wg0-lab-only"],
            check=False, capture_output=True,
            text=True,
            timeout=10
        )

        if nm_result.returncode == 0:
            return {
                "success": True,
                "method": "networkmanager",
                "message": "VPN connected via NetworkManager"
            }

        # Fallback: Try wg-quick (requires root)
        wg_result = subprocess.run(
            ["sudo", "wg-quick", "up", str(vpn_config)],
            check=False, capture_output=True,
            text=True,
            timeout=10
        )

        if wg_result.returncode == 0:
            return {
                "success": True,
                "method": "wg-quick",
                "message": "VPN connected via wg-quick"
            }
        return {
            "success": False,
            "error": f"Failed to connect VPN: {wg_result.stderr}",
            "nm_error": nm_result.stderr
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "VPN connection attempt timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"VPN connection failed: {e!s}"
        }


def disconnect_vpn() -> Dict[str, Any]:
    """
    Disconnect from WireGuard VPN.

    Returns:
        Dictionary with disconnection results
    """
    try:
        # Try NetworkManager first
        nm_result = subprocess.run(
            ["nmcli", "connection", "down", "wg0-lab-only"],
            check=False, capture_output=True,
            text=True,
            timeout=10
        )

        if nm_result.returncode == 0:
            return {
                "success": True,
                "method": "networkmanager",
                "message": "VPN disconnected via NetworkManager"
            }

        # Try to find and disconnect any WireGuard interfaces
        wg_result = subprocess.run(
            ["wg", "show", "all", "dump"],
            check=False, capture_output=True,
            text=True,
            timeout=5
        )

        if wg_result.returncode == 0 and wg_result.stdout.strip():
            # Find interface name from first line
            first_line = wg_result.stdout.split("\n")[0]
            if first_line:
                interface_name = first_line.split("\t")[0]
                down_result = subprocess.run(
                    ["sudo", "wg-quick", "down", interface_name],
                    check=False, capture_output=True,
                    text=True,
                    timeout=10
                )

                if down_result.returncode == 0:
                    return {
                        "success": True,
                        "method": "wg-quick",
                        "interface": interface_name,
                        "message": f"VPN disconnected: {interface_name}"
                    }

        return {
            "success": True,
            "message": "No active VPN connections found"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to disconnect VPN: {e!s}"
        }

