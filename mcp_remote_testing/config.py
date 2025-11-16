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

# Key configuration files
LAB_DEVICES_JSON = CONFIG_DIR / "lab_devices.json"
VPN_CONFIG = SECRETS_DIR / "Grosny-IoT-VPN-Alex.conf"
VPN_CONFIG_ALT = SECRETS_DIR / "wg0.conf"

def get_lab_devices_config() -> Path:
    """Get path to lab devices configuration file"""
    return LAB_DEVICES_JSON

def get_vpn_config() -> Optional[Path]:
    """Get path to VPN configuration file"""
    if VPN_CONFIG.exists():
        return VPN_CONFIG
    if VPN_CONFIG_ALT.exists():
        return VPN_CONFIG_ALT
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

