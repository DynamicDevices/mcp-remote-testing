"""
VPN Management Tools for MCP Server
"""

import subprocess
from typing import Any, Dict, Optional

from lab_testing.config import get_vpn_config


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


def get_vpn_statistics() -> Dict[str, Any]:
    """
    Get detailed WireGuard VPN statistics including transfer data, handshakes, and latency.

    Returns:
        Dictionary with detailed VPN statistics
    """
    try:
        # Get detailed statistics from wg show
        result = subprocess.run(
            ["wg", "show", "all", "dump"],
            check=False, capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0 or not result.stdout.strip():
            return {
                "connected": False,
                "error": "No active WireGuard interfaces found"
            }

        interfaces = []
        current_interface = None
        current_interface_data = None

        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            
            # Interface line format: interface_name\tpublic_key\tlisten_port\tfwmark
            if len(parts) >= 2 and not parts[0].startswith("peer"):
                # This is an interface or peer line
                if len(parts) >= 4:
                    # Interface line
                    if current_interface_data:
                        interfaces.append(current_interface_data)
                    
                    current_interface = parts[0]
                    current_interface_data = {
                        "interface": current_interface,
                        "public_key": parts[1] if len(parts) > 1 else None,
                        "listen_port": int(parts[2]) if len(parts) > 2 and parts[2] else None,
                        "peers": []
                    }
                elif len(parts) >= 8 and current_interface_data:
                    # Peer line: public_key\tpreshared_key\tendpoint\tallowed_ips\tlast_handshake\ttransfer_rx\ttransfer_tx\tpersistent_keepalive
                    try:
                        peer_public_key = parts[0]
                        endpoint = parts[2] if len(parts) > 2 else None
                        allowed_ips = parts[3].split(",") if len(parts) > 3 and parts[3] else []
                        
                        # Parse last handshake (seconds since epoch)
                        last_handshake = None
                        if len(parts) > 4 and parts[4] and parts[4] != "0":
                            try:
                                last_handshake_seconds = int(parts[4])
                                import time
                                last_handshake = {
                                    "timestamp": last_handshake_seconds,
                                    "age_seconds": int(time.time()) - last_handshake_seconds,
                                    "age_human": _format_duration(int(time.time()) - last_handshake_seconds)
                                }
                            except (ValueError, TypeError):
                                pass
                        
                        # Parse transfer stats (bytes)
                        transfer_rx = int(parts[5]) if len(parts) > 5 and parts[5] else 0
                        transfer_tx = int(parts[6]) if len(parts) > 6 and parts[6] else 0
                        
                        persistent_keepalive = int(parts[7]) if len(parts) > 7 and parts[7] else None
                        
                        current_interface_data["peers"].append({
                            "public_key": peer_public_key[:16] + "..." if len(peer_public_key) > 16 else peer_public_key,
                            "public_key_full": peer_public_key,
                            "endpoint": endpoint,
                            "allowed_ips": allowed_ips,
                            "last_handshake": last_handshake,
                            "transfer": {
                                "rx_bytes": transfer_rx,
                                "tx_bytes": transfer_tx,
                                "rx_mb": round(transfer_rx / (1024 * 1024), 2),
                                "tx_mb": round(transfer_tx / (1024 * 1024), 2),
                                "total_bytes": transfer_rx + transfer_tx,
                                "total_mb": round((transfer_rx + transfer_tx) / (1024 * 1024), 2)
                            },
                            "persistent_keepalive": persistent_keepalive
                        })
                    except (ValueError, IndexError) as e:
                        # Skip malformed peer lines
                        continue

        if current_interface_data:
            interfaces.append(current_interface_data)

        # Calculate totals
        total_rx = sum(sum(p["transfer"]["rx_bytes"] for p in iface.get("peers", [])) for iface in interfaces)
        total_tx = sum(sum(p["transfer"]["tx_bytes"] for p in iface.get("peers", [])) for iface in interfaces)

        return {
            "connected": len(interfaces) > 0,
            "interfaces": interfaces,
            "summary": {
                "total_interfaces": len(interfaces),
                "total_peers": sum(len(iface.get("peers", [])) for iface in interfaces),
                "total_transfer_rx_mb": round(total_rx / (1024 * 1024), 2),
                "total_transfer_tx_mb": round(total_tx / (1024 * 1024), 2),
                "total_transfer_mb": round((total_rx + total_tx) / (1024 * 1024), 2)
            }
        }

    except FileNotFoundError:
        return {
            "connected": False,
            "error": "WireGuard tools not found. Install wireguard-tools package."
        }
    except Exception as e:
        return {
            "connected": False,
            "error": f"Failed to get VPN statistics: {e!s}"
        }


def _format_duration(seconds: int) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def _find_networkmanager_connection() -> Optional[str]:
    """Find NetworkManager WireGuard connection name"""
    try:
        # List all WireGuard connections
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            check=False, capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "wireguard" in line.lower():
                    parts = line.split(":")
                    if len(parts) >= 2:
                        return parts[0]
    except Exception:
        pass
    return None


def connect_vpn() -> Dict[str, Any]:
    """
    Connect to WireGuard VPN.

    Tries multiple methods:
    1. NetworkManager (if connection exists, doesn't require root)
    2. wg-quick (requires root/sudo)

    Returns:
        Dictionary with connection results
    """
    vpn_config = get_vpn_config()

    if not vpn_config or not vpn_config.exists():
        return {
            "success": False,
            "error": "VPN configuration file not found. See docs/SETUP.md for setup instructions."
        }

    try:
        # Try using NetworkManager first (doesn't require root for user connections)
        nm_connection = _find_networkmanager_connection()
        if nm_connection:
            nm_result = subprocess.run(
                ["nmcli", "connection", "up", nm_connection],
                check=False, capture_output=True,
                text=True,
                timeout=10
            )

            if nm_result.returncode == 0:
                return {
                    "success": True,
                    "method": "networkmanager",
                    "connection": nm_connection,
                    "message": f"VPN connected via NetworkManager: {nm_connection}"
                }

        # Fallback: Try wg-quick (requires root)
        # Extract interface name from config file
        interface_name = vpn_config.stem  # Use filename without extension as interface name
        
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
                "interface": interface_name,
                "message": f"VPN connected via wg-quick: {interface_name}"
            }
        return {
            "success": False,
            "error": f"Failed to connect VPN: {wg_result.stderr}",
            "nm_error": nm_result.stderr if nm_connection else "No NetworkManager connection found",
            "config_file": str(vpn_config)
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
        nm_connection = _find_networkmanager_connection()
        if nm_connection:
            nm_result = subprocess.run(
                ["nmcli", "connection", "down", nm_connection],
                check=False, capture_output=True,
                text=True,
                timeout=10
            )

            if nm_result.returncode == 0:
                return {
                    "success": True,
                    "method": "networkmanager",
                    "connection": nm_connection,
                    "message": f"VPN disconnected via NetworkManager: {nm_connection}"
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

