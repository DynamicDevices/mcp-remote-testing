"""
Network Topology Mapping Tool

Scans the network and creates a visual map of running systems and their status.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import concurrent.futures
import ipaddress
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lab_testing.config import get_lab_devices_config
from lab_testing.tools.device_manager import ssh_to_device, test_device
from lab_testing.tools.tasmota_control import get_power_switch_for_device
from lab_testing.utils.logger import get_logger

logger = get_logger()


def _ping_host(ip: str, timeout: int = 2) -> Tuple[str, bool, Optional[float]]:
    """Ping a single host and return (ip, reachable, latency_ms)"""
    try:
        start = time.time()
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout + 1
        )
        latency = (time.time() - start) * 1000  # Convert to ms
        return (ip, result.returncode == 0, latency if result.returncode == 0 else None)
    except Exception:
        return (ip, False, None)


def _scan_network_range(network: str, max_hosts: int = 254, timeout: int = 1) -> List[Dict[str, Any]]:
    """
    Scan a network range for active hosts.
    
    Args:
        network: Network CIDR (e.g., "192.168.1.0/24")
        max_hosts: Maximum number of hosts to scan (to avoid long scans)
        timeout: Ping timeout per host
    
    Returns:
        List of active hosts with their IPs and latency
    """
    try:
        net = ipaddress.ip_network(network, strict=False)
        hosts = list(net.hosts())[:max_hosts]  # Limit to avoid huge scans
        
        active_hosts = []
        
        # Use thread pool for parallel pings
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(_ping_host, str(host), timeout): str(host) for host in hosts}
            
            for future in concurrent.futures.as_completed(futures):
                ip, reachable, latency = future.result()
                if reachable:
                    active_hosts.append({
                        "ip": ip,
                        "latency_ms": round(latency, 2) if latency else None,
                        "status": "online"
                    })
        
        return sorted(active_hosts, key=lambda x: ipaddress.IPv4Address(x["ip"]))
    
    except Exception as e:
        logger.warning(f"Failed to scan network {network}: {e}")
        return []


def _get_device_info_from_config(ip: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get device information from config by IP address"""
    devices = config.get("devices", {})
    for device_id, device_info in devices.items():
        if device_info.get("ip") == ip:
            return {
                "device_id": device_id,
                "name": device_info.get("name", "Unknown"),
                "type": device_info.get("device_type", "unknown"),
                "status": device_info.get("status", "unknown")
            }
    return None


