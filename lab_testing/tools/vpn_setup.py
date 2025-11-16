"""
WireGuard VPN Setup Helper

Helps users set up WireGuard VPN configuration for the MCP server.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from lab_testing.config import SECRETS_DIR, get_vpn_config


def check_wireguard_installed() -> Dict[str, Any]:
    """Check if WireGuard tools are installed"""
    try:
        result = subprocess.run(
            ["wg", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5
        )
        installed = result.returncode == 0
        return {
            "installed": installed,
            "version": result.stdout.strip() if installed else None,
            "error": result.stderr if not installed else None
        }
    except FileNotFoundError:
        return {
            "installed": False,
            "error": "WireGuard tools not found. Install with: sudo apt install wireguard-tools (Debian/Ubuntu) or sudo yum install wireguard-tools (RHEL/CentOS)"
        }
    except Exception as e:
        return {
            "installed": False,
            "error": f"Failed to check WireGuard: {e!s}"
        }


def list_existing_configs() -> Dict[str, Any]:
    """List existing WireGuard configuration files"""
    configs = []
    
    # Check secrets directory
    if SECRETS_DIR.exists():
        for conf_file in SECRETS_DIR.glob("*.conf"):
            configs.append({
                "path": str(conf_file),
                "name": conf_file.name,
                "location": "secrets"
            })
    
    # Check common system locations
    system_locations = [
        (Path.home() / ".config" / "wireguard", "user_config"),
        (Path("/etc/wireguard"), "system"),
    ]
    
    for location, loc_type in system_locations:
        if location.exists():
            for conf_file in location.glob("*.conf"):
                configs.append({
                    "path": str(conf_file),
                    "name": conf_file.name,
                    "location": loc_type
                })
    
    return {
        "configs": configs,
        "count": len(configs)
    }


def create_config_template(output_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Create a WireGuard configuration template.
    
    Args:
        output_path: Where to save the template (default: SECRETS_DIR/wg0.conf)
    
    Returns:
        Dictionary with creation results
    """
    if output_path is None:
        output_path = SECRETS_DIR / "wg0.conf"
    
    # Ensure secrets directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    template = """[Interface]
# Your private key (generate with: wg genkey | tee privatekey | wg pubkey > publickey)
PrivateKey = YOUR_PRIVATE_KEY_HERE

# Your local IP address on the VPN network
Address = 10.0.0.X/24

# Optional: DNS servers to use when connected
# DNS = 8.8.8.8, 8.8.4.4

[Peer]
# Server's public key
PublicKey = SERVER_PUBLIC_KEY_HERE

# Server endpoint (IP or hostname:port)
Endpoint = vpn.example.com:51820

# Allowed IPs (routes to send through VPN)
# Use 0.0.0.0/0 for all traffic, or specific subnets for lab network only
AllowedIPs = 192.168.0.0/16, 10.0.0.0/8

# Optional: Keep connection alive
PersistentKeepalive = 25
"""
    
    try:
        if output_path.exists():
            return {
                "success": False,
                "error": f"Configuration file already exists: {output_path}",
                "path": str(output_path)
            }
        
        output_path.write_text(template)
        output_path.chmod(0o600)  # Secure permissions
        
        return {
            "success": True,
            "path": str(output_path),
            "message": f"Template created at {output_path}. Edit it with your VPN server details."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create template: {e!s}"
        }


def setup_networkmanager_connection(config_path: Path) -> Dict[str, Any]:
    """
    Import WireGuard config into NetworkManager.
    
    This allows connecting without root privileges.
    
    Args:
        config_path: Path to WireGuard .conf file
    
    Returns:
        Dictionary with setup results
    """
    if not config_path.exists():
        return {
            "success": False,
            "error": f"Configuration file not found: {config_path}"
        }
    
    try:
        # Import into NetworkManager
        # NetworkManager expects the connection name to match the config filename
        connection_name = config_path.stem
        
        result = subprocess.run(
            ["nmcli", "connection", "import", "type", "wireguard", "file", str(config_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "connection_name": connection_name,
                "message": f"WireGuard connection '{connection_name}' imported into NetworkManager. You can now connect without root."
            }
        else:
            return {
                "success": False,
                "error": f"Failed to import into NetworkManager: {result.stderr}",
                "hint": "You can still use wg-quick with sudo, or import manually via NetworkManager GUI"
            }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "NetworkManager (nmcli) not found. Install with: sudo apt install network-manager (Debian/Ubuntu)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to setup NetworkManager connection: {e!s}"
        }


def get_setup_instructions() -> Dict[str, Any]:
    """Get setup instructions for WireGuard VPN"""
    return {
        "instructions": {
            "1_install": {
                "title": "Install WireGuard Tools",
                "debian_ubuntu": "sudo apt update && sudo apt install wireguard-tools",
                "rhel_centos": "sudo yum install wireguard-tools",
                "arch": "sudo pacman -S wireguard-tools",
                "macos": "brew install wireguard-tools"
            },
            "2_generate_keys": {
                "title": "Generate Key Pair",
                "commands": [
                    "wg genkey | tee privatekey | wg pubkey > publickey",
                    "# Share publickey with your VPN server administrator"
                ]
            },
            "3_create_config": {
                "title": "Create Configuration",
                "description": "Use the create_config_template tool to generate a template, then edit it with your server details",
                "locations": [
                    f"{SECRETS_DIR}/wg0.conf (recommended)",
                    "~/.config/wireguard/wg0.conf",
                    "/etc/wireguard/wg0.conf (requires root)"
                ]
            },
            "4_import_networkmanager": {
                "title": "Import into NetworkManager (Optional)",
                "description": "Allows connecting without root privileges",
                "command": "nmcli connection import type wireguard file /path/to/wg0.conf"
            },
            "5_test_connection": {
                "title": "Test Connection",
                "description": "Use the connect_vpn tool or manually:",
                "networkmanager": "nmcli connection up wg0",
                "wg_quick": "sudo wg-quick up /path/to/wg0.conf"
            },
            "6_configure_mcp": {
                "title": "Configure MCP Server",
                "description": "Set VPN_CONFIG_PATH environment variable if using non-standard location:",
                "example": "export VPN_CONFIG_PATH=/path/to/your/wg0.conf"
            }
        },
        "current_config": {
            "detected": get_vpn_config() is not None,
            "path": str(get_vpn_config()) if get_vpn_config() else None
        },
        "existing_configs": list_existing_configs()
    }

