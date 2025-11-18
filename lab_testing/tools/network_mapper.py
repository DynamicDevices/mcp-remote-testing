"""
Network Topology Mapping Tool

Scans the network and creates a visual map of running systems and their status.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import base64
import concurrent.futures
import io
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

# Try to import matplotlib for image generation
try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not available - image generation disabled")


def _ping_host(ip: str, timeout: float = 0.5) -> Tuple[str, bool, Optional[float]]:
    """Ping a single host and return (ip, reachable, latency_ms)

    Args:
        ip: IP address to ping
        timeout: Ping timeout in seconds (default: 0.5 for faster scanning)
    """
    try:
        start = time.time()
        # Use shorter timeout for faster scanning
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(int(timeout * 1000)), ip],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout + 0.5,  # Add small buffer
        )
        latency = (time.time() - start) * 1000  # Convert to ms
        return (ip, result.returncode == 0, latency if result.returncode == 0 else None)
    except subprocess.TimeoutExpired:
        return (ip, False, None)
    except Exception:
        return (ip, False, None)


def _scan_network_range(
    network: str, max_hosts: int = 254, timeout: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Scan a network range for active hosts.

    Args:
        network: Network CIDR (e.g., "192.168.1.0/24")
        max_hosts: Maximum number of hosts to scan (to avoid long scans)
        timeout: Ping timeout per host in seconds (default: 0.5 for faster scanning)

    Returns:
        List of active hosts with their IPs and latency
    """
    try:
        net = ipaddress.ip_network(network, strict=False)
        hosts = list(net.hosts())[:max_hosts]  # Limit to avoid huge scans

        active_hosts = []

        # Use thread pool for parallel pings - increased workers for faster scanning
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = {executor.submit(_ping_host, str(host), timeout): str(host) for host in hosts}

            for future in concurrent.futures.as_completed(futures):
                ip, reachable, latency = future.result()
                if reachable:
                    active_hosts.append(
                        {
                            "ip": ip,
                            "latency_ms": round(latency, 2) if latency else None,
                            "status": "online",
                        }
                    )

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
                "type": device_info.get(
                    "device_type", "unknown"
                ),  # Note: config uses "device_type"
                "status": device_info.get("status", "unknown"),
            }
    return None