def create_network_map(
    networks: Optional[List[str]] = None,
    scan_networks: bool = True,
    test_configured_devices: bool = True,
    max_hosts_per_network: int = 254
) -> Dict[str, Any]:
    """
    Create a visual map of the network showing what's up and what isn't.
    
    Args:
        networks: List of network CIDRs to scan (e.g., ["192.168.1.0/24"])
                  If None, uses networks from config
        scan_networks: If True, actively scan networks for hosts
        test_configured_devices: If True, test all configured devices
        max_hosts_per_network: Maximum hosts to scan per network
    
    Returns:
        Dictionary with network map including:
        - Active hosts discovered
        - Configured devices status
        - Network topology visualization
        - Summary statistics
    """
    try:
        # Load device configuration
        config_path = get_lab_devices_config()
        with open(config_path) as f:
            config = json.load(f)
        
        devices = config.get("devices", {})
        infrastructure = config.get("lab_infrastructure", {})
        
        # Get networks to scan
        if networks is None:
            networks = infrastructure.get("network_access", {}).get("lab_networks", [])
            if not networks:
                # Default to common lab networks
                networks = ["192.168.1.0/24", "192.168.2.0/24"]
        
        result = {
            "timestamp": time.time(),
            "networks_scanned": networks,
            "active_hosts": [],
            "configured_devices": {},
            "unknown_hosts": [],
            "summary": {}
        }
        
        # Scan networks for active hosts
        if scan_networks:
            logger.info(f"Scanning {len(networks)} networks for active hosts...")
            for network in networks:
                active = _scan_network_range(network, max_hosts_per_network)
                result["active_hosts"].extend(active)
        
        # Test configured devices
        if test_configured_devices:
            logger.info(f"Testing {len(devices)} configured devices...")
            device_statuses = {}
            
            # Test devices in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(test_device, device_id): device_id for device_id in devices.keys()}
                
                for future in concurrent.futures.as_completed(futures):
                    device_id = futures[future]
                    try:
                        test_result = future.result()
                        device_info = devices[device_id]
                        
                        # Get additional info
                        friendly_name = device_info.get("friendly_name") or device_info.get("name", device_id)
                        power_switch = get_power_switch_for_device(device_id)
                        
                        # Get uptime if device is online
                        uptime = None
                        if test_result.get("ping_reachable", False) or test_result.get("ping", {}).get("success", False):
                            try:
                                uptime_result = ssh_to_device(device_id, "uptime -p 2>/dev/null || cat /proc/uptime | awk '{print int($1/60) \" minutes\"}'")
                                if uptime_result.get("success"):
                                    uptime = uptime_result.get("stdout", "").strip()
                            except Exception:
                                pass
                        
                        device_statuses[device_id] = {
                            "device_id": device_id,
                            "friendly_name": friendly_name,
                            "name": device_info.get("name", "Unknown"),
                            "ip": device_info.get("ip"),
                            "type": device_info.get("device_type", "unknown"),
                            "ping": test_result.get("ping", {}).get("success", False) if isinstance(test_result.get("ping"), dict) else test_result.get("ping_reachable", False),
                            "ssh": test_result.get("ssh", {}).get("success", False) if isinstance(test_result.get("ssh"), dict) else test_result.get("ssh_available", False),
                            "status": "online" if (test_result.get("ping", {}).get("success", False) if isinstance(test_result.get("ping"), dict) else test_result.get("ping_reachable", False)) else "offline",
                            "uptime": uptime,
                            "power_switch": power_switch
                        }
                    except Exception as e:
                        device_info = devices[device_id]
                        friendly_name = device_info.get("friendly_name") or device_info.get("name", device_id)
                        device_statuses[device_id] = {
                            "device_id": device_id,
                            "friendly_name": friendly_name,
                            "name": device_info.get("name", "Unknown"),
                            "ip": device_info.get("ip"),
                            "type": device_info.get("device_type", "unknown"),
                            "status": "error",
                            "error": str(e)
                        }
            
            result["configured_devices"] = device_statuses
        
        # Match active hosts with configured devices
        configured_ips = {dev.get("ip") for dev in result["configured_devices"].values() if dev.get("ip")}
        
        for host in result["active_hosts"]:
            ip = host["ip"]
            if ip not in configured_ips:
                # Check if we can identify it
                device_info = _get_device_info_from_config(ip, config)
                if device_info:
                    host["device_id"] = device_info["device_id"]
                    host["name"] = device_info["name"]
                    host["type"] = device_info["type"]
                else:
                    result["unknown_hosts"].append(host)
        
        # Create summary
        online_devices = sum(1 for d in result["configured_devices"].values() if d.get("status") == "online")
        offline_devices = sum(1 for d in result["configured_devices"].values() if d.get("status") == "offline")
        
        result["summary"] = {
            "total_configured_devices": len(result["configured_devices"]),
            "online_devices": online_devices,
            "offline_devices": offline_devices,
            "active_hosts_found": len(result["active_hosts"]),
            "unknown_hosts": len(result["unknown_hosts"]),
            "networks_scanned": len(networks)
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Failed to create network map: {e}", exc_info=True)
        return {
            "error": f"Failed to create network map: {e!s}",
            "timestamp": time.time()
        }


def generate_network_map_visualization(network_map: Dict[str, Any], format: str = "text") -> str:
    """
    Generate a visual representation of the network map.
    
    Args:
        network_map: Network map dictionary from create_network_map
        format: Output format ("text", "json", "mermaid")
    
    Returns:
        Visual representation as string
    """
    if "error" in network_map:
        return f"Error: {network_map['error']}"
    
    if format == "json":
        return json.dumps(network_map, indent=2)
    
    if format == "mermaid":
        # Generate Mermaid diagram
        lines = ["graph TB"]
        lines.append("    subgraph \"Network Map\"")
        
        # Add configured devices
        for device_id, device in network_map.get("configured_devices", {}).items():
            status = device.get("status", "unknown")
            status_icon = "✓" if status == "online" else "✗"
            color = "green" if status == "online" else "red"
            lines.append(f"        {device_id.replace('-', '_')}[\"{status_icon} {device.get('name', device_id)}\"]")
            lines.append(f"        style {device_id.replace('-', '_')} fill:#{color}33")
        
        # Add unknown hosts
        for i, host in enumerate(network_map.get("unknown_hosts", [])[:10]):  # Limit to 10
            host_id = f"unknown_{i}"
            lines.append(f"        {host_id}[\"? {host['ip']}\"]")
            lines.append(f"        style {host_id} fill:#yellow33")
        
        lines.append("    end")
        return "\n".join(lines)
    
    # Default: text format
    lines = []
    lines.append("=" * 70)
    lines.append("Network Topology Map")
    lines.append("=" * 70)
    lines.append("")
    
    summary = network_map.get("summary", {})
    lines.append(f"Summary:")
    lines.append(f"  Configured Devices: {summary.get('total_configured_devices', 0)}")
    lines.append(f"  Online: {summary.get('online_devices', 0)}")
    lines.append(f"  Offline: {summary.get('offline_devices', 0)}")
    lines.append(f"  Active Hosts Found: {summary.get('active_hosts_found', 0)}")
    lines.append(f"  Unknown Hosts: {summary.get('unknown_hosts', 0)}")
    lines.append("")
    
    # Configured devices by status
    online_devices = [d for d in network_map.get("configured_devices", {}).values() if d.get("status") == "online"]
    offline_devices = [d for d in network_map.get("configured_devices", {}).values() if d.get("status") == "offline"]
    
    if online_devices:
        lines.append("Online Devices:")
        for device in sorted(online_devices, key=lambda x: x.get("ip", "")):
            lines.append(f"  ✓ {device.get('name', 'Unknown')} ({device.get('ip', 'N/A')})")
            if device.get("ping"):
                lines.append(f"      Ping: OK")
            if device.get("ssh"):
                lines.append(f"      SSH: OK")
        lines.append("")
    
    if offline_devices:
        lines.append("Offline Devices:")
        for device in sorted(offline_devices, key=lambda x: x.get("ip", "")):
            lines.append(f"  ✗ {device.get('name', 'Unknown')} ({device.get('ip', 'N/A')})")
        lines.append("")
    
    # Unknown hosts
    unknown = network_map.get("unknown_hosts", [])
    if unknown:
        lines.append(f"Unknown Active Hosts ({len(unknown)}):")
        for host in sorted(unknown[:20], key=lambda x: x.get("ip", "")):  # Show first 20
            latency = f" ({host.get('latency_ms', 0):.1f}ms)" if host.get("latency_ms") else ""
            lines.append(f"  ? {host.get('ip')}{latency}")
        if len(unknown) > 20:
            lines.append(f"  ... and {len(unknown) - 20} more")
        lines.append("")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)

