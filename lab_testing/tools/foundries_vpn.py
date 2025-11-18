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
            # Import successful, now try to connect
            connection_name = vpn_config.stem
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
        return {
            "success": False,
            "error": f"Failed to connect to Foundries VPN: {error_output}",
            "suggestions": [
                "Check VPN configuration file is valid",
                "Ensure WireGuard tools are installed",
                "Check if VPN server is accessible",
            ],
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


def list_foundries_devices(factory: Optional[str] = None) -> Dict[str, Any]:
    """
    List devices accessible via Foundries VPN.

    Uses fioctl to list devices in the FoundriesFactory that have WireGuard enabled.

    Args:
        factory: Optional factory name. If not provided, uses default factory from fioctl config.

    Returns:
        Dictionary with list of Foundries devices
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
        cmd = [fioctl_path, "devices", "list"]
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
                "error": f"Failed to list Foundries devices: {error_msg}",
                "suggestions": [
                    "Check fioctl is configured correctly: 'fioctl factories list'",
                    "Ensure you have access to the factory",
                ],
            }

        # Parse fioctl output (table format)
        # fioctl devices list outputs a table with columns: NAME, TARGET, STATUS, APPS, UP-TO-DATE, IS-PROD
        # Columns are space-aligned, so we need to handle multi-word values carefully
        lines = result.stdout.strip().split("\n")
        devices = []

        # Skip header and separator lines
        for line in lines:
            line = line.rstrip()  # Keep leading spaces for column detection
            # Skip empty lines, header row, and separator row (lines starting with ----)
            if (
                not line.strip()
                or line.strip().startswith("NAME")
                or line.strip().startswith("----")
            ):
                continue

            # Split by multiple spaces to handle column alignment
            # Format: NAME (50 chars) TARGET (30 chars) STATUS (10 chars) APPS (variable) UP-TO-DATE IS-PROD
            parts = [p for p in line.split("  ") if p.strip()]  # Split by double spaces

            if len(parts) >= 3:
                device_name = parts[0].strip()

                # Handle multi-word TARGET (e.g., "Initial Target")
                # If STATUS is "Target", then TARGET is actually two words
                target_parts = parts[1].strip().split()
                if len(target_parts) >= 2 and len(parts) > 2 and parts[2].strip() == "Target":
                    # "Initial Target" case - combine first two parts
                    target = " ".join(target_parts[:2])
                    status = parts[2].strip() if len(parts) > 2 else "unknown"
                    apps_start_idx = 3
                else:
                    target = target_parts[0] if target_parts else "Unknown"
                    status = parts[2].strip() if len(parts) > 2 else "unknown"
                    apps_start_idx = 3

                # Extract apps, up_to_date, and is_prod
                # Last two parts should be UP-TO-DATE and IS-PROD
                apps = ""
                up_to_date = "unknown"
                is_prod = "unknown"

                if len(parts) >= 5:
                    # Has UP-TO-DATE and IS-PROD
                    up_to_date = parts[-2].strip() if len(parts) >= 5 else "unknown"
                    is_prod = parts[-1].strip() if len(parts) >= 5 else "unknown"
                    # Everything between STATUS and UP-TO-DATE is APPS
                    apps = " ".join([p.strip() for p in parts[apps_start_idx:-2] if p.strip()])
                elif len(parts) > apps_start_idx:
                    apps = " ".join([p.strip() for p in parts[apps_start_idx:] if p.strip()])

                devices.append(
                    {
                        "name": device_name,
                        "target": target,
                        "status": status,
                        "apps": apps,
                        "up_to_date": up_to_date,
                        "is_prod": is_prod,
                        "factory": factory or "default",
                    }
                )

        return {
            "success": True,
            "devices": devices,
            "count": len(devices),
            "factory": factory or "default",
            "message": f"Found {len(devices)} Foundries device(s)",
            "next_steps": [
                "Enable VPN on device: enable_foundries_vpn_device(device_name)",
                "Connect to Foundries VPN: connect_foundries_vpn()",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to list Foundries devices: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to list Foundries devices: {e!s}",
            "suggestions": [
                "Check if fioctl is installed: https://github.com/foundriesio/fioctl",
                "Check if fioctl is configured: Run 'fioctl login'",
                "Verify you have access to the factory",
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
            return {
                "success": False,
                "error": "VPN is not connected",
                "details": status,
                "suggestions": [
                    "Connect to VPN: connect_foundries_vpn()",
                    "Or run automated setup: setup_foundries_vpn()",
                ],
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
