"""
Foundries.io VPN Management Tools for MCP Server

Provides tools for managing Foundries VPN connections and devices.
Foundries VPN uses WireGuard but with a server-based architecture where
devices connect to a centralized VPN server managed by FoundriesFactory.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from lab_testing.config import get_foundries_vpn_config
from lab_testing.utils.foundries_vpn_cache import (
    cache_vpn_ip,
    get_all_cached_ips,
    get_vpn_ip,
    remove_vpn_ip,
)
from lab_testing.utils.logger import get_logger

logger = get_logger()


def _check_fioctl_installed() -> tuple:
    """
    Check if fioctl CLI tool is installed.

    Checks both PATH and common installation locations.

    Returns:
        Tuple of (is_installed, error_message)
    """
    fioctl_path = _get_fioctl_path()
    if not fioctl_path:
        return (
            False,
            "fioctl not found in PATH or common locations. Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
        )

    # Verify fioctl works by checking version (fioctl uses 'version' subcommand, not '--version')
    try:
        result = subprocess.run(
            [fioctl_path, "version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, None
    except Exception as e:
        return False, f"fioctl found but failed to execute: {e!s}"

    return False, "fioctl found but version check failed"


def _get_fioctl_path() -> Optional[str]:
    """
    Get the path to fioctl executable.

    Returns:
        Path to fioctl, or None if not found
    """
    import shutil

    # Check PATH first
    fioctl_path = shutil.which("fioctl")
    if fioctl_path:
        return fioctl_path

    # Check common installation locations
    common_paths = [
        "/usr/local/bin/fioctl",
        "/usr/bin/fioctl",
        Path.home() / ".local/bin/fioctl",
    ]

    for path in common_paths:
        path_str = str(path) if isinstance(path, Path) else path
        if Path(path_str).exists():
            return path_str

    return None


def _check_fioctl_configured() -> tuple:
    """
    Check if fioctl is configured with Factory credentials.

    Returns:
        Tuple of (is_configured, error_message)
    """
    fioctl_path = _get_fioctl_path()
    if not fioctl_path:
        return False, "fioctl not found"

    try:
        result = subprocess.run(
            [fioctl_path, "factories", "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, None
        return False, "fioctl not configured. Run 'fioctl login' to configure credentials"
    except Exception as e:
        return False, f"Failed to check fioctl configuration: {e!s}"


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


def get_foundries_vpn_server_config(factory: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Foundries VPN server configuration using fioctl API.

    Returns WireGuard server endpoint, address, and public key.

    Args:
        factory: Optional factory name (defaults to configured factory)

    Returns:
        Dictionary with VPN server configuration
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
                ],
            }

        fioctl_configured, config_error = _check_fioctl_configured()
        if not fioctl_configured:
            return {
                "success": False,
                "error": config_error,
                "suggestions": [
                    "Run 'fioctl login' to configure FoundriesFactory credentials",
                ],
            }

        # Get fioctl path
        fioctl_path = _get_fioctl_path()
        if not fioctl_path:
            return {
                "success": False,
                "error": "fioctl not found",
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                ],
            }

        # Get WireGuard server config
        cmd = [fioctl_path, "config", "wireguard"]
        if factory:
            cmd.extend(["--factory", factory])

        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return {
                "success": False,
                "error": f"Failed to get VPN server config: {error_msg}",
                "suggestions": [
                    "Check fioctl is configured correctly: 'fioctl factories list'",
                    "Ensure you have access to the factory",
                ],
            }

        # Parse output
        config = {}
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                config[key] = value

        enabled = config.get("enabled", "false").lower() == "true"

        return {
            "success": True,
            "enabled": enabled,
            "endpoint": config.get("endpoint", ""),
            "address": config.get("address", ""),
            "public_key": config.get("public_key", ""),
            "factory": factory or "default",
            "message": (
                "VPN server config retrieved successfully" if enabled else "VPN server is disabled"
            ),
            "next_steps": (
                ["Enable VPN on devices: enable_foundries_vpn_device(device_name)"]
                if enabled
                else ["Enable VPN server in FoundriesFactory"]
            ),
        }

    except Exception as e:
        logger.error(f"Failed to get VPN server config: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to get VPN server config: {e!s}",
            "suggestions": [
                "Check if fioctl is installed: https://github.com/foundriesio/fioctl",
                "Check if fioctl is configured: Run 'fioctl login'",
            ],
        }


def enable_foundries_vpn_device(device_name: str, factory: Optional[str] = None) -> Dict[str, Any]:
    """
    Enable WireGuard VPN on a Foundries device.

    Uses fioctl to enable WireGuard configuration on a device.
    The device will connect to the Foundries VPN server after OTA update (up to 5 minutes).

    Args:
        device_name: Name of the device to enable VPN on
        factory: Optional factory name. If not provided, uses default factory from fioctl config.

    Returns:
        Dictionary with operation results
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
                ],
            }

        fioctl_configured, config_error = _check_fioctl_configured()
        if not fioctl_configured:
            return {
                "success": False,
                "error": config_error,
                "suggestions": [
                    "Run 'fioctl login' to configure FoundriesFactory credentials",
                ],
            }

        # Get fioctl path
        fioctl_path = _get_fioctl_path()
        if not fioctl_path:
            return {
                "success": False,
                "error": "fioctl not found",
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                ],
            }

        # Build fioctl command
        cmd = [fioctl_path, "devices", "config", "wireguard", device_name, "enable"]
        if factory:
            cmd.extend(["--factory", factory])

        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {
                "success": True,
                "device_name": device_name,
                "factory": factory or "default",
                "message": f"WireGuard VPN enabled on device '{device_name}'. Configuration will be applied via OTA update (up to 5 minutes).",
                "next_steps": [
                    "Wait for OTA update to complete (up to 5 minutes)",
                    "Check device status: list_foundries_devices()",
                    "Connect to Foundries VPN: connect_foundries_vpn()",
                ],
            }

        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        return {
            "success": False,
            "error": f"Failed to enable WireGuard VPN on device '{device_name}': {error_msg}",
            "suggestions": [
                "Verify device name is correct: list_foundries_devices()",
                "Check device exists in factory",
                "Ensure you have permissions to configure devices",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to enable Foundries VPN on device: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to enable Foundries VPN on device: {e!s}",
            "suggestions": [
                "Check if fioctl is installed: https://github.com/foundriesio/fioctl",
                "Check if fioctl is configured: Run 'fioctl login'",
                "Verify device name is correct: list_foundries_devices()",
                "Check device exists in factory",
            ],
        }


def disable_foundries_vpn_device(device_name: str, factory: Optional[str] = None) -> Dict[str, Any]:
    """
    Disable WireGuard VPN on a Foundries device.

    Uses fioctl to disable WireGuard configuration on a device.
    The device will disconnect from the Foundries VPN server after OTA update (up to 5 minutes).

    Args:
        device_name: Name of the device to disable VPN on
        factory: Optional factory name. If not provided, uses default factory from fioctl config.

    Returns:
        Dictionary with operation results
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
                ],
            }

        fioctl_configured, config_error = _check_fioctl_configured()
        if not fioctl_configured:
            return {
                "success": False,
                "error": config_error,
                "suggestions": [
                    "Run 'fioctl login' to configure FoundriesFactory credentials",
                ],
            }

        # Get fioctl path
        fioctl_path = _get_fioctl_path()
        if not fioctl_path:
            return {
                "success": False,
                "error": "fioctl not found",
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                ],
            }

        # Build fioctl command
        cmd = [fioctl_path, "devices", "config", "wireguard", device_name, "disable"]
        if factory:
            cmd.extend(["--factory", factory])

        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {
                "success": True,
                "device_name": device_name,
                "factory": factory or "default",
                "message": f"WireGuard VPN disabled on device '{device_name}'. Configuration will be applied via OTA update (up to 5 minutes).",
                "next_steps": [
                    "Wait for OTA update to complete (up to 5 minutes)",
                    "Check device status: list_foundries_devices()",
                ],
            }

        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        return {
            "success": False,
            "error": f"Failed to disable WireGuard VPN on device '{device_name}': {error_msg}",
            "suggestions": [
                "Verify device name is correct: list_foundries_devices()",
                "Check device exists in factory",
                "Ensure you have permissions to configure devices",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to disable Foundries VPN on device: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to disable Foundries VPN on device: {e!s}",
            "suggestions": [
                "Check if fioctl is installed: https://github.com/foundriesio/fioctl",
                "Check if fioctl is configured: Run 'fioctl login'",
                "Verify device name is correct: list_foundries_devices()",
                "Check device exists in factory",
            ],
        }


def manage_foundries_vpn_ip_cache(
    action: str = "get",
    device_name: Optional[str] = None,
    vpn_ip: Optional[str] = None,
    refresh_from_server: bool = False,
    server_host: Optional[str] = None,
    server_port: int = 5025,
    server_user: str = "root",
    server_password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Manage Foundries VPN IP address cache.

    This tool allows you to query, update, and refresh the cache of Foundries device VPN IP addresses.
    The cache is populated from the WireGuard server's /etc/hosts file or manually.

    Args:
        action: Action to perform - "get" (get IP for device), "list" (list all cached IPs),
                "set" (manually set IP), "remove" (remove entry), "refresh" (refresh from server)
        device_name: Foundries device name (required for get/set/remove actions)
        vpn_ip: VPN IP address (required for set action)
        refresh_from_server: If True, refresh cache from WireGuard server /etc/hosts (for refresh action)
        server_host: WireGuard server hostname/IP (default: from config or "proxmox.dynamicdevices.co.uk")
        server_port: SSH port on WireGuard server (default: 5025)
        server_user: SSH user for WireGuard server (default: "root")
        server_password: SSH password for WireGuard server (if not using SSH keys)

    Returns:
        Dictionary with operation results
    """
    try:
        if action == "get":
            if not device_name:
                return {
                    "success": False,
                    "error": "device_name is required for 'get' action",
                }

            cached_ip = get_vpn_ip(device_name)
            if cached_ip:
                return {
                    "success": True,
                    "device_name": device_name,
                    "vpn_ip": cached_ip,
                    "cached": True,
                }
            return {
                "success": False,
                "device_name": device_name,
                "error": "VPN IP not found in cache",
                "suggestions": [
                    "Refresh cache from server: manage_foundries_vpn_ip_cache(action='refresh')",
                    "Manually set IP: manage_foundries_vpn_ip_cache(action='set', device_name='...', vpn_ip='...')",
                    "List all cached IPs: manage_foundries_vpn_ip_cache(action='list')",
                ],
            }

        if action == "list":
            cached_ips = get_all_cached_ips()
            devices = []
            for dev_name, entry in cached_ips.items():
                devices.append(
                    {
                        "device_name": dev_name,
                        "vpn_ip": entry.get("vpn_ip"),
                        "source": entry.get("source", "unknown"),
                        "cached_at": entry.get("cached_at"),
                    }
                )

            return {
                "success": True,
                "count": len(devices),
                "devices": devices,
            }

        if action == "set":
            if not device_name or not vpn_ip:
                return {
                    "success": False,
                    "error": "device_name and vpn_ip are required for 'set' action",
                }

            cache_vpn_ip(device_name, vpn_ip, source="manual")
            return {
                "success": True,
                "device_name": device_name,
                "vpn_ip": vpn_ip,
                "message": f"Cached VPN IP for {device_name}: {vpn_ip}",
            }

        if action == "remove":
            if not device_name:
                return {
                    "success": False,
                    "error": "device_name is required for 'remove' action",
                }

            removed = remove_vpn_ip(device_name)
            if removed:
                return {
                    "success": True,
                    "device_name": device_name,
                    "message": f"Removed VPN IP cache entry for {device_name}",
                }
            return {
                "success": False,
                "device_name": device_name,
                "error": "Device not found in cache",
            }

        if action == "refresh":
            # Use fioctl to get VPN IPs from device configurations
            # This is more reliable than reading /etc/hosts from WireGuard server

            # Check if fioctl is installed and configured
            fioctl_installed, fioctl_error = _check_fioctl_installed()
            if not fioctl_installed:
                return {
                    "success": False,
                    "error": fioctl_error,
                    "suggestions": [
                        "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                        "Or use refresh_from_server=true to refresh from WireGuard server /etc/hosts",
                    ],
                }

            fioctl_configured, config_error = _check_fioctl_configured()
            if not fioctl_configured:
                return {
                    "success": False,
                    "error": config_error,
                    "suggestions": [
                        "Run 'fioctl login' to configure FoundriesFactory credentials",
                        "Or use refresh_from_server=true to refresh from WireGuard server /etc/hosts",
                    ],
                }

            # Get fioctl path
            fioctl_path = _get_fioctl_path()
            if not fioctl_path:
                return {
                    "success": False,
                    "error": "fioctl not found",
                    "suggestions": [
                        "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                    ],
                }

            # First, list all devices
            list_cmd = [fioctl_path, "devices", "list"]
            list_result = subprocess.run(
                list_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if list_result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to list devices: {list_result.stderr}",
                    "suggestions": [
                        "Check fioctl is configured correctly: 'fioctl factories list'",
                    ],
                }

            # Parse device names from fioctl output
            devices = []
            for line in list_result.stdout.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("NAME") or line.startswith("----"):
                    continue
                # Extract device name (first column)
                parts = [p.strip() for p in line.split() if p.strip()]
                if parts:
                    device_name = parts[0]
                    # Only process Foundries device names
                    if "imx8mm" in device_name or "jaguar" in device_name:
                        devices.append(device_name)

            # Get VPN IP for each device from fioctl config
            cached_count = 0
            errors = []

            for device_name in devices:
                try:
                    # Get device wireguard config
                    config_cmd = [fioctl_path, "devices", "config", device_name, "wireguard"]
                    config_result = subprocess.run(
                        config_cmd,
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if config_result.returncode == 0:
                        # Parse output for address= line
                        # Format: "address=10.42.42.4" or similar
                        for line in config_result.stdout.split("\n"):
                            line = line.strip()
                            if line.startswith("address="):
                                ip_addr = line.split("=", 1)[1].strip()
                                if ip_addr and ip_addr != "(none)":
                                    cache_vpn_ip(device_name, ip_addr, source="fioctl")
                                    cached_count += 1
                                    logger.debug(f"Cached VPN IP for {device_name}: {ip_addr}")
                                    break
                    else:
                        # Device might not have VPN enabled, skip silently
                        logger.debug(
                            f"Device {device_name} has no WireGuard config (may not be enabled)"
                        )
                except Exception as e:
                    errors.append(f"Failed to get VPN IP for {device_name}: {e!s}")

            return {
                "success": True,
                "cached_count": cached_count,
                "source": "fioctl",
                "devices_checked": len(devices),
                "message": f"Refreshed VPN IP cache from fioctl: {cached_count} devices cached",
                "errors": errors if errors else None,
            }

        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "valid_actions": ["get", "list", "set", "remove", "refresh"],
        }

    except Exception as e:
        logger.error(f"Failed to manage VPN IP cache: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Operation failed: {e!s}",
            "suggestions": [
                "Check action parameter is valid",
                "Verify required parameters are provided",
            ],
        }


def check_foundries_vpn_client_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Check if Foundries VPN client configuration file exists and is valid.

    Validates the WireGuard config file format and checks for required fields.

    Args:
        config_path: Optional path to config file. If not provided, searches standard locations.

    Returns:
        Dictionary with validation results
    """
    try:
        # Find config file
        if config_path:
            vpn_config = Path(config_path)
        else:
            vpn_config = get_foundries_vpn_config()

        if not vpn_config or not vpn_config.exists():
            return {
                "success": False,
                "error": "Foundries VPN client configuration file not found",
                "config_path": str(vpn_config) if vpn_config else None,
                "suggestions": [
                    "Obtain WireGuard config from FoundriesFactory web interface",
                    "Generate config template: generate_foundries_vpn_client_config_template()",
                    "Place config file in one of these locations:",
                    "  - ~/.config/wireguard/foundries.conf",
                    "  - {LAB_TESTING_ROOT}/secrets/foundries-vpn.conf",
                    "Or set FOUNDRIES_VPN_CONFIG_PATH environment variable",
                ],
            }

        # Read and validate config file
        try:
            config_content = vpn_config.read_text()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read config file: {e!s}",
                "config_path": str(vpn_config),
                "suggestions": [
                    "Check file permissions",
                    "Ensure file is readable",
                ],
            }

        # Validate WireGuard config format
        required_sections = ["[Interface]", "[Peer]"]
        required_interface_keys = ["PrivateKey"]
        required_peer_keys = ["PublicKey", "Endpoint"]

        has_interface = False
        has_peer = False
        interface_keys = set()
        peer_keys = set()

        current_section = None
        for line in config_content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                current_section = line
                if current_section == "[Interface]":
                    has_interface = True
                elif current_section == "[Peer]":
                    has_peer = True
            elif "=" in line and current_section:
                key = line.split("=")[0].strip()
                if current_section == "[Interface]":
                    interface_keys.add(key)
                elif current_section == "[Peer]":
                    peer_keys.add(key)

        # Check for required sections and keys
        errors = []
        if not has_interface:
            errors.append("Missing [Interface] section")
        if not has_peer:
            errors.append("Missing [Peer] section")
        if "PrivateKey" not in interface_keys:
            errors.append("Missing PrivateKey in [Interface] section")
        if "PublicKey" not in peer_keys:
            errors.append("Missing PublicKey in [Peer] section")
        if "Endpoint" not in peer_keys:
            errors.append("Missing Endpoint in [Peer] section")

        if errors:
            return {
                "success": False,
                "error": "Invalid WireGuard config format",
                "config_path": str(vpn_config),
                "errors": errors,
                "suggestions": [
                    "Check config file format matches WireGuard specification",
                    "Generate new config template: generate_foundries_vpn_client_config_template()",
                    "See WireGuard documentation: https://www.wireguard.com/",
                ],
            }

        # Check if PrivateKey looks valid (base64, 32 bytes = 44 chars)
        private_key_line = None
        for line in config_content.split("\n"):
            if line.strip().startswith("PrivateKey"):
                private_key_line = line.split("=")[1].strip()
                break

        if private_key_line and len(private_key_line) < 40:
            return {
                "success": False,
                "error": "PrivateKey appears invalid (too short)",
                "config_path": str(vpn_config),
                "suggestions": [
                    "Generate new private key: wg genkey",
                    "Regenerate config file",
                ],
            }

        return {
            "success": True,
            "config_path": str(vpn_config),
            "valid": True,
            "has_interface": True,
            "has_peer": True,
            "message": "Foundries VPN client configuration is valid",
            "next_steps": [
                "Connect to VPN: connect_foundries_vpn()",
                "Or use automated setup: setup_foundries_vpn()",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to check Foundries VPN client config: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to check config: {e!s}",
            "suggestions": [
                "Check config file path",
                "Verify file permissions",
            ],
        }


def generate_foundries_vpn_client_config_template(
    output_path: Optional[str] = None, factory: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a Foundries VPN client configuration template with server details.

    Gets server configuration from FoundriesFactory and creates a template config file
    that the user can fill in with their private key and assigned IP address.

    Args:
        output_path: Optional path to save config file. If not provided, uses standard location.
        factory: Optional factory name. If not provided, uses default factory.

    Returns:
        Dictionary with generation results
    """
    try:
        # Check prerequisites
        fioctl_installed, fioctl_error = _check_fioctl_installed()
        if not fioctl_installed:
            return {
                "success": False,
                "error": fioctl_error,
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                ],
            }

        fioctl_configured, config_error = _check_fioctl_configured()
        if not fioctl_configured:
            return {
                "success": False,
                "error": config_error,
                "suggestions": [
                    "Run 'fioctl login' to configure FoundriesFactory credentials",
                ],
            }

        # Get server configuration
        server_config = get_foundries_vpn_server_config(factory)
        if not server_config.get("success"):
            return {
                "success": False,
                "error": "Failed to get VPN server configuration",
                "details": server_config,
                "suggestions": [
                    "Check fioctl is configured correctly",
                    "Verify VPN server is enabled in FoundriesFactory",
                ],
            }

        if not server_config.get("enabled"):
            return {
                "success": False,
                "error": "VPN server is not enabled in FoundriesFactory",
                "suggestions": [
                    "Enable VPN server in FoundriesFactory",
                    "Contact Factory administrator",
                ],
            }

        # Determine output path
        if output_path:
            config_file = Path(output_path)
        else:
            # Use standard location
            config_file = Path.home() / ".config" / "wireguard" / "foundries.conf"
            config_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if file already exists
        if config_file.exists():
            return {
                "success": False,
                "error": f"Config file already exists: {config_file}",
                "config_path": str(config_file),
                "suggestions": [
                    "Delete existing file or use different output_path",
                    "Check existing config: check_foundries_vpn_client_config()",
                ],
            }

        # Generate template
        server_address_base = server_config.get("address", "10.42.42.1").rsplit(".", 1)[0]
        template = f"""# Foundries VPN WireGuard Client Configuration
# Generated automatically - Fill in YOUR_PRIVATE_KEY_HERE and YOUR_VPN_IP_HERE

[Interface]
# Your private key (generate with: wg genkey | tee privatekey | wg pubkey > publickey)
# Share your public key with VPN administrator to get assigned IP address
PrivateKey = YOUR_PRIVATE_KEY_HERE

# Your assigned VPN IP address (get from VPN administrator)
# VPN network: {server_address_base}.X/24
Address = YOUR_VPN_IP_HERE

# Optional: DNS servers to use when connected
# DNS = 8.8.8.8, 8.8.4.4

[Peer]
# Server's public key (from FoundriesFactory)
PublicKey = {server_config.get('public_key', '')}

# Server endpoint
Endpoint = {server_config.get('endpoint', '')}

# Allowed IPs - routes to send through VPN
# Use specific subnets for lab network access only
AllowedIPs = {server_address_base}.0/24, 192.168.2.0/24

# Keep connection alive
PersistentKeepalive = 25
"""

        # Write template
        try:
            config_file.write_text(template)
            config_file.chmod(0o600)  # Secure permissions
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to write config file: {e!s}",
                "config_path": str(config_file),
            }

        return {
            "success": True,
            "config_path": str(config_file),
            "server_endpoint": server_config.get("endpoint"),
            "server_address": server_config.get("address"),
            "server_public_key": server_config.get("public_key"),
            "message": f"Config template generated at {config_file}",
            "next_steps": [
                "1. Generate your private key: wg genkey | tee privatekey | wg pubkey > publickey",
                "2. Share your public key with VPN administrator to get assigned IP address",
                "3. Edit config file and replace YOUR_PRIVATE_KEY_HERE and YOUR_VPN_IP_HERE",
                "4. Check config: check_foundries_vpn_client_config()",
                "5. Connect: connect_foundries_vpn() or setup_foundries_vpn()",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to generate VPN client config template: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to generate template: {e!s}",
            "suggestions": [
                "Check fioctl is installed and configured",
                "Verify VPN server is enabled",
            ],
        }


def setup_foundries_vpn(
    config_path: Optional[str] = None,
    factory: Optional[str] = None,
    auto_generate_config: bool = False,
) -> Dict[str, Any]:
    """
    Automated end-to-end Foundries VPN setup.

    Checks prerequisites, validates or generates client config, and connects to VPN.
    This is a convenience function that automates the entire setup process.

    Args:
        config_path: Optional path to client config file. If not provided, searches standard locations.
        factory: Optional factory name. If not provided, uses default factory.
        auto_generate_config: If True and config not found, generates template config (requires manual editing).

    Returns:
        Dictionary with setup results
    """
    try:
        steps_completed = []
        steps_failed = []

        # Step 1: Check fioctl installation
        fioctl_installed, fioctl_error = _check_fioctl_installed()
        if not fioctl_installed:
            return {
                "success": False,
                "error": fioctl_error,
                "steps_completed": steps_completed,
                "steps_failed": ["Check fioctl installation"],
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                ],
            }
        steps_completed.append("fioctl installed")

        # Step 2: Check fioctl configuration
        fioctl_configured, config_error = _check_fioctl_configured()
        if not fioctl_configured:
            return {
                "success": False,
                "error": config_error,
                "steps_completed": steps_completed,
                "steps_failed": ["Check fioctl configuration"],
                "suggestions": [
                    "Run 'fioctl login' to configure FoundriesFactory credentials",
                ],
            }
        steps_completed.append("fioctl configured")

        # Step 3: Check WireGuard tools
        wg_check = subprocess.run(
            ["which", "wg"], check=False, capture_output=True, text=True, timeout=5
        )
        if wg_check.returncode != 0:
            return {
                "success": False,
                "error": "WireGuard tools not installed",
                "steps_completed": steps_completed,
                "steps_failed": ["Check WireGuard tools"],
                "suggestions": [
                    "Install WireGuard tools: sudo apt install wireguard-tools",
                    "Or: sudo yum install wireguard-tools",
                ],
            }
        steps_completed.append("WireGuard tools installed")

        # Step 4: Get server configuration
        server_config = get_foundries_vpn_server_config(factory)
        if not server_config.get("success"):
            return {
                "success": False,
                "error": "Failed to get VPN server configuration",
                "steps_completed": steps_completed,
                "steps_failed": ["Get server configuration"],
                "details": server_config,
            }
        steps_completed.append("Server configuration retrieved")

        if not server_config.get("enabled"):
            return {
                "success": False,
                "error": "VPN server is not enabled in FoundriesFactory",
                "steps_completed": steps_completed,
                "steps_failed": ["VPN server enabled"],
                "suggestions": [
                    "Enable VPN server in FoundriesFactory",
                    "Contact Factory administrator",
                ],
            }
        steps_completed.append("VPN server enabled")

        # Step 5: Check or generate client config
        client_config_check = check_foundries_vpn_client_config(config_path)
        if not client_config_check.get("success"):
            if auto_generate_config:
                # Generate template config
                template_result = generate_foundries_vpn_client_config_template(
                    config_path, factory
                )
                if template_result.get("success"):
                    steps_completed.append("Config template generated")
                    return {
                        "success": False,
                        "error": "Client config template generated but requires manual editing",
                        "steps_completed": steps_completed,
                        "config_path": template_result.get("config_path"),
                        "next_steps": template_result.get("next_steps", []),
                        "message": "Template generated. Edit config file with your private key and assigned IP, then run setup_foundries_vpn() again.",
                    }
                steps_failed.append("Generate config template")
                return {
                    "success": False,
                    "error": "Failed to generate config template",
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "details": template_result,
                }
            steps_failed.append("Client config found")
            return {
                "success": False,
                "error": "Client configuration not found",
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "details": client_config_check,
                "suggestions": [
                    "Obtain config from FoundriesFactory web interface",
                    "Or run: generate_foundries_vpn_client_config_template()",
                    "Or use auto_generate_config=True to generate template",
                ],
            }
        steps_completed.append("Client config found and valid")

        # Step 6: Connect to VPN
        connect_result = connect_foundries_vpn(config_path)
        if connect_result.get("success"):
            steps_completed.append("VPN connected")
            return {
                "success": True,
                "steps_completed": steps_completed,
                "connection_method": connect_result.get("method"),
                "message": "Foundries VPN setup completed successfully",
                "next_steps": [
                    "List devices: list_foundries_devices()",
                    "Test device connectivity: test_device(device_id)",
                ],
            }
        steps_failed.append("Connect to VPN")
        return {
            "success": False,
            "error": "Failed to connect to VPN",
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "details": connect_result,
        }

    except Exception as e:
        logger.error(f"Failed to setup Foundries VPN: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Setup failed: {e!s}",
            "steps_completed": steps_completed if "steps_completed" in locals() else [],
            "steps_failed": steps_failed if "steps_failed" in locals() else [],
            "suggestions": [
                "Check prerequisites manually",
                "Review error details",
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


def enable_foundries_device_to_device(
    device_name: str,
    device_ip: Optional[str] = None,
    vpn_subnet: str = "10.42.42.0/24",
    server_host: Optional[str] = None,
    server_port: int = 5025,
    server_user: str = "root",
    server_password: Optional[str] = None,
    device_user: str = "fio",
    device_password: str = "fio",
) -> Dict[str, Any]:
    """
    Enable device-to-device communication for a Foundries device.

    This tool SSHes into the WireGuard server, then from there to the target device,
    and updates the device's NetworkManager WireGuard configuration to allow the full
    VPN subnet instead of just the server IP. This enables device-to-device communication
    for debugging/development purposes.

    By default, Foundries devices use restrictive AllowedIPs (server IP only) for security.
    This tool temporarily overrides that for development/debugging.

    Args:
        device_name: Name of the Foundries device (e.g., "imx8mm-jaguar-sentai-2d0e0a09dab86563")
        device_ip: VPN IP address of the device (e.g., "10.42.42.2"). If not provided,
                   will try to get from device list.
        vpn_subnet: VPN subnet to allow (default: "10.42.42.0/24")
        server_host: WireGuard server hostname/IP (default: from config or "144.76.167.54")
        server_port: SSH port on WireGuard server (default: 5025)
        server_user: SSH user for WireGuard server (default: "root")
        server_password: SSH password for WireGuard server (if not using SSH keys)
        device_user: SSH user on device (default: "fio")
        device_password: SSH password on device (default: "fio")

    Returns:
        Dictionary with operation results
    """
    try:
        steps_completed = []
        steps_failed = []

        # Get device IP if not provided
        if not device_ip:
            from lab_testing.tools.foundries_devices import list_foundries_devices
            devices = list_foundries_devices()
            if not devices.get("success"):
                return {
                    "success": False,
                    "error": "Failed to list devices to find device IP",
                    "details": devices,
                }

            device_found = False
            for device in devices.get("devices", []):
                if device.get("name") == device_name:
                    device_ip = device.get("vpn_ip")
                    device_found = True
                    break

            if not device_found:
                return {
                    "success": False,
                    "error": f"Device '{device_name}' not found in device list",
                    "suggestions": [
                        "Check device name spelling",
                        "Ensure device has VPN enabled",
                        "List devices: list_foundries_devices()",
                    ],
                }

        if not device_ip:
            return {
                "success": False,
                "error": "Device IP not found and not provided",
            }

        # Get server host from config if not provided
        if not server_host:
            config_path = get_foundries_vpn_config()
            if config_path and config_path.exists():
                # Try to read config file to get server endpoint
                try:
                    config_content = config_path.read_text()
                    for line in config_content.split("\n"):
                        if line.startswith("Endpoint =") or line.startswith("Endpoint="):
                            endpoint = line.split("=", 1)[1].strip()
                            # Extract host from endpoint (e.g., "144.76.167.54:5555" -> "144.76.167.54")
                            server_host = endpoint.split(":")[0] if ":" in endpoint else endpoint
                            break
                except Exception:
                    pass

            if not server_host:
                server_host = "144.76.167.54"  # Default

        steps_completed.append(f"Resolved device IP: {device_ip}, server: {server_host}")

        # Build SSH command to update device config
        # Step 1: Update NetworkManager config on device
        update_cmd = f"""sshpass -p '{device_password}' ssh -o StrictHostKeyChecking=no {device_user}@{device_ip} 'echo "{device_password}" | sudo -S sed -i "s/allowed-ips=10.42.42.1/allowed-ips={vpn_subnet}/" /etc/NetworkManager/system-connections/factory-vpn0.nmconnection && echo "Config updated"'"""

        # Step 2: Reload NetworkManager connection
        reload_cmd = f"""sshpass -p '{device_password}' ssh -o StrictHostKeyChecking=no {device_user}@{device_ip} 'echo "{device_password}" | sudo -S nmcli connection reload factory-vpn0 && echo "{device_password}" | sudo -S nmcli connection down factory-vpn0 && sleep 1 && echo "{device_password}" | sudo -S nmcli connection up factory-vpn0 && sleep 2 && echo "{device_password}" | sudo -S wg show factory-vpn0 | grep "allowed ips"'"""

        # Step 3: Set server-side AllowedIPs
        # First, get device public key from server
        get_key_cmd = f"""wg show factory | grep -A 5 "{device_ip}" | grep "peer:" | awk '{{print $2}}' || wg show factory | grep -B 5 "{device_ip}" | grep "peer:" | awk '{{print $2}}'"""

        # Build full command to run on server
        if server_password:
            ssh_to_server = f"sshpass -p '{server_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {server_port} {server_user}@{server_host}"
        else:
            ssh_to_server = (
                f"ssh -o StrictHostKeyChecking=no -p {server_port} {server_user}@{server_host}"
            )

        # Execute update
        full_cmd = f"""{ssh_to_server} "{update_cmd} && {reload_cmd}" """

        logger.info(f"Enabling device-to-device for {device_name} ({device_ip})")
        result = subprocess.run(
            full_cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            steps_failed.append("Failed to update device config")
            return {
                "success": False,
                "error": f"Failed to update device configuration: {result.stderr}",
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "suggestions": [
                    "Check SSH access from server to device",
                    "Verify device IP is correct",
                    "Check device is online",
                ],
            }

        steps_completed.append("Updated device NetworkManager config")
        steps_completed.append("Reloaded NetworkManager connection")

        # Set server-side AllowedIPs
        # Get device public key
        key_result = subprocess.run(
            f"""{ssh_to_server} "{get_key_cmd}" """,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if key_result.returncode == 0 and key_result.stdout.strip():
            pubkey = key_result.stdout.strip()
            set_server_cmd = f"""wg set factory peer {pubkey} allowed-ips {vpn_subnet}"""

            server_result = subprocess.run(
                f"""{ssh_to_server} "{set_server_cmd}" """,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if server_result.returncode == 0:
                steps_completed.append(f"Set server-side AllowedIPs to {vpn_subnet}")
            else:
                steps_failed.append("Failed to set server-side AllowedIPs")
                logger.warning(f"Failed to set server-side AllowedIPs: {server_result.stderr}")

        return {
            "success": True,
            "device_name": device_name,
            "device_ip": device_ip,
            "vpn_subnet": vpn_subnet,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "message": f"Device-to-device communication enabled for {device_name}",
            "note": "Device config updated. Server-side AllowedIPs may need to be set manually if daemon overwrites it.",
        }

    except Exception as e:
        logger.error(f"Failed to enable device-to-device: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Operation failed: {e!s}",
            "steps_completed": steps_completed if "steps_completed" in locals() else [],
            "steps_failed": steps_failed if "steps_failed" in locals() else [],
            "suggestions": [
                "Check device is online and accessible",
                "Verify SSH credentials",
                "Check WireGuard server is accessible",
            ],
        }


def check_client_peer_registered(
    client_public_key: Optional[str] = None,
    server_host: Optional[str] = None,
    server_port: int = 5025,
    server_user: str = "root",
    server_password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check if a client peer is registered on the Foundries WireGuard server.

    This tool checks if the client's public key is configured as a peer on the server.
    It can connect via Foundries VPN (if connected) or standard VPN (hardware lab).

    Args:
        client_public_key: Client's WireGuard public key. If not provided, will try to
                          derive from local config file.
        server_host: WireGuard server hostname/IP. If not provided, will try to get
                    from Foundries VPN config or use standard VPN IP.
        server_port: SSH port on WireGuard server (default: 5025)
        server_user: SSH user for WireGuard server (default: "root")
        server_password: SSH password for WireGuard server (if not using SSH keys)

    Returns:
        Dictionary with client peer registration status
    """
    try:
        # Get client public key if not provided
        if not client_public_key:
            config_path = get_foundries_vpn_config()
            if config_path and config_path.exists():
                try:
                    config_content = config_path.read_text()
                    for line in config_content.split("\n"):
                        if "PrivateKey" in line and "=" in line:
                            privkey = line.split("=", 1)[1].strip()
                            # Derive public key
                            result = subprocess.run(
                                ["wg", "pubkey"],
                                check=False,
                                input=privkey.encode(),
                                capture_output=True,
                                text=True,
                                timeout=5,
                            )
                            if result.returncode == 0:
                                client_public_key = result.stdout.strip()
                                break
                except Exception as e:
                    logger.warning(f"Failed to derive public key from config: {e}")

        if not client_public_key:
            return {
                "success": False,
                "error": "Client public key not provided and could not be derived from config",
                "suggestions": [
                    "Provide client_public_key parameter",
                    "Ensure Foundries VPN config file exists with PrivateKey",
                    "Generate keys: wg genkey | tee privatekey | wg pubkey > publickey",
                ],
            }

        # Determine server host
        foundries_vpn_connected = False
        if not server_host:
            # Check if Foundries VPN is connected
            status = foundries_vpn_status()
            if status.get("connected"):
                foundries_vpn_connected = True
                server_host = "10.42.42.1"  # Foundries VPN server IP
            else:
                # Not connected - cannot check without VPN
                return {
                    "success": False,
                    "error": "Foundries VPN not connected. Cannot check client peer registration without VPN connection.",
                    "suggestions": [
                        "Connect to Foundries VPN first: connect_foundries_vpn()",
                        "If not registered, contact VPN admin: ajlennon@dynamicdevices.co.uk",
                    ],
                }

        # Build SSH command
        if server_password:
            ssh_cmd = f"sshpass -p '{server_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {server_port} {server_user}@{server_host}"
        else:
            ssh_cmd = (
                f"ssh -o StrictHostKeyChecking=no -p {server_port} {server_user}@{server_host}"
            )

        # Check if peer exists in runtime
        check_runtime_cmd = f"{ssh_cmd} 'wg show factory | grep -A 3 \"{client_public_key}\"'"
        result = subprocess.run(
            check_runtime_cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        runtime_registered = result.returncode == 0 and client_public_key in result.stdout

        # Check if peer exists in config file
        check_config_cmd = f'{ssh_cmd} \'grep -A 3 "{client_public_key}" /etc/wireguard/factory.conf || grep "{client_public_key}" /etc/wireguard/factory-clients.conf\''
        result_config = subprocess.run(
            check_config_cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        config_registered = result.returncode == 0 and client_public_key in result_config.stdout

        # Parse assigned IP if registered
        assigned_ip = None
        allowed_ips = None
        if runtime_registered:
            # Extract IP from wg show output
            for line in result.stdout.split("\n"):
                if "allowed ips:" in line.lower():
                    allowed_ips = line.split(":")[1].strip() if ":" in line else None
                    # Extract IP from allowed_ips (e.g., "10.42.42.10/32" -> "10.42.42.10")
                    if allowed_ips and "/" in allowed_ips:
                        assigned_ip = allowed_ips.split("/")[0]
                    break

        return {
            "success": True,
            "client_public_key": client_public_key,
            "registered": runtime_registered or config_registered,
            "runtime_registered": runtime_registered,
            "config_registered": config_registered,
            "assigned_ip": assigned_ip,
            "allowed_ips": allowed_ips,
            "server_host": server_host,
            "connection_method": "Foundries VPN" if foundries_vpn_connected else "Not connected",
            "next_steps": (
                [
                    "Client peer is registered. You can connect to Foundries VPN.",
                    "If not connected, use: connect_foundries_vpn()",
                ]
                if (runtime_registered or config_registered)
                else [
                    "Client peer is NOT registered on server",
                    "Register using: register_foundries_vpn_client()",
                    "Or contact VPN admin: ajlennon@dynamicdevices.co.uk",
                ]
            ),
        }
    except Exception as e:
        logger.error(f"Failed to check client peer registration: {e}")
        return {
            "success": False,
            "error": f"Failed to check client peer registration: {e!s}",
            "suggestions": [
                "Check VPN connection (Foundries or standard)",
                "Verify server host and port are correct",
                "Check SSH access to server",
            ],
        }


def register_foundries_vpn_client(
    client_public_key: str,
    assigned_ip: str,
    server_host: Optional[str] = None,
    server_port: int = 5025,
    server_user: str = "root",
    server_password: Optional[str] = None,
    use_config_file: bool = True,
) -> Dict[str, Any]:
    """
    Register a client peer on the Foundries WireGuard server.

    This tool automates client peer registration. It connects to the server via
    Foundries VPN (10.42.42.1). Requires Foundries VPN to be connected first.

    **Bootstrap Scenario:** For clean installation, the first admin needs initial
    server access (public IP or direct access) to register themselves. After the
    first admin connects, all subsequent client registrations can be done via
    Foundries VPN by the admin.

    Args:
        client_public_key: Client's WireGuard public key to register
        assigned_ip: IP address to assign to client (e.g., "10.42.42.10")
        server_host: WireGuard server hostname/IP. If not provided, will try to get
                    from Foundries VPN config or use standard VPN IP.
        server_port: SSH port on WireGuard server (default: 5025)
        server_user: SSH user for WireGuard server (default: "root")
        server_password: SSH password for WireGuard server (if not using SSH keys)
        use_config_file: If True, use config file method (/etc/wireguard/factory-clients.conf).
                        If False, use legacy method (wg set + wg-quick save).

    Returns:
        Dictionary with registration results
    """
    try:
        steps_completed = []
        steps_failed = []

        # Determine server host
        foundries_vpn_connected = False
        if not server_host:
            # Check if Foundries VPN is connected
            status = foundries_vpn_status()
            if status.get("connected"):
                foundries_vpn_connected = True
                server_host = "10.42.42.1"  # Foundries VPN server IP
                steps_completed.append("Using Foundries VPN for server access: 10.42.42.1")
            else:
                # Not connected - need Foundries VPN for server access
                return {
                    "success": False,
                    "error": "Foundries VPN not connected. Cannot access server without VPN connection.",
                    "suggestions": [
                        "Connect to Foundries VPN first: connect_foundries_vpn()",
                        "If this is first-time setup, contact VPN admin: ajlennon@dynamicdevices.co.uk",
                        "Admin can register your client peer, then you can connect",
                    ],
                    "bootstrap_note": (
                        "For clean installation: First admin needs initial server access (public IP or direct access). "
                        "After first admin connects, all subsequent client registrations can be done via Foundries VPN."
                    ),
                }

        # Build SSH command
        if server_password:
            ssh_cmd = f"sshpass -p '{server_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {server_port} {server_user}@{server_host}"
        else:
            ssh_cmd = (
                f"ssh -o StrictHostKeyChecking=no -p {server_port} {server_user}@{server_host}"
            )

        # Check if peer already exists
        check_cmd = f"{ssh_cmd} 'wg show factory | grep \"{client_public_key}\"'"
        result = subprocess.run(
            check_cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and client_public_key in result.stdout:
            return {
                "success": True,
                "message": "Client peer already registered",
                "client_public_key": client_public_key,
                "assigned_ip": assigned_ip,
                "steps_completed": ["Client peer already exists on server"],
            }

        if use_config_file:
            # Method 1: Use config file (Priority 2 - preferred)
            # Add to factory-clients.conf
            comment = f"# Client peer - {assigned_ip}"
            peer_line = f"{client_public_key} {assigned_ip} client"

            # Check if config file exists, create if not
            check_file_cmd = f"{ssh_cmd} 'test -f /etc/wireguard/factory-clients.conf && echo exists || echo notfound'"
            result = subprocess.run(
                check_file_cmd,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if "notfound" in result.stdout:
                # Create config file
                create_cmd = f"{ssh_cmd} 'echo \"# Foundries VPN Client Peers\" > /etc/wireguard/factory-clients.conf && chmod 600 /etc/wireguard/factory-clients.conf'"
                result = subprocess.run(
                    create_cmd,
                    shell=True,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    steps_completed.append("Created /etc/wireguard/factory-clients.conf")

            # Check if peer already in config file
            check_peer_cmd = (
                f"{ssh_cmd} 'grep \"{client_public_key}\" /etc/wireguard/factory-clients.conf'"
            )
            result = subprocess.run(
                check_peer_cmd,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and client_public_key in result.stdout:
                steps_completed.append("Client peer already in config file")
            else:
                # Add peer to config file
                add_peer_cmd = (
                    f"{ssh_cmd} 'echo \"{peer_line}\" >> /etc/wireguard/factory-clients.conf'"
                )
                result = subprocess.run(
                    add_peer_cmd,
                    shell=True,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    steps_completed.append(f"Added client peer to config file: {assigned_ip}")
                else:
                    steps_failed.append(f"Failed to add to config file: {result.stderr}")

            # Apply client peer (daemon will pick it up, or apply manually)
            apply_cmd = f"{ssh_cmd} 'wg set factory peer {client_public_key} allowed-ips {assigned_ip}/32 && wg-quick save factory'"
            result = subprocess.run(
                apply_cmd,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                steps_completed.append("Applied client peer to WireGuard interface")
            else:
                steps_failed.append(f"Failed to apply peer: {result.stderr}")

        else:
            # Method 2: Legacy method (direct wg set)
            allowed_ips = f"{assigned_ip}/32"
            register_cmd = f"{ssh_cmd} 'wg set factory peer {client_public_key} allowed-ips {allowed_ips} && wg-quick save factory'"
            result = subprocess.run(
                register_cmd,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                steps_completed.append(f"Registered client peer: {assigned_ip}")
            else:
                steps_failed.append(f"Failed to register peer: {result.stderr}")

        # Verify registration
        verify_result = check_client_peer_registered(
            client_public_key=client_public_key,
            server_host=server_host,
            server_port=server_port,
            server_user=server_user,
            server_password=server_password,
        )

        if verify_result.get("registered"):
            steps_completed.append("Verified client peer registration")
        else:
            steps_failed.append("Client peer registration verification failed")

        if steps_failed:
            return {
                "success": False,
                "error": "Some steps failed during client peer registration",
                "client_public_key": client_public_key,
                "assigned_ip": assigned_ip,
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "suggestions": [
                    "Check SSH access to server",
                    "Verify server host and port are correct",
                    "Check VPN connection (Foundries or standard)",
                    "Try manual registration: ssh to server and run wg set commands",
                ],
            }

        return {
            "success": True,
            "message": "Client peer registered successfully",
            "client_public_key": client_public_key,
            "assigned_ip": assigned_ip,
            "server_host": server_host,
            "connection_method": "Foundries VPN" if foundries_vpn_connected else "Not connected",
            "steps_completed": steps_completed,
            "next_steps": [
                "Client peer is now registered on server",
                "If using standard VPN, disconnect: disconnect_vpn()",
                "Connect to Foundries VPN: connect_foundries_vpn()",
                "Verify connection: ping 10.42.42.1",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to register client peer: {e}")
        return {
            "success": False,
            "error": f"Failed to register client peer: {e!s}",
            "suggestions": [
                "Check VPN connection (Foundries or standard)",
                "Verify server host and port are correct",
                "Check SSH access to server",
                "Contact VPN admin: ajlennon@dynamicdevices.co.uk",
            ],
        }