def create_network_map(
    networks: Optional[List[str]] = None,
    scan_networks: bool = True,
    test_configured_devices: bool = True,
    max_hosts_per_network: int = 254,
    quick_mode: bool = False,
    layout: str = "lr",
    group_by: str = "type",
    show_details: bool = False,
    show_metrics: bool = True,
    show_alerts: bool = True,
    show_history: bool = False,
    export_format: str = "mermaid",
    export_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a visual map of the network showing what's up and what isn't.

    Now uses list_devices() data for comprehensive device information including
    Tasmota power states, test equipment detection, and SSH status.

    Args:
        networks: List of network CIDRs to scan (e.g., ["192.168.1.0/24"])
                  If None, uses networks from config
        scan_networks: If True, actively scan networks for hosts (for unknown hosts discovery)
        test_configured_devices: If True, use list_devices to get device status (always True now)
        max_hosts_per_network: Maximum hosts to scan per network
        quick_mode: If True, skip network scanning entirely (faster, <5s)
        layout: Layout style - 'lr' (left-right), 'tb' (top-bottom), 'radial', 'hierarchical', 'grid'
        group_by: Group devices by - 'type', 'status', 'location', 'power_circuit', 'none'
        show_details: If True, show detailed device information in node labels
        show_metrics: If True, color-code devices by latency and show performance metrics
        show_alerts: If True, highlight devices with errors, warnings, or issues
        show_history: If True, show historical status changes and uptime indicators
        export_format: Export format - 'mermaid', 'png', 'svg', 'pdf', 'html', 'json', 'csv'
        export_path: Optional path to save exported file

    Returns:
        Dictionary with network map including:
        - Active hosts discovered
        - Configured devices status (from list_devices)
        - Network topology visualization
        - Summary statistics
        - Visualization options and export data
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
            # Use get_target_network directly to avoid import issues with cached modules
            from lab_testing.config import get_target_network

            networks = [get_target_network()]

        result = {
            "timestamp": time.time(),
            "networks_scanned": networks if not quick_mode else [],
            "active_hosts": [],
            "configured_devices": {},
            "unknown_hosts": [],
            "summary": {},
        }

        # Use list_devices to get comprehensive device information
        # This includes scanning, identification, Tasmota detection, test equipment detection, etc.
        if test_configured_devices:
            logger.info("Using list_devices() to get comprehensive device information...")
            from lab_testing.tools.device_manager import list_devices

            # Get all devices from list_devices (uses cache, does scanning/identification)
            devices_result = list_devices(show_summary=False)

            if devices_result.get("success"):
                # Transform list_devices output to network_map format
                devices_by_type = devices_result.get("devices_by_type", {})

                # Flatten devices_by_type into a single list
                all_devices = []
                for device_type, device_list in devices_by_type.items():
                    for device in device_list:
                        device["_source_type"] = device_type
                        all_devices.append(device)

                # Convert to configured_devices format (keyed by device_id)
                device_statuses = {}
                configured_ips = set()

                for device in all_devices:
                    device_id = device.get("id") or device.get("device_id")
                    if not device_id:
                        continue

                    ip = device.get("ip")
                    if ip:
                        configured_ips.add(ip)

                    # Get power switch info
                    power_switch = device.get("power_switch")
                    if isinstance(power_switch, dict):
                        power_switch = power_switch.get("device_id")

                    # Determine ping/ssh status from device data
                    status = device.get("status", "discovered")
                    hostname = device.get("hostname")
                    ssh_error = device.get("ssh_error")

                    ping_ok = status in [
                        "online",
                        "discovered",
                    ]  # If device is discovered/online, ping worked
                    ssh_ok = (
                        hostname is not None and not ssh_error
                    )  # SSH OK if we have hostname and no error

                    # Map status: "discovered" means device is reachable (ping worked), so treat as "online" for network map
                    # "online" means fully identified with SSH, "discovered" means pingable but not SSH'd
                    network_map_status = (
                        "online" if status in ["online", "discovered"] else "offline"
                    )

                    device_statuses[device_id] = {
                        "device_id": device_id,
                        "friendly_name": device.get("friendly_name")
                        or device.get("name", device_id),
                        "name": device.get("name") or device.get("friendly_name", device_id),
                        "ip": ip,
                        "type": device.get("device_type") or device.get("_source_type", "unknown"),
                        "ping": ping_ok,
                        "ssh": ssh_ok,
                        "status": network_map_status,
                        "power_switch": power_switch,
                        "hostname": hostname,
                        "tasmota_power_state": device.get("tasmota_power_state"),
                        "tasmota_power_watts": device.get("tasmota_power_watts"),
                        "equipment_type": device.get("equipment_type"),
                    }

                result["configured_devices"] = device_statuses
                # Store configured IPs for later comparison
                configured_ips = set(configured_ips)
                logger.info(f"Found {len(device_statuses)} devices from list_devices()")
            else:
                logger.warning(
                    f"list_devices() failed: {devices_result.get('error', 'Unknown error')}"
                )
                configured_ips = set()

        # Scan networks for unknown hosts (hosts not in list_devices)
        scanned_hosts = []
        if scan_networks and not quick_mode:
            logger.info(f"Scanning {len(networks)} networks for unknown hosts...")
            # Use faster timeout for scanning
            ping_timeout = 0.5
            for network in networks:
                active = _scan_network_range(network, max_hosts_per_network, timeout=ping_timeout)
                scanned_hosts.extend(active)
        elif quick_mode:
            logger.info("Quick mode: Skipping network scan for unknown hosts")

        # Combine configured devices IPs with scanned hosts for active_hosts list
        result["active_hosts"] = [{"ip": ip, "status": "online"} for ip in configured_ips]
        result["active_hosts"].extend(scanned_hosts)

        # Match active hosts with configured devices - find unknown hosts
        configured_ips = {
            dev.get("ip") for dev in result["configured_devices"].values() if dev.get("ip")
        }

        # Get target network base for filtering
        from lab_testing.config import get_target_network

        target_network = get_target_network()
        target_network_base = ".".join(target_network.split("/")[0].split(".")[:3])

        for host in result["active_hosts"]:
            ip = host.get("ip") if isinstance(host, dict) else host
            if isinstance(host, str):
                ip = host
                host = {"ip": ip, "status": "online"}

            # Only process hosts on target network
            host_network_base = ".".join(ip.split(".")[:3])
            if host_network_base != target_network_base:
                continue  # Skip hosts not on target network

            if ip not in configured_ips:
                # Check if we can identify it from config
                device_info = _get_device_info_from_config(ip, config)
                if device_info:
                    host["device_id"] = device_info["device_id"]
                    host["name"] = device_info["name"]
                    host["type"] = device_info["type"]
                else:
                    result["unknown_hosts"].append(host)

        # Create summary - only count devices on target network
        from lab_testing.config import get_target_network

        target_network = get_target_network()
        target_network_base = ".".join(target_network.split("/")[0].split(".")[:3])

        # Filter devices to only those on target network for summary
        target_network_devices = {
            device_id: device
            for device_id, device in result["configured_devices"].items()
            if device.get("ip")
            and ".".join(device.get("ip", "").split(".")[:3]) == target_network_base
        }

        online_devices = sum(
            1 for d in target_network_devices.values() if d.get("status") == "online"
        )
        offline_devices = sum(
            1 for d in target_network_devices.values() if d.get("status") == "offline"
        )

        result["summary"] = {
            "total_configured_devices": len(target_network_devices),
            "online_devices": online_devices,
            "offline_devices": offline_devices,
            "active_hosts_found": len(result["active_hosts"]),
            "unknown_hosts": len(result["unknown_hosts"]),
            "networks_scanned": len(networks),
        }

        # Add visualization options to result
        result["visualization_options"] = {
            "layout": layout,
            "group_by": group_by,
            "show_details": show_details,
            "show_metrics": show_metrics,
            "show_alerts": show_alerts,
            "show_history": show_history,
            "export_format": export_format,
        }

        return result

    except Exception as e:
        logger.error(f"Failed to create network map: {e}", exc_info=True)
        return {"error": f"Failed to create network map: {e!s}", "timestamp": time.time()}


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
        lines.append('    subgraph "Network Map"')

        # Add configured devices
        for device_id, device in network_map.get("configured_devices", {}).items():
            status = device.get("status", "unknown")
            status_icon = "✓" if status == "online" else "✗"
            color = "green" if status == "online" else "red"
            lines.append(
                f"        {device_id.replace('-', '_')}[\"{status_icon} {device.get('name', device_id)}\"]"
            )
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
    lines.append("Summary:")
    lines.append(f"  Configured Devices: {summary.get('total_configured_devices', 0)}")
    lines.append(f"  Online: {summary.get('online_devices', 0)}")
    lines.append(f"  Offline: {summary.get('offline_devices', 0)}")
    lines.append(f"  Active Hosts Found: {summary.get('active_hosts_found', 0)}")
    lines.append(f"  Unknown Hosts: {summary.get('unknown_hosts', 0)}")
    lines.append("")

    # Configured devices by status
    online_devices = [
        d for d in network_map.get("configured_devices", {}).values() if d.get("status") == "online"
    ]
    offline_devices = [
        d
        for d in network_map.get("configured_devices", {}).values()
        if d.get("status") == "offline"
    ]

    if online_devices:
        lines.append("Online Devices:")
        for device in sorted(online_devices, key=lambda x: x.get("ip", "")):
            lines.append(f"  ✓ {device.get('name', 'Unknown')} ({device.get('ip', 'N/A')})")
            if device.get("ping"):
                lines.append("      Ping: OK")
            if device.get("ssh"):
                lines.append("      SSH: OK")
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


def generate_network_map_mermaid(network_map: Dict[str, Any]) -> str:
    """
    Generate a Mermaid diagram representation of the network topology.
    Enhanced with icons, friendly names, and clear power connections.

    Args:
        network_map: Network map dictionary from create_network_map

    Returns:
        Mermaid diagram as a string
    """
    if "error" in network_map:
        return f"```mermaid\ngraph TD\n    Error[\"❌ Error: {network_map['error']}\"]\n```"

    try:
        from lab_testing.config import get_target_network, get_target_network_friendly_name

        target_network = get_target_network()
        network_friendly_name = get_target_network_friendly_name()

        summary = network_map.get("summary", {})
        configured_devices = network_map.get("configured_devices", {})
        
        # Extract visualization options
        viz_options = network_map.get("visualization_options", {})
        layout = viz_options.get("layout", "lr")
        group_by = viz_options.get("group_by", "type")
        show_details = viz_options.get("show_details", False)
        show_metrics = viz_options.get("show_metrics", True)
        show_alerts = viz_options.get("show_alerts", True)
        show_history = viz_options.get("show_history", False)

        # Load full config to get power switch device info
        import json

        from lab_testing.config import get_lab_devices_config

        config_path = get_lab_devices_config()
        full_config = {}
        if config_path.exists():
            with open(config_path) as f:
                full_config = json.load(f)

        devices_config = full_config.get("devices", {})

        # Device type icons
        type_icons = {
            "development_board": "💻",
            "development_boards": "💻",
            "test_equipment": "🔬",
            "tasmota_device": "🔌",
            "server": "🖥️",
            "network_infrastructure": "🌐",
            "embedded_controllers": "⚙️",
            "other": "📱",
        }

        # Helper function to get latency color class
        def get_latency_color_class(latency_ms: Optional[float]) -> str:
            """Get color class based on latency for performance metrics"""
            if latency_ms is None:
                return "online"  # Default
            if latency_ms < 10:
                return "latency_excellent"  # Green
            elif latency_ms < 50:
                return "latency_good"  # Yellow
            elif latency_ms < 100:
                return "latency_fair"  # Orange
            else:
                return "latency_poor"  # Red

        # Helper function to get alert indicators
        def get_alert_indicators(device: Dict[str, Any]) -> List[str]:
            """Get alert indicators for a device"""
            alerts = []
            ssh_error = device.get("ssh_error")
            ssh_error_type = device.get("ssh_error_type")
            last_seen = device.get("last_seen")
            power_watts = device.get("tasmota_power_watts")
            
            # SSH errors
            if ssh_error:
                if ssh_error_type == "timeout":
                    alerts.append("⏱️ SSH Timeout")
                elif ssh_error_type == "refused":
                    alerts.append("🚫 SSH Refused")
                elif ssh_error_type == "auth_failed":
                    alerts.append("🔐 Auth Failed")
                else:
                    alerts.append("⚠️ SSH Error")
            
            # High power consumption warning (for Tasmota devices)
            if power_watts is not None and power_watts > 50:
                alerts.append("⚡ High Power")
            
            # Device not seen recently (if show_history enabled)
            if show_history and last_seen:
                # Parse last_seen timestamp if it's a string
                import datetime
                try:
                    if isinstance(last_seen, str):
                        # Try parsing ISO format or relative time
                        if "ago" in last_seen.lower():
                            # Relative time like "5m ago"
                            alerts.append(f"🕐 {last_seen}")
                        else:
                            # ISO timestamp
                            last_seen_dt = datetime.datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                            now = datetime.datetime.now(datetime.timezone.utc)
                            age = now - last_seen_dt
                            if age.total_seconds() > 3600:  # More than 1 hour
                                alerts.append(f"🕐 {int(age.total_seconds() / 3600)}h ago")
                except Exception:
                    pass
            
            return alerts

        # Helper function to build enhanced device label
        def build_device_label(device: Dict[str, Any], device_type: str, hostname: str, ip: str, 
                              is_gateway: bool = False) -> Tuple[str, str]:
            """Build device label with optional details, alerts, and metrics
            
            Returns:
                Tuple of (label_string, css_class)
            """
            icon = get_icon(device_type)
            label_parts = [f"{icon} {hostname}", ip]
            
            # Add gateway indicator
            if is_gateway:
                label_parts.insert(1, "🌐 Gateway")
            
            # Add device details if requested
            if show_details:
                # Manufacturer/model
                manufacturer = device.get("manufacturer")
                model = device.get("model")
                if manufacturer:
                    label_parts.append(f"Mfr: {manufacturer}")
                if model:
                    label_parts.append(f"Model: {model}")
                
                # Firmware version
                firmware = device.get("firmware")
                if firmware:
                    if isinstance(firmware, dict):
                        fw_version = firmware.get("version_id") or firmware.get("version", "Unknown")
                    else:
                        fw_version = str(firmware)
                    label_parts.append(f"FW: {fw_version[:20]}")
                
                # MAC address (if available)
                mac = device.get("mac_address") or device.get("mac")
                if mac:
                    label_parts.append(f"MAC: {mac[:17]}")
            
            # Add performance metrics if requested
            latency_ms = device.get("latency_ms")
            css_class = "online"  # Default
            
            if show_metrics and latency_ms is not None:
                label_parts.append(f"Ping: {latency_ms}ms")
                css_class = get_latency_color_class(latency_ms)
            
            # Add alert indicators if requested
            if show_alerts:
                alerts = get_alert_indicators(device)
                if alerts:
                    label_parts.extend(alerts)
                    # Override CSS class for devices with alerts
                    if ssh_error := device.get("ssh_error"):
                        css_class = "alert_device"
            
            # Add SSH status
            ssh_error = device.get("ssh_error")
            ssh_status = device.get("ssh_status")
            if not ssh_status:
                ssh_status = "error" if ssh_error else "ok"
            if ssh_status == "ok":
                label_parts.append("SSH: ✓")
            else:
                label_parts.append("SSH: ✗")
            
            # Join parts and wrap in quotes
            label = f'"{"<br/>".join(label_parts)}"'
            return label, css_class

        # Build Mermaid diagram with better layout for network visualization
        # Map layout parameter to Mermaid graph direction
        layout_map = {
            "lr": "LR",  # Left-right (default)
            "tb": "TD",  # Top-bottom
            "radial": "LR",  # Radial uses LR base with special styling
            "hierarchical": "TD",  # Hierarchical uses top-down
            "grid": "LR",  # Grid uses LR base
        }
        graph_direction = layout_map.get(layout, "LR")
        lines = ["```mermaid", f"graph {graph_direction}"]

        # Add styling for subgraph titles to make them more visible and prevent overlap
        # Set white background and improve subgraph title visibility
        lines.append(
            "    %%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff', 'primaryTextColor':'#000', 'primaryBorderColor':'#000', 'lineColor':'#000', 'secondaryColor':'#fff', 'tertiaryColor':'#fff', 'background':'#fff', 'subgraphTitleFontSize':'20px', 'subgraphTitleFontWeight':'bold', 'subgraphPadding':20}}}%%"
        )

        # Title with summary - use friendly name if available
        online_count = summary.get("online_devices", 0)
        total_count = summary.get("total_configured_devices", 0)
        title = f"{network_friendly_name}: {target_network} | {online_count} Online / {total_count} Total"
        lines.append(f'    subgraph Network["{title}"]')

        # Organize devices into logical groups for better network map visualization
        lines.append('        subgraph PowerSwitches["🔌 Power Switches"]')

        # Track nodes and power connections
        device_nodes = {}
        tasmota_nodes = {}  # Maps node_id -> {"label": ..., "device_id": ...}
        power_connections = []  # List of (tasmota_id, device_id) tuples

        # Track all Tasmota devices (including those that don't power anything)
        all_tasmota_devices = {}

        # Create mapping from device_id to node_id for power switch lookups
        device_id_to_node_id = {}  # Maps device_id -> node_id

        # Filter devices to only target network
        target_network_base = ".".join(target_network.split("/")[0].split(".")[:3])

        # Helper function to get icon for device type
        def get_icon(device_type):
            return type_icons.get(device_type, "📱")

        # First, identify all Tasmota devices (they should be shown even if not powering anything)
        for device_id, device in configured_devices.items():
            device_type = device.get("type", "other")
            if device_type == "tasmota_device":
                ip = device.get("ip", "")
                if ip:
                    device_network_base = ".".join(ip.split(".")[:3])
                    if device_network_base == target_network_base:
                        all_tasmota_devices[device_id] = device

        # Process online devices first
        online_devices = []
        for device_id, device in configured_devices.items():
            status = device.get("status", "offline")
            if status != "online":
                continue

            # Only include devices on target network
            ip = device.get("ip", "")
            if not ip:
                continue
            device_network_base = ".".join(ip.split(".")[:3])
            if device_network_base != target_network_base:
                continue

            online_devices.append((device_id, device))

        # Process offline devices
        offline_devices = []
        for device_id, device in configured_devices.items():
            status = device.get("status", "offline")
            if status != "offline":
                continue

            # Only include devices on target network
            ip = device.get("ip", "")
            if not ip:
                continue
            device_network_base = ".".join(ip.split(".")[:3])
            if device_network_base != target_network_base:
                continue

            offline_devices.append((device_id, device))

        # First, add all Tasmota devices (they're power sources, show them first)
        for device_id, device in all_tasmota_devices.items():
            if device.get("status") != "online":
                continue
            friendly_name = device.get("friendly_name") or device.get("name", device_id)
            ip = device.get("ip", "")
            power_state = device.get("tasmota_power_state", "")
            power_watts = device.get("tasmota_power_watts")

            tasmota_clean_name = (
                friendly_name.replace('"', "'").replace("\n", " ").replace("\r", " ")
            )
            if len(tasmota_clean_name) > 20:
                tasmota_clean_name = tasmota_clean_name[:17] + "..."

            # Add power state to label
            power_indicator = ""
            if power_state:
                power_indicator = f"<br/>{'🟢 ON' if power_state.lower() == 'on' else '🔴 OFF'}"
                if power_watts is not None:
                    power_indicator += f" {power_watts}W"

            tasmota_label = f'"🔌 {tasmota_clean_name}<br/>{ip}{power_indicator}"'
            tasmota_node_id = f"T_{device_id.replace('-', '_').replace('.', '_').replace('/', '_')}"
            tasmota_nodes[tasmota_node_id] = {"label": tasmota_label, "device_id": device_id}
            device_id_to_node_id[device_id] = tasmota_node_id
            lines.append(f"            {tasmota_node_id}({tasmota_label}):::tasmota_device")

        # Close PowerSwitches subgraph
        lines.append("        end")

        # Separate devices into test equipment and regular devices
        test_equipment_online = []
        regular_devices_online = []

        for device_id, device in online_devices:
            device_type = device.get("type", "other")
            # Skip Tasmota devices (already added above)
            if device_type == "tasmota_device":
                continue

            if device_type == "test_equipment":
                test_equipment_online.append((device_id, device))
            else:
                regular_devices_online.append((device_id, device))

        # Start Test Equipment subgraph
        if test_equipment_online:
            lines.append('        subgraph TestEquipment["🔬 Test Equipment"]')

            # Track equipment type counts for indexing
            equipment_type_counts = {}

            for idx, (device_id, device) in enumerate(test_equipment_online, 1):
                device_type = device.get("type", "other")
                equipment_type = device.get("equipment_type", "test_equipment")
                ip = device.get("ip", "")

                # Create friendly name: equipment_type + index
                # Capitalize equipment_type for display (e.g., "dmm" -> "DMM", "oscilloscope" -> "Oscilloscope")
                equipment_type_lower = equipment_type.lower()
                if equipment_type_lower == "dmm":
                    equipment_type_display = "DMM"
                elif equipment_type_lower == "oscilloscope":
                    equipment_type_display = "Oscilloscope"
                elif equipment_type_lower == "power_supply":
                    equipment_type_display = "Power Supply"
                else:
                    equipment_type_display = equipment_type.replace("_", " ").title()

                # Count equipment of this type for indexing
                if equipment_type not in equipment_type_counts:
                    equipment_type_counts[equipment_type] = 0
                equipment_type_counts[equipment_type] += 1
                equipment_index = equipment_type_counts[equipment_type]

                # Friendly name format: "DMM-1", "Oscilloscope-1", etc.
                friendly_name = f"{equipment_type_display}-{equipment_index}"

                # Clean friendly name for Mermaid
                clean_friendly_name = (
                    friendly_name.replace('"', "'").replace("\n", " ").replace("\r", " ")
                )

                icon = get_icon(device_type)
                # Show equipment type and IP
                node_label = f'"{icon} {clean_friendly_name}<br/>{equipment_type_display}<br/>{ip}"'

                node_id = f"D_{device_id.replace('-', '_').replace('.', '_').replace('/', '_')}"
                device_nodes[node_id] = {"type": device_type, "device_id": device_id}
                device_id_to_node_id[device_id] = node_id

                # Check for power switch relationship
                power_switch = device.get("power_switch")
                power_switch_id = None
                if power_switch:
                    if isinstance(power_switch, dict):
                        power_switch_id = power_switch.get("device_id")
                    else:
                        power_switch_id = power_switch

                if power_switch_id:
                    if power_switch_id in device_id_to_node_id:
                        tasmota_node_id = device_id_to_node_id[power_switch_id]
                        if tasmota_node_id in tasmota_nodes:
                            power_connections.append((tasmota_node_id, node_id))
                    elif power_switch_id in devices_config:
                        switch_info = devices_config[power_switch_id]
                        tasmota_ip = switch_info.get("ip", "")
                        if tasmota_ip:
                            switch_network_base = ".".join(tasmota_ip.split(".")[:3])
                            if switch_network_base == target_network_base:
                                tasmota_name = switch_info.get("friendly_name") or switch_info.get(
                                    "name", power_switch_id
                                )
                                if tasmota_node_id not in tasmota_nodes:
                                    tasmota_clean_name = (
                                        tasmota_name.replace('"', "'")
                                        .replace("\n", " ")
                                        .replace("\r", " ")
                                    )
                                    if len(tasmota_clean_name) > 20:
                                        tasmota_clean_name = tasmota_clean_name[:17] + "..."
                                    tasmota_label = f'"🔌 {tasmota_clean_name}<br/>{tasmota_ip}"'
                                    tasmota_nodes[tasmota_node_id] = {
                                        "label": tasmota_label,
                                        "device_id": power_switch_id,
                                    }
                                    device_id_to_node_id[power_switch_id] = tasmota_node_id
                                    lines.append(
                                        f"            {tasmota_node_id}({tasmota_label}):::tasmota_device"
                                    )
                                power_connections.append((tasmota_node_id, node_id))

                lines.append(f"            {node_id}({node_label}):::online")

            lines.append("        end")

        # Start Devices subgraph
        lines.append('        subgraph Devices["📱 Devices"]')

        # Process regular online devices (non-Tasmota, non-test-equipment)
        for device_id, device in regular_devices_online:
            device_type = device.get("type", "other")
            friendly_name = device.get("friendly_name") or device.get("name", device_id)
            hostname = device.get("hostname") or friendly_name
            ip = device.get("ip", "")

            # Check if this is a gateway/router (unifi or .1 address)
            is_gateway = False
            if "unifi" in hostname.lower() or ip.endswith(".1"):
                device_type = "network_infrastructure"
                is_gateway = True

            # Use full hostname, don't truncate
            clean_hostname = hostname.replace('"', "'").replace("\n", " ").replace("\r", " ")

            # Use helper function to build enhanced label
            node_label, css_class = build_device_label(device, device_type, clean_hostname, ip, is_gateway)

            node_id = f"D_{device_id.replace('-', '_').replace('.', '_').replace('/', '_')}"
            device_nodes[node_id] = {"type": device_type, "device_id": device_id}
            device_id_to_node_id[device_id] = node_id

            # Check for power switch relationship
            power_switch = device.get("power_switch")
            power_switch_id = None
            if power_switch:
                # Handle both dict format (from list_devices) and string format (from config)
                if isinstance(power_switch, dict):
                    power_switch_id = power_switch.get("device_id")
                else:
                    power_switch_id = power_switch

            if power_switch_id:
                # Try to find the Tasmota node using device_id mapping
                if power_switch_id in device_id_to_node_id:
                    tasmota_node_id = device_id_to_node_id[power_switch_id]
                    if tasmota_node_id in tasmota_nodes:
                        power_connections.append((tasmota_node_id, node_id))
                # Also check in devices_config as fallback
                elif power_switch_id in devices_config:
                    switch_info = devices_config[power_switch_id]
                    tasmota_ip = switch_info.get("ip", "")
                    if tasmota_ip:
                        switch_network_base = ".".join(tasmota_ip.split(".")[:3])
                        if switch_network_base == target_network_base:
                            tasmota_name = switch_info.get("friendly_name") or switch_info.get(
                                "name", power_switch_id
                            )
                            # Add Tasmota node if not already added
                            if tasmota_node_id not in tasmota_nodes:
                                tasmota_clean_name = (
                                    tasmota_name.replace('"', "'")
                                    .replace("\n", " ")
                                    .replace("\r", " ")
                                )
                                if len(tasmota_clean_name) > 20:
                                    tasmota_clean_name = tasmota_clean_name[:17] + "..."
                                tasmota_label = f'"🔌 {tasmota_clean_name}<br/>{tasmota_ip}"'
                                tasmota_nodes[tasmota_node_id] = {
                                    "label": tasmota_label,
                                    "device_id": power_switch_id,
                                }
                                device_id_to_node_id[power_switch_id] = tasmota_node_id
                                lines.append(
                                    f"            {tasmota_node_id}({tasmota_label}):::tasmota_device"
                                )
                            power_connections.append((tasmota_node_id, node_id))

            # Use network_infrastructure styling for gateway devices, but respect alert/metric classes
            if is_gateway and css_class == "online":
                final_css_class = "network_infrastructure"
            else:
                final_css_class = css_class
            lines.append(f"            {node_id}({node_label}):::{final_css_class}")

        # Separate offline devices into test equipment and regular devices
        test_equipment_offline = []
        regular_devices_offline = []

        for device_id, device in offline_devices[:15]:
            device_type = device.get("type", "other")
            # Skip Tasmota devices (already added above)
            if device_type == "tasmota_device":
                continue

            if device_type == "test_equipment":
                test_equipment_offline.append((device_id, device))
            else:
                regular_devices_offline.append((device_id, device))

        # Process offline test equipment in separate subgraph
        if test_equipment_offline:
            # Close Devices subgraph first
            lines.append("        end")
            # Start Test Equipment Offline subgraph
            lines.append('        subgraph TestEquipmentOffline["🔬 Test Equipment (Offline)"]')

            # Track equipment type counts for offline equipment indexing
            equipment_type_counts_offline = {}

            for device_id, device in test_equipment_offline:
                device_type = device.get("type", "other")
                equipment_type = device.get("equipment_type", "test_equipment")
                ip = device.get("ip", "")

                # Create friendly name: equipment_type + index
                # Capitalize equipment_type for display (e.g., "dmm" -> "DMM", "oscilloscope" -> "Oscilloscope")
                equipment_type_lower = equipment_type.lower()
                if equipment_type_lower == "dmm":
                    equipment_type_display = "DMM"
                elif equipment_type_lower == "oscilloscope":
                    equipment_type_display = "Oscilloscope"
                elif equipment_type_lower == "power_supply":
                    equipment_type_display = "Power Supply"
                else:
                    equipment_type_display = equipment_type.replace("_", " ").title()

                # Count equipment of this type for indexing
                if equipment_type not in equipment_type_counts_offline:
                    equipment_type_counts_offline[equipment_type] = 0
                equipment_type_counts_offline[equipment_type] += 1
                equipment_index = equipment_type_counts_offline[equipment_type]

                # Friendly name format: "DMM-1", "Oscilloscope-1", etc.
                friendly_name = f"{equipment_type_display}-{equipment_index}"

                # Clean friendly name for Mermaid
                clean_friendly_name = (
                    friendly_name.replace('"', "'").replace("\n", " ").replace("\r", " ")
                )

                icon = get_icon(device_type)
                # Show equipment type and IP
                node_label = f'"{icon} {clean_friendly_name}<br/>{equipment_type_display}<br/>{ip}<br/>❌ OFFLINE"'

                node_id = f"D_{device_id.replace('-', '_').replace('.', '_').replace('/', '_')}"
                device_nodes[node_id] = {"type": device_type, "device_id": device_id}
                device_id_to_node_id[device_id] = node_id

                # Check for power switch relationship (same logic as online devices)
                power_switch = device.get("power_switch")
                power_switch_id = None
                if power_switch:
                    if isinstance(power_switch, dict):
                        power_switch_id = power_switch.get("device_id")
                    else:
                        power_switch_id = power_switch

                if power_switch_id:
                    if power_switch_id in device_id_to_node_id:
                        tasmota_node_id = device_id_to_node_id[power_switch_id]
                        if tasmota_node_id in tasmota_nodes:
                            power_connections.append((tasmota_node_id, node_id))
                    elif power_switch_id in devices_config:
                        switch_info = devices_config[power_switch_id]
                        tasmota_ip = switch_info.get("ip", "")
                        if tasmota_ip:
                            switch_network_base = ".".join(tasmota_ip.split(".")[:3])
                            if switch_network_base == target_network_base:
                                tasmota_name = switch_info.get("friendly_name") or switch_info.get(
                                    "name", power_switch_id
                                )
                                if tasmota_node_id not in tasmota_nodes:
                                    tasmota_clean_name = (
                                        tasmota_name.replace('"', "'")
                                        .replace("\n", " ")
                                        .replace("\r", " ")
                                    )
                                    if len(tasmota_clean_name) > 20:
                                        tasmota_clean_name = tasmota_clean_name[:17] + "..."
                                    tasmota_label = f'"🔌 {tasmota_clean_name}<br/>{tasmota_ip}"'
                                    tasmota_nodes[tasmota_node_id] = {
                                        "label": tasmota_label,
                                        "device_id": power_switch_id,
                                    }
                                    device_id_to_node_id[power_switch_id] = tasmota_node_id
                                    lines.append(
                                        f"            {tasmota_node_id}({tasmota_label}):::tasmota_device"
                                    )
                                power_connections.append((tasmota_node_id, node_id))

                lines.append(f"            {node_id}({node_label}):::offline")

            lines.append("        end")
            # Reopen Devices subgraph for regular offline devices
            lines.append('        subgraph DevicesOffline["📱 Devices (Offline)"]')

        # Process regular offline devices
        for device_id, device in regular_devices_offline:
            device_type = device.get("type", "other")
            friendly_name = device.get("friendly_name") or device.get("name", device_id)
            hostname = device.get("hostname") or friendly_name
            ip = device.get("ip", "")

            # Use full hostname, don't truncate
            clean_hostname = hostname.replace('"', "'").replace("\n", " ").replace("\r", " ")

            icon = get_icon(device_type)
            node_label = f'"{icon} {clean_hostname}<br/>{ip}<br/>❌ OFFLINE"'

            node_id = f"D_{device_id.replace('-', '_').replace('.', '_').replace('/', '_')}"
            device_nodes[node_id] = {"type": device_type, "device_id": device_id}
            device_id_to_node_id[device_id] = node_id

            # Check for power switch relationship (same logic as online devices)
            power_switch = device.get("power_switch")
            power_switch_id = None
            if power_switch:
                if isinstance(power_switch, dict):
                    power_switch_id = power_switch.get("device_id")
                else:
                    power_switch_id = power_switch

            if power_switch_id:
                if power_switch_id in device_id_to_node_id:
                    tasmota_node_id = device_id_to_node_id[power_switch_id]
                    if tasmota_node_id in tasmota_nodes:
                        power_connections.append((tasmota_node_id, node_id))
                elif power_switch_id in devices_config:
                    switch_info = devices_config[power_switch_id]
                    tasmota_ip = switch_info.get("ip", "")
                    if tasmota_ip:
                        switch_network_base = ".".join(tasmota_ip.split(".")[:3])
                        if switch_network_base == target_network_base:
                            tasmota_name = switch_info.get("friendly_name") or switch_info.get(
                                "name", power_switch_id
                            )
                            if tasmota_node_id not in tasmota_nodes:
                                tasmota_clean_name = (
                                    tasmota_name.replace('"', "'")
                                    .replace("\n", " ")
                                    .replace("\r", " ")
                                )
                                if len(tasmota_clean_name) > 20:
                                    tasmota_clean_name = tasmota_clean_name[:17] + "..."
                                tasmota_label = f'"🔌 {tasmota_clean_name}<br/>{tasmota_ip}"'
                                tasmota_nodes[tasmota_node_id] = {
                                    "label": tasmota_label,
                                    "device_id": power_switch_id,
                                }
                                device_id_to_node_id[power_switch_id] = tasmota_node_id
                                lines.append(
                                    f"            {tasmota_node_id}({tasmota_label}):::tasmota_device"
                                )
                            power_connections.append((tasmota_node_id, node_id))

            lines.append(f"            {node_id}({node_label}):::offline")

        if len(offline_devices) > 15:
            lines.append(
                f'            OfflineMore("... and {len(offline_devices) - 15} more offline"):::offline'
            )

        lines.append("        end")

        # Add power connections with better styling
        for tasmota_id, device_id in power_connections:
            # Check if device is offline by looking up its status
            device_status = "online"  # default
            device_lookup_id = device_nodes[device_id]["device_id"]
            if device_lookup_id in configured_devices:
                device_status = configured_devices[device_lookup_id].get("status", "offline")

            # Use solid line for online, dashed for offline
            # Use thicker, colored lines for power connections
            # Connect from PowerSwitches subgraph to Devices subgraph
            if device_status == "offline":
                lines.append(f'        {tasmota_id} -.->|"⚡ Powers"| {device_id}')
            else:
                lines.append(f'        {tasmota_id} ==>|"⚡ Powers"| {device_id}')

        lines.append("    end")

        # Add legend/key
        lines.append("")
        lines.append('    subgraph Legend["📋 Legend"]')
        lines.append('        L1("💻 Development Boards"):::development_board')
        lines.append('        L2("🔬 Test Equipment"):::test_equipment')
        lines.append('        L3("🔌 Tasmota Power Switches"):::tasmota_device')
        lines.append('        L4("🖥️ Servers"):::server')
        lines.append('        L5("🌐 Network Infrastructure"):::network_infrastructure')
        lines.append('        L6("⚙️ Embedded Controllers"):::embedded_controllers')
        lines.append('        L7("📱 Other Devices"):::other')
        lines.append('        L8("🟢 Online Devices"):::online')
        lines.append('        L9("❌ Offline Devices"):::offline')
        lines.append('        L10("⚡ Power Connection"):::power_line')
        lines.append("    end")

        # Add styling with better colors
        lines.append("")
        lines.append(
            "    classDef development_board fill:#87CEEB,stroke:#4682B4,stroke-width:3px,color:#000"
        )
        lines.append(
            "    classDef test_equipment fill:#FFB6C1,stroke:#FF69B4,stroke-width:3px,color:#000"
        )
        lines.append(
            "    classDef tasmota_device fill:#DDA0DD,stroke:#9370DB,stroke-width:4px,color:#000"
        )
        lines.append("    classDef server fill:#90EE90,stroke:#228B22,stroke-width:3px,color:#000")
        lines.append(
            "    classDef network_infrastructure fill:#FFD700,stroke:#FFA500,stroke-width:3px,color:#000"
        )
        lines.append(
            "    classDef embedded_controllers fill:#FFA07A,stroke:#FF6347,stroke-width:3px,color:#000"
        )
        lines.append("    classDef other fill:#D3D3D3,stroke:#808080,stroke-width:2px,color:#000")
        lines.append("    classDef online fill:#90EE90,stroke:#228B22,stroke-width:3px,color:#000")
        lines.append(
            "    classDef offline fill:#FFB6B6,stroke:#FF0000,stroke-width:2px,stroke-dasharray: 5 5,color:#000"
        )
        lines.append("    classDef power_line stroke:#FFD700,stroke-width:4px")
        
        # Add latency-based performance metric classes (if show_metrics enabled)
        if show_metrics:
            lines.append("    classDef latency_excellent fill:#90EE90,stroke:#228B22,stroke-width:3px,color:#000")
            lines.append("    classDef latency_good fill:#FFD700,stroke:#FFA500,stroke-width:3px,color:#000")
            lines.append("    classDef latency_fair fill:#FFA07A,stroke:#FF6347,stroke-width:3px,color:#000")
            lines.append("    classDef latency_poor fill:#FF6B6B,stroke:#CC0000,stroke-width:3px,color:#FFF")
        
        # Add alert device class (if show_alerts enabled)
        if show_alerts:
            lines.append("    classDef alert_device fill:#FFB6B6,stroke:#FF0000,stroke-width:4px,color:#000")

        # Add link styling for power connections (thicker, golden color)
        lines.append("    linkStyle default stroke:#FFD700,stroke-width:3px")

        lines.append("```")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error generating Mermaid diagram: {e}", exc_info=True)
        return f'```mermaid\ngraph TD\n    Error["❌ Error generating diagram: {e!s}"]\n```'


def convert_mermaid_to_png(
    mermaid_diagram: str, output_path: Optional[Path] = None
) -> Optional[str]:
    """
    Convert a Mermaid diagram to PNG image.

    Args:
        mermaid_diagram: Mermaid diagram text (with or without ```mermaid code blocks)
        output_path: Optional path to save the image. If None, returns base64 encoded image.

    Returns:
        Base64 encoded image string if output_path is None, otherwise None
    """
    import tempfile

    # Extract mermaid content if wrapped in code blocks
    mermaid_content = mermaid_diagram
    if mermaid_diagram.startswith("```mermaid"):
        # Remove code block markers
        lines = mermaid_diagram.split("\n")
        mermaid_content = (
            "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        )
    elif mermaid_diagram.startswith("```"):
        # Generic code block
        lines = mermaid_diagram.split("\n")
        mermaid_content = (
            "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        )

    # Try to use mermaid-cli (mmdc) if available
    try:
        # Check if mmdc is available
        result = subprocess.run(
            ["which", "mmdc"],
            check=False,
            capture_output=True,
            timeout=2,
        )
        if result.returncode != 0:
            # Try npm mermaid-cli
            result = subprocess.run(
                ["which", "mermaid"],
                check=False,
                capture_output=True,
                timeout=2,
            )
            if result.returncode != 0:
                logger.debug("mermaid-cli not found, skipping Mermaid-to-PNG conversion")
                return None

        # Use mmdc to convert Mermaid to PNG
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as mermaid_file:
            mermaid_file.write(mermaid_content)
            mermaid_file_path = mermaid_file.name

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as png_file:
            png_file_path = png_file.name

        try:
            # Try mmdc first with higher resolution for better detail visibility
            # Use width of 2400px (2x default) for better zoom/clarity
            # Use white background instead of transparent
            cmd = [
                "mmdc",
                "-i",
                mermaid_file_path,
                "-o",
                png_file_path,
                "-b",
                "white",
                "-w",
                "2400",
            ]
            result = subprocess.run(cmd, check=False, capture_output=True, timeout=30)

            if result.returncode != 0:
                # Try mermaid command
                cmd = [
                    "mermaid",
                    mermaid_file_path,
                    "-o",
                    str(Path(png_file_path).parent),
                    "-f",
                    "png",
                ]
                result = subprocess.run(cmd, check=False, capture_output=True, timeout=30)

            if result.returncode == 0 and Path(png_file_path).exists():
                # Read PNG and convert to base64
                with open(png_file_path, "rb") as f:
                    png_data = f.read()

                if output_path:
                    Path(output_path).write_bytes(png_data)
                    return None
                return base64.b64encode(png_data).decode("utf-8")
            logger.warning(f"mermaid-cli conversion failed: {result.stderr.decode()}")
            return None
        finally:
            # Cleanup temp files
            try:
                Path(mermaid_file_path).unlink(missing_ok=True)
                Path(png_file_path).unlink(missing_ok=True)
            except Exception:
                pass

    except FileNotFoundError:
        logger.debug("mermaid-cli not found, skipping Mermaid-to-PNG conversion")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("mermaid-cli conversion timed out")
        return None
    except Exception as e:
        logger.warning(f"Failed to convert Mermaid to PNG: {e}")
        return None


def generate_network_map_image(
    network_map: Dict[str, Any], output_path: Optional[Path] = None
) -> Optional[str]:
    """
    Generate a visual network topology diagram as an image.

    Args:
        network_map: Network map dictionary from create_network_map
        output_path: Optional path to save the image. If None, returns base64 encoded image.

    Returns:
        Base64 encoded image string if output_path is None, otherwise None
    """
    if not HAS_MATPLOTLIB:
        logger.error("matplotlib not available - cannot generate image")
        return None

    if "error" in network_map:
        logger.error(f"Cannot generate image: {network_map['error']}")
        return None

    try:
        # Larger figure size for better readability in chat
        fig, ax = plt.subplots(figsize=(24, 16))
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis("off")

        # Get target network for prioritization (import at top of function)
        from lab_testing.config import get_target_network

        target_network = get_target_network()

        # Title - larger font
        summary = network_map.get("summary", {})
        title = f"Lab Network Topology - {target_network}\n{summary.get('online_devices', 0)} Online / {summary.get('total_configured_devices', 0)} Total Devices"
        ax.text(50, 97, title, ha="center", va="top", fontsize=24, fontweight="bold")

        # Group devices by network - ONLY show target network
        # Also track power switch relationships
        devices_by_network = {}
        target_network_devices = {"online": [], "offline": []}
        power_connections = {}  # device_id -> power_switch_info

        # Load full config to get power switch relationships
        import json

        from lab_testing.config import get_lab_devices_config

        config_path = get_lab_devices_config()
        full_config = {}
        if config_path.exists():
            with open(config_path) as f:
                full_config = json.load(f)

        for device_id, device in network_map.get("configured_devices", {}).items():
            ip = device.get("ip", "")
            if ip:
                network = ".".join(ip.split(".")[:3]) + ".0/24"

                # Only include devices on target network
                if network == target_network:
                    status = device.get("status", "offline")
                    target_network_devices[status].append(device)

                    # Check for power switch relationship
                    power_switch = device.get("power_switch")
                    if power_switch:
                        # Get power switch device info from full config
                        devices = full_config.get("devices", {})
                        if power_switch in devices:
                            switch_info = devices[power_switch]
                            switch_ip = switch_info.get("ip", "")
                            # Only track if power switch is also on target network
                            if switch_ip:
                                switch_network = ".".join(switch_ip.split(".")[:3]) + ".0/24"
                                if switch_network == target_network:
                                    power_connections[device_id] = {
                                        "power_switch_id": power_switch,
                                        "power_switch_name": switch_info.get("friendly_name")
                                        or switch_info.get("name", power_switch),
                                        "power_switch_ip": switch_ip,
                                        "device_id": device_id,
                                        "device_name": device.get("friendly_name")
                                        or device.get("name", device_id),
                                        "device_ip": ip,
                                    }

        # Only add target network if it has devices
        if target_network_devices["online"] or target_network_devices["offline"]:
            devices_by_network = {target_network: target_network_devices}

        # Add Tasmota devices that are power switches (even if not in configured_devices)
        tasmota_devices = {}
        if full_config:
            devices = full_config.get("devices", {})
            for device_id, device_info in devices.items():
                if device_info.get("device_type") == "tasmota_device":
                    ip = device_info.get("ip", "")
                    if ip:
                        network = ".".join(ip.split(".")[:3]) + ".0/24"
                        if network == target_network:
                            # Check if this Tasmota device is used as a power switch
                            is_power_switch = any(
                                conn["power_switch_id"] == device_id
                                for conn in power_connections.values()
                            )
                            if is_power_switch:
                                status = (
                                    "online"
                                    if any(
                                        d.get("ip") == ip and d.get("status") == "online"
                                        for d in target_network_devices["online"]
                                    )
                                    else "offline"
                                )
                                tasmota_devices[device_id] = {
                                    "device_id": device_id,
                                    "friendly_name": device_info.get("friendly_name")
                                    or device_info.get("name", device_id),
                                    "name": device_info.get("name", "Unknown"),
                                    "ip": ip,
                                    "type": "tasmota_device",
                                    "status": status,
                                    "is_power_switch": True,
                                }
                                # Add to appropriate list
                                if status == "online":
                                    target_network_devices["online"].append(
                                        tasmota_devices[device_id]
                                    )
                                else:
                                    target_network_devices["offline"].append(
                                        tasmota_devices[device_id]
                                    )

        # Add unknown hosts - only from target network
        for host in network_map.get("unknown_hosts", []):
            ip = host.get("ip", "")
            if ip:
                network = ".".join(ip.split(".")[:3]) + ".0/24"
                if network == target_network:
                    # Add to target network
                    if target_network not in devices_by_network:
                        devices_by_network[target_network] = {"online": [], "offline": []}
                    devices_by_network[target_network]["online"].append(
                        {"name": f"Unknown: {ip}", "ip": ip, "type": "unknown"}
                    )

        # Color scheme
        colors = {
            "development_boards": "#4A90E2",  # Blue
            "test_equipment": "#E24A4A",  # Red
            "network_infrastructure": "#50C878",  # Green
            "embedded_controllers": "#FFA500",  # Orange
            "tasmota_device": "#9B59B6",  # Purple
            "other": "#95A5A6",  # Gray
            "unknown": "#F39C12",  # Yellow
        }

        # Helper function to create clean, readable device names
        def clean_device_name(name, max_chars=20):
            """Create a clean, readable device name that fits in boxes"""
            # Remove common suffixes that make names too long
            name = name.replace(".localdomain", "")
            name = name.replace("localdomain", "")

            # If still too long, try to extract meaningful part
            if len(name) > max_chars:
                # Try to get the first meaningful part before hyphens/underscores
                parts = name.replace("_", "-").split("-")
                if len(parts) > 1:
                    # Use first 2-3 meaningful parts
                    meaningful = [p for p in parts[:3] if len(p) > 2]
                    if meaningful:
                        name = "-".join(meaningful)

                # If still too long, truncate intelligently
                if len(name) > max_chars:
                    # Try to keep first part and last part
                    if "-" in name or "_" in name:
                        first = name.split("-")[0] if "-" in name else name.split("_")[0]
                        last = name.split("-")[-1] if "-" in name else name.split("_")[-1]
                        if len(first) + len(last) + 1 <= max_chars:
                            name = f"{first}-{last}"
                        else:
                            name = name[: max_chars - 3] + "..."
                    else:
                        name = name[: max_chars - 3] + "..."

            return name

        # Helper function to get short display name
        def get_display_name(device):
            """Get the best display name for a device"""
            name = device.get("friendly_name") or device.get("name", "Unknown")
            # Prefer shorter names, fallback to IP if name is too long
            if len(name) > 30:
                ip = device.get("ip", "")
                # Try to use a meaningful part of the name
                short_name = clean_device_name(name, max_chars=18)
                return short_name
            return clean_device_name(name, max_chars=18)

        # Draw networks - optimized for single target network
        y_start = 90
        # Use more vertical space since we only have one network
        network_height = 80

        # Only show target network
        sorted_networks = list(devices_by_network.items())

        # Track device positions for drawing connections (shared across network)
        device_positions = {}  # device_id -> (x, y)

        for idx, (network, devices) in enumerate(sorted_networks):
            y_pos = y_start

            # Network label - target network styling (larger)
            label_text = f"{network} (TARGET)"
            ax.text(
                5,
                y_pos,
                label_text,
                ha="left",
                va="top",
                fontsize=18,
                fontweight="bold",
                bbox=dict(
                    boxstyle="round,pad=0.6",
                    facecolor="lightgreen",
                    alpha=0.7,
                    edgecolor="darkgreen",
                    linewidth=3,
                ),
            )

            # Draw devices in a grid layout - larger boxes for better readability
            x_start = 5
            y_device = y_pos - 6
            device_width = 14  # Much wider for better text display
            device_height = 6  # Much taller
            devices_per_row = 6  # Fewer devices per row for larger boxes
            row_spacing = 7  # More spacing between rows

            # Online devices
            online_devices = devices.get("online", [])
            row = 0
            col = 0
            for device in online_devices[:30]:  # Limit to 30 online devices per network
                device_type = device.get("type", "other")
                color = colors.get(device_type, colors["other"])
                ip = device.get("ip", "")
                device_id = device.get("device_id", "")

                # Get clean, readable display name
                display_name = get_display_name(device)

                x_pos = x_start + (col * (device_width + 1))
                y_current = y_device - (row * row_spacing)

                # Store position for connection drawing
                if device_id:
                    device_positions[device_id] = (
                        x_pos + device_width / 2,
                        y_current - device_height / 2,
                    )

                # Draw device box with better styling
                # Tasmota devices get special border
                is_tasmota = device_type == "tasmota_device"
                edge_color = "#7D3C98" if is_tasmota else "black"
                edge_width = 2 if is_tasmota else 1.5

                box = FancyBboxPatch(
                    (x_pos, y_current - device_height),
                    device_width,
                    device_height,
                    boxstyle="round,pad=0.3",
                    facecolor=color,
                    edgecolor=edge_color,
                    alpha=0.85,
                    linewidth=edge_width,
                )
                ax.add_patch(box)

                # Device name - single line, centered, bold (larger font)
                # Add power switch indicator for Tasmota
                if is_tasmota:
                    display_name = f"⚡ {display_name}"
                ax.text(
                    x_pos + device_width / 2,
                    y_current - 1.8,
                    display_name,
                    ha="center",
                    va="center",
                    fontsize=12,
                    fontweight="bold",
                    color="white",
                    wrap=False,
                )

                # IP address (larger, below name, italic)
                ax.text(
                    x_pos + device_width / 2,
                    y_current - 3.8,
                    ip,
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="white",
                    style="italic",
                )

                # Status indicator (green circle for online - larger)
                circle = Circle(
                    (x_pos + 1.2, y_current - 2),
                    0.6,
                    facecolor="#2ECC71",
                    edgecolor="white",
                    linewidth=1.5,
                    zorder=10,
                )
                ax.add_patch(circle)

                col += 1
                if col >= devices_per_row:
                    col = 0
                    row += 1

            # Offline devices (smaller, in separate section)
            offline_devices = devices.get("offline", [])
            if offline_devices:
                # Calculate y_offline position - use y_device if no online devices
                if online_devices:
                    y_offline = y_current - row_spacing - 2
                else:
                    y_offline = y_device - 2
                ax.text(
                    x_start,
                    y_offline + 1,
                    f"Offline ({len(offline_devices)}):",
                    ha="left",
                    va="top",
                    fontsize=14,
                    style="italic",
                    alpha=0.7,
                    fontweight="bold",
                )

                row = 0
                col = 0
                device_width_offline = 11  # Larger offline boxes
                device_height_offline = 4  # Taller offline boxes
                devices_per_row_offline = 6  # Fewer per row for larger boxes

                for device in offline_devices[:40]:  # Limit offline devices
                    device_type = device.get("type", "other")
                    color = colors.get(device_type, colors["other"])
                    ip = device.get("ip", "")
                    device_id = device.get("device_id", "")

                    # Get clean, readable display name
                    display_name = get_display_name(device)
                    # Shorter for offline devices
                    if len(display_name) > 12:
                        display_name = clean_device_name(display_name, max_chars=12)

                    x_pos = x_start + (col * (device_width_offline + 0.8))
                    y_current_offline = y_offline - (row * 3.5)

                    # Store position for connection drawing (offline devices too)
                    if device_id:
                        device_positions[device_id] = (
                            x_pos + device_width_offline / 2,
                            y_current_offline - device_height_offline / 2,
                        )

                    # Draw smaller, grayed out box
                    # Tasmota devices get special border even when offline
                    is_tasmota = device_type == "tasmota_device"
                    edge_color = "#7D3C98" if is_tasmota else "gray"
                    edge_width = 1.5 if is_tasmota else 0.8

                    box = FancyBboxPatch(
                        (x_pos, y_current_offline - device_height_offline),
                        device_width_offline,
                        device_height_offline,
                        boxstyle="round,pad=0.2",
                        facecolor=color,
                        edgecolor=edge_color,
                        alpha=0.4,
                        linewidth=edge_width,
                    )
                    ax.add_patch(box)

                    # Device name - single line, centered (larger)
                    # Add power switch indicator for Tasmota
                    if is_tasmota:
                        display_name = f"⚡ {display_name}"
                    ax.text(
                        x_pos + device_width_offline / 2,
                        y_current_offline - 1.2,
                        display_name,
                        ha="center",
                        va="center",
                        fontsize=10,
                        alpha=0.9,
                        wrap=False,
                        fontweight="bold",
                    )

                    # IP address (larger, at bottom)
                    ax.text(
                        x_pos + device_width_offline / 2,
                        y_current_offline - 3,
                        ip,
                        ha="center",
                        va="center",
                        fontsize=8,
                        alpha=0.7,
                        style="italic",
                    )

                    # Red X for offline (top left corner - larger)
                    ax.text(
                        x_pos + 0.8,
                        y_current_offline - 0.8,
                        "✗",
                        ha="center",
                        va="center",
                        fontsize=12,
                        color="red",
                        fontweight="bold",
                    )

                    col += 1
                    if col >= devices_per_row_offline:
                        col = 0
                        row += 1

        # Draw power connections (lines from Tasmota devices to boards they power)
        # Draw connections after all devices are positioned
        for device_id, conn_info in power_connections.items():
            switch_id = conn_info["power_switch_id"]
            device_pos = device_positions.get(device_id)
            switch_pos = device_positions.get(switch_id)

            if device_pos and switch_pos:
                # Draw arrow from Tasmota device to powered device
                # Use curved arrow for better visibility
                arrow = FancyArrowPatch(
                    switch_pos,
                    device_pos,
                    arrowstyle="->",
                    mutation_scale=20,
                    color="#FFD700",
                    linewidth=2.5,
                    alpha=0.8,
                    zorder=5,
                    linestyle="-",
                    connectionstyle="arc3,rad=0.2",
                )
                ax.add_patch(arrow)

        # Legend - larger, positioned at bottom
        legend_y = 5
        legend_x = 5
        ax.text(legend_x, legend_y, "Device Types:", fontsize=14, fontweight="bold")
        legend_y -= 2.2

        # Show legend in two columns to save space
        legend_col1_x = legend_x
        legend_col2_x = legend_x + 25
        col1_y = legend_y
        col2_y = legend_y

        device_types = [dt for dt in colors.items() if dt[0] != "unknown"]
        mid_point = len(device_types) // 2

        for i, (device_type, color) in enumerate(device_types):
            if i < mid_point:
                x_pos = legend_col1_x
                y_pos = col1_y
                col1_y -= 1.3
            else:
                x_pos = legend_col2_x
                y_pos = col2_y
                col2_y -= 1.3

            box = FancyBboxPatch(
                (x_pos, y_pos - 0.5),
                2,
                0.8,
                boxstyle="round,pad=0.1",
                facecolor=color,
                edgecolor="black",
                alpha=0.8,
                linewidth=0.8,
            )
            ax.add_patch(box)
            ax.text(
                x_pos + 2.3,
                y_pos - 0.1,
                device_type.replace("_", " ").title(),
                ha="left",
                va="center",
                fontsize=11,
            )

        # Status indicators - larger, on the right
        status_x = 75
        status_y = 5
        ax.text(status_x, status_y, "Status:", fontsize=14, fontweight="bold")
        status_y -= 2.2

        circle_online = Circle(
            (status_x, status_y),
            0.5,
            facecolor="#2ECC71",
            edgecolor="white",
            linewidth=1.5,
            zorder=10,
        )
        ax.add_patch(circle_online)
        ax.text(status_x + 1, status_y, "Online", ha="left", va="center", fontsize=11)

        status_y -= 2
        ax.text(
            status_x,
            status_y,
            "✗",
            ha="center",
            va="center",
            fontsize=14,
            color="red",
            fontweight="bold",
        )
        ax.text(status_x + 1, status_y, "Offline", ha="left", va="center", fontsize=11)

        plt.tight_layout()

        # Save or return image
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close()
            return None
        # Return as base64 encoded string
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close()
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        buf.close()
        return img_base64

    except Exception as e:
        logger.error(f"Failed to generate network map image: {e}", exc_info=True)
        if "fig" in locals():
            plt.close()
        return None
