"""
Configuration management for Lab Testing MCP Server

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import os
from pathlib import Path
from typing import List, Optional

# Default paths - can be overridden via environment variables
DEFAULT_LAB_TESTING_ROOT = Path("/data_drive/esl/ai-lab-testing")
LAB_TESTING_ROOT = Path(os.getenv("LAB_TESTING_ROOT", DEFAULT_LAB_TESTING_ROOT))

# Configuration file paths
CONFIG_DIR = LAB_TESTING_ROOT / "config"
SECRETS_DIR = LAB_TESTING_ROOT / "secrets"
SCRIPTS_DIR = LAB_TESTING_ROOT / "scripts" / "local"
LOGS_DIR = LAB_TESTING_ROOT / "logs"
CACHE_DIR = Path.home() / ".cache" / "ai-lab-testing"

# Key configuration files
LAB_DEVICES_JSON = CONFIG_DIR / "lab_devices.json"

# VPN configuration - can be overridden via VPN_CONFIG_PATH environment variable
# If not set, searches common locations
VPN_CONFIG_PATH_ENV = os.getenv("VPN_CONFIG_PATH")

# Foundries VPN configuration - can be overridden via FOUNDRIES_VPN_CONFIG_PATH environment variable
# If not set, searches Foundries-specific locations
FOUNDRIES_VPN_CONFIG_PATH_ENV = os.getenv("FOUNDRIES_VPN_CONFIG_PATH")

# Target network configuration - can be overridden via TARGET_NETWORK environment variable
# Default target network for lab testing operations
DEFAULT_TARGET_NETWORK = os.getenv("TARGET_NETWORK", "192.168.2.0/24")


def get_lab_devices_config() -> Path:
    """Get path to lab devices configuration file"""
    return LAB_DEVICES_JSON


def get_vpn_config() -> Optional[Path]:
    """
    Get path to VPN configuration file.

    Search order:
    1. VPN_CONFIG_PATH environment variable (if set)
    2. Common filenames in SECRETS_DIR (wg0.conf, *.conf)
    3. Common system locations (~/.config/wireguard/*.conf, /etc/wireguard/*.conf)
    4. NetworkManager WireGuard connections

    Returns:
        Path to VPN config file, or None if not found
    """
    # 1. Check environment variable first
    if VPN_CONFIG_PATH_ENV:
        config_path = Path(VPN_CONFIG_PATH_ENV)
        if config_path.exists():
            return config_path

    # 2. Check common filenames in secrets directory
    common_names = ["wg0.conf", "wireguard.conf", "vpn.conf"]
    for name in common_names:
        config_path = SECRETS_DIR / name
        if config_path.exists():
            return config_path

    # 3. Search for any .conf files in secrets directory
    if SECRETS_DIR.exists():
        conf_files = list(SECRETS_DIR.glob("*.conf"))
        if conf_files:
            # Prefer files with 'wg' or 'wireguard' in name
            for f in conf_files:
                if "wg" in f.name.lower() or "wireguard" in f.name.lower():
                    return f
            # Otherwise return first .conf file
            return conf_files[0]

    # 4. Check common system locations
    system_locations = [
        Path.home() / ".config" / "wireguard",
        Path("/etc/wireguard"),
    ]

    for location in system_locations:
        if location.exists():
            conf_files = list(location.glob("*.conf"))
            if conf_files:
                # Prefer wg0.conf
                for f in conf_files:
                    if f.name == "wg0.conf":
                        return f
                return conf_files[0]

    return None


def get_foundries_vpn_config() -> Optional[Path]:
    """
    Get path to Foundries VPN (WireGuard) configuration file.

    Foundries VPN uses WireGuard but with a server-based architecture where devices
    connect to a centralized VPN server managed by FoundriesFactory.

    Search order:
    1. FOUNDRIES_VPN_CONFIG_PATH environment variable (if set)
    2. Foundries-specific filenames in SECRETS_DIR (foundries-vpn.conf, foundries.conf)
    3. User config: ~/.config/wireguard/foundries.conf
    4. System config: /etc/wireguard/foundries.conf

    Returns:
        Path to Foundries VPN config file, or None if not found
    """
    # 1. Check environment variable first
    if FOUNDRIES_VPN_CONFIG_PATH_ENV:
        config_path = Path(FOUNDRIES_VPN_CONFIG_PATH_ENV)
        if config_path.exists():
            return config_path

    # 2. Check Foundries-specific filenames in secrets directory
    foundries_names = ["foundries-vpn.conf", "foundries.conf"]
    for name in foundries_names:
        config_path = SECRETS_DIR / name
        if config_path.exists():
            return config_path

    # 3. Check user config location
    user_config = Path.home() / ".config" / "wireguard" / "foundries.conf"
    try:
        if user_config.exists():
            return user_config
    except (PermissionError, OSError):
        pass

    # 4. Check system config location (may require root)
    system_config = Path("/etc/wireguard/foundries.conf")
    try:
        if system_config.exists():
            return system_config
    except (PermissionError, OSError):
        pass

    # 5. Also check for any .conf files with "foundries" in the name
    if SECRETS_DIR.exists():
        for conf_file in SECRETS_DIR.glob("*.conf"):
            if "foundries" in conf_file.name.lower():
                return conf_file

    # Check user wireguard directory for any foundries configs
    user_wg_dir = Path.home() / ".config" / "wireguard"
    try:
        if user_wg_dir.exists():
            for conf_file in user_wg_dir.glob("*.conf"):
                if "foundries" in conf_file.name.lower():
                    return conf_file
    except (PermissionError, OSError):
        pass

    return None


def get_scripts_dir() -> Path:
    """Get path to scripts directory"""
    return SCRIPTS_DIR


def get_logs_dir() -> Path:
    """Get path to logs directory"""
    return LOGS_DIR


def get_target_network() -> str:
    """
    Get the target network for lab testing operations.

    Priority:
    1. TARGET_NETWORK environment variable
    2. Value from lab_devices.json config file (if exists)
    3. Default: 192.168.2.0/24

    Returns:
        Network CIDR string (e.g., "192.168.2.0/24")
    """
    # Check environment variable first
    env_network = os.getenv("TARGET_NETWORK")
    if env_network:
        return env_network

    # Check config file
    try:
        if LAB_DEVICES_JSON.exists():
            import json

            with open(LAB_DEVICES_JSON) as f:
                config = json.load(f)
                infrastructure = config.get("lab_infrastructure", {})
                network_access = infrastructure.get("network_access", {})
                target_network = network_access.get("target_network")
                if target_network:
                    return target_network
    except Exception:
        # If config read fails, fall back to default
        pass

    # Default target network
    return DEFAULT_TARGET_NETWORK


def get_target_network_friendly_name() -> str:
    """
    Get the friendly name for the target network.

    Priority:
    1. Value from lab_devices.json config file (if exists)
    2. Default: "Hardware Lab"

    Returns:
        Friendly name string (e.g., "Hardware Lab")
    """
    # Check config file
    try:
        if LAB_DEVICES_JSON.exists():
            import json

            with open(LAB_DEVICES_JSON) as f:
                config = json.load(f)
                infrastructure = config.get("lab_infrastructure", {})
                network_access = infrastructure.get("network_access", {})
                friendly_name = network_access.get("friendly_name")
                if friendly_name:
                    return friendly_name
    except Exception:
        # If config read fails, fall back to default
        pass

    # Default friendly name
    return "Hardware Lab"


def get_lab_networks() -> List[str]:
    """
    Get list of lab networks for scanning.

    Priority:
    1. Networks from lab_devices.json config file
    2. TARGET_NETWORK environment variable (as single-item list)
    3. Default: [target_network]

    Returns:
        List of network CIDR strings
    """
    # Check config file first
    try:
        if LAB_DEVICES_JSON.exists():
            import json

            with open(LAB_DEVICES_JSON) as f:
                config = json.load(f)
                infrastructure = config.get("lab_infrastructure", {})
                network_access = infrastructure.get("network_access", {})
                lab_networks = network_access.get("lab_networks")
                if lab_networks and isinstance(lab_networks, list):
                    return lab_networks
    except Exception:
        pass

    # Fall back to target network
    return [get_target_network()]


def validate_config() -> tuple:
    """Validate that required configuration files exist"""
    errors = []

    if not LAB_TESTING_ROOT.exists():
        errors.append(f"Lab testing root directory not found: {LAB_TESTING_ROOT}")

    if not LAB_DEVICES_JSON.exists():
        errors.append(f"Lab devices configuration not found: {LAB_DEVICES_JSON}")

    if not SCRIPTS_DIR.exists():
        errors.append(f"Scripts directory not found: {SCRIPTS_DIR}")

    return len(errors) == 0, errors
