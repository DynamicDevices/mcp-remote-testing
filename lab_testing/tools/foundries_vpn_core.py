"""
Foundries VPN Core Functions

Core connection and status functions for Foundries VPN.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from lab_testing.config import get_foundries_vpn_config
from lab_testing.tools.foundries_vpn_helpers import (
    _check_fioctl_configured,
    _check_fioctl_installed,
)
from lab_testing.tools.foundries_vpn_server import get_foundries_vpn_server_config
from lab_testing.utils.logger import get_logger

logger = get_logger()


def foundries_vpn_status() -> Dict[str, Any]:
    """
    Get Foundries VPN connection status.

    Checks if connected to Foundries VPN server by examining WireGuard interfaces
    and checking if they're associated with Foundries VPN.

    Returns:
        Dictionary with Foundries VPN status information
    """
    try:
        # Check if fioctl is installed
        fioctl_installed, fioctl_error = _check_fioctl_installed()
        if not fioctl_installed:
            return {
                "success": False,
                "error": fioctl_error,
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                    "Follow installation instructions: https://docs.foundries.io/latest/reference-manual/fioctl/",
                ],
            }

        # Check if fioctl is configured
        fioctl_configured, config_error = _check_fioctl_configured()
        if not fioctl_configured:
            return {
                "success": False,
                "error": config_error,
                "suggestions": [
                    "Run 'fioctl login' to configure FoundriesFactory credentials",
                    "Ensure you have access to the FoundriesFactory",
                ],
            }

        # Check for active WireGuard interfaces (potential Foundries VPN)
        wg_result = subprocess.run(
            ["wg", "show"], check=False, capture_output=True, text=True, timeout=5
        )

        interfaces = []
        if wg_result.returncode == 0 and wg_result.stdout.strip():
            for line in wg_result.stdout.split("\n"):
                if line.startswith("interface:"):
                    interface_name = line.split(":")[1].strip()
                    interfaces.append({"name": interface_name, "status": "active"})

        # Check NetworkManager connections
        nm_result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,STATE", "connection", "show", "--active"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        nm_connections = []
        if nm_result.returncode == 0:
            for line in nm_result.stdout.strip().split("\n"):
                if line and "wireguard" in line.lower():
                    parts = line.split(":")
                    if len(parts) >= 4:
                        nm_connections.append(
                            {
                                "name": parts[0],
                                "type": parts[1],
                                "device": parts[2],
                                "state": parts[3],
                            }
                        )

        connected = len(interfaces) > 0 or len(nm_connections) > 0

        return {
            "success": True,
            "connected": connected,
            "fioctl_installed": True,
            "fioctl_configured": True,
            "wireguard_interfaces": interfaces,
            "networkmanager_connections": nm_connections,
            "message": "Foundries VPN connected" if connected else "Foundries VPN not connected",
            "next_steps": (
                ["Connect to Foundries VPN: connect_foundries_vpn()"]
                if not connected
                else ["List Foundries devices: list_foundries_devices()"]
            ),
        }

    except Exception as e:
        logger.error(f"Failed to get Foundries VPN status: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to get Foundries VPN status: {e!s}",
            "suggestions": [
                "Check if fioctl is installed: https://github.com/foundriesio/fioctl",
                "Check if WireGuard tools are installed",
            ],
        }


def connect_foundries_vpn(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Connect to Foundries VPN server.

    Requires a WireGuard configuration file obtained from FoundriesFactory.
    The config can be obtained via FoundriesFactory web interface or API.

    Args:
        config_path: Optional path to WireGuard config file for Foundries VPN.
                     If not provided, searches for Foundries VPN config in standard locations.

    Returns:
        Dictionary with connection results
    """
    try:
        # Check if fioctl is installed and configured
        fioctl_installed, fioctl_error = _check_fioctl_installed()
        if not fioctl_installed:
            return {
                "success": False,
                "error": fioctl_error,
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                    "Follow installation instructions: https://docs.foundries.io/latest/reference-manual/fioctl/",
                ],
            }

        fioctl_configured, config_error = _check_fioctl_configured()
        if not fioctl_configured:
            return {
                "success": False,
                "error": config_error,
                "suggestions": [
                    "Run 'fioctl login' to configure FoundriesFactory credentials",
                    "Ensure you have access to the FoundriesFactory",
                ],
            }

        # Find WireGuard config file
        if config_path:
            vpn_config = Path(config_path)
        else:
            # Use centralized config function to find Foundries VPN config
            vpn_config = get_foundries_vpn_config()

            if not vpn_config:
                return {
                    "success": False,
                    "error": "Foundries VPN configuration file not found",
                    "suggestions": [
                        "Obtain WireGuard config from FoundriesFactory",
                        "Place config file in one of these locations:",
                        "  - ~/.config/wireguard/foundries.conf",
                        "  - {LAB_TESTING_ROOT}/secrets/foundries-vpn.conf",
                        "  - {LAB_TESTING_ROOT}/secrets/foundries.conf",
                        "  - /etc/wireguard/foundries.conf",
                        "Or set FOUNDRIES_VPN_CONFIG_PATH environment variable",
                        "Or provide config_path parameter to connect_foundries_vpn()",
                        "See Foundries VPN documentation: https://docs.foundries.io/latest/reference-manual/remote-access/wireguard.html",
                    ],
                }

        if not vpn_config.exists():
            return {
                "success": False,
                "error": f"VPN configuration file not found: {vpn_config}",
            }

        # Try NetworkManager first (doesn't require root)
        nm_result = subprocess.run(
            ["nmcli", "connection", "import", "type", "wireguard", "file", str(vpn_config)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if nm_result.returncode == 0:
            # Import successful, configure to ONLY route VPN network (critical for internet connectivity)
            connection_name = vpn_config.stem

            # Parse AllowedIPs from config to set routes
            allowed_ips = []
            with open(vpn_config) as f:
                for line in f:
                    if line.strip().startswith("AllowedIPs"):
                        # Extract IPs from AllowedIPs = 10.42.42.0/24, ...
                        ips = line.split("=", 1)[1].strip()
                        allowed_ips = [ip.strip() for ip in ips.split(",")]
                        break

            # Configure NetworkManager to ONLY route VPN network, never default route
            if allowed_ips:
                routes_str = " ".join([f"ip = {ip}" for ip in allowed_ips])
                subprocess.run(
                    ["nmcli", "connection", "modify", connection_name, "ipv4.routes", routes_str],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )

            # CRITICAL: Prevent VPN from becoming default route
            subprocess.run(
                ["nmcli", "connection", "modify", connection_name, "ipv4.never-default", "yes"],
                check=False,
                capture_output=True,
                timeout=5,
            )

            # Connect
            connect_result = subprocess.run(
                ["nmcli", "connection", "up", connection_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if connect_result.returncode == 0:
                return {
                    "success": True,
                    "method": "networkmanager",
                    "connection": connection_name,
                    "message": f"Foundries VPN connected via NetworkManager: {connection_name}",
                    "next_steps": ["List Foundries devices: list_foundries_devices()"],
                }

        # Fallback: Try wg-quick (requires root)
        interface_name = vpn_config.stem
        wg_result = subprocess.run(
            ["sudo", "wg-quick", "up", str(vpn_config)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if wg_result.returncode == 0:
            return {
                "success": True,
                "method": "wg-quick",
                "interface": interface_name,
                "message": f"Foundries VPN connected: {interface_name}",
                "next_steps": ["List Foundries devices: list_foundries_devices()"],
            }

        error_output = wg_result.stderr.strip() if wg_result.stderr else "Unknown error"

        # Check if client peer might not be registered
        suggestions = [
            "Check VPN configuration file is valid",
            "Ensure WireGuard tools are installed",
            "Check if VPN server is accessible",
        ]

        # Try to check client peer registration if we can derive public key
        try:
            config_content = vpn_config.read_text()
            for line in config_content.split("\n"):
                if "PrivateKey" in line and "=" in line:
                    privkey = line.split("=", 1)[1].strip()
                    result = subprocess.run(
                        ["wg", "pubkey"],
                        check=False,
                        input=privkey.encode(),
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        pubkey = result.stdout.strip()
                        client_check = check_client_peer_registered(client_public_key=pubkey)
                        if client_check and not client_check.get("registered"):
                            suggestions.insert(
                                0, "⚠️  CRITICAL: Client peer may not be registered on server"
                            )
                            suggestions.insert(
                                1, "Check registration: check_client_peer_registered()"
                            )
                            suggestions.insert(
                                2,
                                "Register if needed: register_foundries_vpn_client() (requires admin)",
                            )
                            suggestions.insert(
                                3, "Or contact VPN admin: ajlennon@dynamicdevices.co.uk"
                            )
                        break
        except Exception:
            pass  # Ignore errors in client check

        return {
            "success": False,
            "error": f"Failed to connect to Foundries VPN: {error_output}",
            "suggestions": suggestions,
        }

    except Exception as e:
        logger.error(f"Failed to connect to Foundries VPN: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to connect to Foundries VPN: {e!s}",
            "suggestions": [
                "Check if fioctl is installed: https://github.com/foundriesio/fioctl",
                "Check if WireGuard tools are installed",
                "Verify VPN configuration file is valid",
                "Check VPN server accessibility",
                "⚠️  If connection fails, check client peer registration: check_client_peer_registered()",
            ],
        }


def verify_foundries_vpn_connection() -> Dict[str, Any]:
    """
    Verify that Foundries VPN connection is working.

    Tests connectivity to VPN server and checks routing.

    Returns:
        Dictionary with verification results
    """
    try:
        # Check VPN status
        status = foundries_vpn_status()
        if not status.get("success"):
            return {
                "success": False,
                "error": "Failed to check VPN status",
                "details": status,
            }

        if not status.get("connected"):
            # Check if client peer is registered (if we can determine public key)
            client_check = None
            try:
                config_path = get_foundries_vpn_config()
                if config_path and config_path.exists():
                    config_content = config_path.read_text()
                    for line in config_content.split("\n"):
                        if "PrivateKey" in line and "=" in line:
                            privkey = line.split("=", 1)[1].strip()
                            result = subprocess.run(
                                ["wg", "pubkey"],
                                check=False,
                                input=privkey.encode(),
                                capture_output=True,
                                text=True,
                                timeout=5,
                            )
                            if result.returncode == 0:
                                pubkey = result.stdout.strip()
                                client_check = check_client_peer_registered(
                                    client_public_key=pubkey
                                )
                                break
            except Exception:
                pass  # Ignore errors in client check

            suggestions = [
                "Connect to VPN: connect_foundries_vpn()",
                "Or run automated setup: setup_foundries_vpn()",
            ]

            if client_check and not client_check.get("registered"):
                suggestions.insert(0, "⚠️  CRITICAL: Client peer may not be registered on server")
                suggestions.insert(1, "Check registration: check_client_peer_registered()")
                suggestions.insert(
                    2, "Register if needed: register_foundries_vpn_client() (requires admin)"
                )
                suggestions.insert(3, "Or contact VPN admin: ajlennon@dynamicdevices.co.uk")

            return {
                "success": False,
                "error": "VPN is not connected",
                "details": status,
                "client_peer_check": client_check if client_check else None,
                "suggestions": suggestions,
            }

        # Get server config to know server IP
        server_config = get_foundries_vpn_server_config()
        if not server_config.get("success"):
            return {
                "success": False,
                "error": "Failed to get server configuration",
                "details": server_config,
            }

        server_ip = server_config.get("address", "").split("/")[0]  # Remove /24 if present
        if not server_ip:
            return {
                "success": False,
                "error": "Server IP not found in configuration",
            }

        # Test ping to VPN server
        ping_result = subprocess.run(
            ["ping", "-c", "2", "-W", "2", server_ip],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        ping_success = ping_result.returncode == 0

        # Check WireGuard interface
        wg_result = subprocess.run(
            ["wg", "show"], check=False, capture_output=True, text=True, timeout=5
        )

        wg_interfaces = []
        if wg_result.returncode == 0:
            for line in wg_result.stdout.split("\n"):
                if line.startswith("interface:"):
                    interface_name = line.split(":")[1].strip()
                    wg_interfaces.append(interface_name)

        return {
            "success": True,
            "connected": True,
            "ping_to_server": ping_success,
            "server_ip": server_ip,
            "wireguard_interfaces": wg_interfaces,
            "message": (
                "VPN connection verified successfully"
                if ping_success
                else "VPN connected but server not reachable"
            ),
            "next_steps": (
                ["List devices: list_foundries_devices()"]
                if ping_success
                else [
                    "Check VPN server is running",
                    "Check firewall rules",
                    "Verify server IP is correct",
                ]
            ),
        }

    except Exception as e:
        logger.error(f"Failed to verify VPN connection: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Verification failed: {e!s}",
            "suggestions": [
                "Check VPN is connected",
                "Check WireGuard tools are installed",
            ],
        }
