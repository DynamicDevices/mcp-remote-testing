"""
Configuration management for Lab Testing MCP Server

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import os
from pathlib import Path
from typing import Optional

# Default paths - can be overridden via environment variables
DEFAULT_LAB_TESTING_ROOT = Path("/data_drive/esl/lab-testing")
LAB_TESTING_ROOT = Path(os.getenv("LAB_TESTING_ROOT", DEFAULT_LAB_TESTING_ROOT))

# Configuration file paths
CONFIG_DIR = LAB_TESTING_ROOT / "config"
SECRETS_DIR = LAB_TESTING_ROOT / "secrets"
SCRIPTS_DIR = LAB_TESTING_ROOT / "scripts" / "local"
LOGS_DIR = LAB_TESTING_ROOT / "logs"
CACHE_DIR = Path.home() / ".cache" / "lab-testing"

# Key configuration files
LAB_DEVICES_JSON = CONFIG_DIR / "lab_devices.json"

# VPN configuration - can be overridden via VPN_CONFIG_PATH environment variable
# If not set, searches common locations
VPN_CONFIG_PATH_ENV = os.getenv("VPN_CONFIG_PATH")

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
                if 'wg' in f.name.lower() or 'wireguard' in f.name.lower():
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

def get_scripts_dir() -> Path:
    """Get path to scripts directory"""
    return SCRIPTS_DIR

def get_logs_dir() -> Path:
    """Get path to logs directory"""
    return LOGS_DIR

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

