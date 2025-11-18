"""
Device Management Tools for MCP Server
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from lab_testing.config import CONFIG_DIR, get_lab_devices_config, get_target_network
from lab_testing.exceptions import (
    DeviceConnectionError,
    DeviceNotFoundError,
    SSHError,
)
from lab_testing.utils.credentials import get_ssh_command
from lab_testing.utils.logger import get_logger

logger = get_logger()


def _create_default_config(config_path: Path) -> Dict[str, Any]:
    """Create a default device configuration file"""
    default_config = {
        "devices": {
            "example_device": {
                "name": "Example Device",
                "ip": "192.168.1.100",
                "ports": {"ssh": 22, "http": 80, "https": 443},
                "device_type": "example",
                "description": "Template entry - replace with actual lab devices",
                "status": "template",
                "last_tested": None,
            }
        },
        "lab_infrastructure": {
            "primary_access": {
                "method": "wireguard_vpn",
                "description": "WireGuard VPN - Primary method for lab access",
                "status": "active",
            },
            "network_access": {
                "target_network": "192.168.2.0/24",
                "friendly_name": "Hardware Lab",
                "lab_networks": ["192.168.2.0/24"],
                "primary_method": "wireguard_vpn",
            },
        },
        "device_categories": {
            "development_boards": [],
            "test_equipment": [],
            "network_infrastructure": [],
            "embedded_controllers": [],
            "sensors": [],
            "other": [],
            "tasmota_devices": [],
        },
    }

    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write default config
    with open(config_path, "w") as f:
        json.dump(default_config, f, indent=2)

    logger.info(f"Created default device configuration at {config_path}")
    return default_config


def load_device_config() -> Dict[str, Any]:
    """Load device configuration from JSON file, creating it if it doesn't exist"""
    config_path = get_lab_devices_config()
    try:
        with open(config_path) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info(f"Device configuration not found at {config_path}, creating default")
        return _create_default_config(config_path)
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parsing device configuration: {e}")


def _get_ssh_status(device: Dict[str, Any]) -> str:
    """
    Determine SSH status for a device.

    Args:
        device: Device dictionary

    Returns:
        SSH status string: "ok", "error", "refused", or "unknown"
    """
    if device.get("hostname"):
        return "ok"
    ssh_error = device.get("ssh_error", "")
    ssh_error_type = device.get("ssh_error_type", "")
    if ssh_error:
        if "refused" in ssh_error.lower() or ssh_error_type == "refused":
            return "refused"
        if ssh_error_type == "timeout":
            return "timeout"
        return "error"
    return "unknown"


def list_devices(
    device_type_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    show_summary: bool = True,
    force_refresh: bool = False,
    ssh_status_filter: Optional[str] = None,
    power_state_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    List devices actually on the target network by scanning it.
    Uses cached device information when available, and updates cache for new discoveries.
    Excludes example/template devices and only shows devices that are online.
    Optimized for speed with parallel SSH identification.

    Args:
        device_type_filter: Filter by device type (e.g., "tasmota_device", "eink_board", "test_equipment")
        status_filter: Filter by status (e.g., "online", "offline", "discovered")
        search_query: Search by IP, hostname, friendly name, or device ID (case-insensitive)
        show_summary: Include summary statistics (default: True)
        force_refresh: If True, bypass cache and rescan all devices (default: False)
        ssh_status_filter: Filter by SSH status (e.g., "ok", "error", "refused", "unknown")
        power_state_filter: Filter Tasmota devices by power state (e.g., "on", "off")
        sort_by: Sort results by field (e.g., "ip", "friendly_name", "status", "last_seen") (default: type then friendly_name)
        sort_order: Sort order - "asc" or "desc" (default: "asc")
        limit: Maximum number of devices to return (default: None, no limit)

    Returns:
        Dictionary containing device list and summary information
    """
    import ipaddress
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from lab_testing.tools.network_mapper import _get_device_info_from_config, _scan_network_range
    from lab_testing.tools.vpn_manager import get_vpn_status
    from lab_testing.utils.device_cache import get_cached_device_info, identify_and_cache_device

    # Get target network
    target_network = get_target_network()

    # Check VPN status to determine if devices are discovered via VPN
    vpn_status = get_vpn_status()
    vpn_connected = vpn_status.get("connected", False)

    logger.info(
        f"Scanning target network {target_network} for devices (VPN: {'connected' if vpn_connected else 'disconnected'})"
    )

    # Scan the target network for active devices
    active_hosts = _scan_network_range(target_network, max_hosts=254, timeout=0.5)
    # Ensure active_hosts is always a list (handle None case)
    if active_hosts is None:
        active_hosts = []

    # Load config to match discovered hosts with configured devices
    config = load_device_config()
    configured_devices = config.get("devices", {})

    # Separate devices into cached and uncached for parallel processing
    cached_devices = {}
    uncached_ips = []

    # Also check for Tasmota and test equipment devices
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from lab_testing.tools.device_detection import detect_tasmota_device, detect_test_equipment

    # Track IPs that need Tasmota/test equipment detection
    ips_needing_detection = []

    for host in active_hosts:
        ip = host["ip"]
        # If force_refresh is True, skip cache and treat all devices as uncached
        if force_refresh:
            uncached_ips.append(ip)
            ips_needing_detection.append(ip)
        else:
            cached_info = get_cached_device_info(ip)
            if cached_info:
                cached_devices[ip] = cached_info
                # Check if cached device needs Tasmota/test equipment detection
                # (e.g., old cache entries without detection, or devices that might have changed)
                if not cached_info.get("tasmota_detected") and not cached_info.get(
                    "test_equipment_detected"
                ):
                    ips_needing_detection.append(ip)
            else:
                uncached_ips.append(ip)
                ips_needing_detection.append(ip)

    # Quick detection of Tasmota and test equipment devices (parallel)
    # Check both uncached IPs and cached IPs that don't have detection yet
    if ips_needing_detection:

        def _detect_device_type(ip: str) -> tuple:
            """Detect device type - runs in thread pool"""
            tasmota_info = detect_tasmota_device(ip, timeout=2.0)
            if tasmota_info:
                return (ip, tasmota_info)
            test_equip_info = detect_test_equipment(ip, timeout=2.0)
            if test_equip_info:
                return (ip, test_equip_info)
            return (ip, None)

        # Detect device types in parallel (quick check)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_detect_device_type, ip): ip for ip in ips_needing_detection}
            for future in as_completed(futures):
                ip, device_type_info = future.result()
                if device_type_info:
                    # Store detected type info in memory
                    if ip not in cached_devices:
                        cached_devices[ip] = {}
                    cached_devices[ip].update(device_type_info)

                    # Save Tasmota/test equipment detection to persistent cache
                    from lab_testing.utils.device_cache import cache_device_info

                    cache_device_info(ip, device_type_info)

    # Parallel identification of uncached devices
    if uncached_ips:
        logger.debug(f"Identifying {len(uncached_ips)} uncached devices in parallel...")

        def _identify_device_with_username(ip: str, username: str) -> tuple:
            """Identify a single device with a specific username - runs in thread pool"""
            try:
                identified_info = identify_and_cache_device(ip, username=username, ssh_port=22)
                if identified_info.get("hostname") or identified_info.get("device_found"):
                    return (ip, identified_info, True)  # True = success
                return (ip, {}, False)
            except Exception as e:
                logger.debug(f"Failed to identify {ip} with username {username}: {e}")
                return (ip, {}, False)

        # Try usernames in parallel for each device (faster than sequential)
        # Prioritize "fio" first, then "root" as fallback
        # Use ThreadPoolExecutor for parallel identification (max 10 concurrent = 5 devices * 2 usernames)
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all username attempts in parallel
            futures = []
            for ip in uncached_ips:
                for username in ["fio", "root"]:  # Try fio first, then root
                    future = executor.submit(_identify_device_with_username, ip, username)
                    futures.append((future, ip))

            # Track which IPs have been successfully identified
            identified_ips = set()

            # Process results as they complete
            for future, ip in futures:
                if ip in identified_ips:
                    continue  # Skip if already identified

                try:
                    ip_result, identified_info, success = future.result(
                        timeout=6
                    )  # Max 6s per attempt
                    if success:
                        # Merge with existing cached data (preserves Tasmota/test equipment detection)
                        if ip in cached_devices:
                            cached_devices[ip].update(identified_info)
                        else:
                            cached_devices[ip] = identified_info
                        identified_ips.add(ip)
                        # Cancel remaining futures for this IP
                        for f, ip_check in futures:
                            if ip_check == ip and not f.done():
                                f.cancel()
                except Exception:
                    continue

            # For any IPs that weren't identified, add empty dict
            for ip in uncached_ips:
                if ip not in identified_ips:
                    cached_devices[ip] = {}

    # Organize discovered devices by type
    by_type = {}
    discovered_devices = []

    for host in active_hosts:
        ip = host["ip"]

        # Check if this IP matches a configured device
        config_device_info = _get_device_info_from_config(ip, config)

        # Skip example/template devices from config
        if config_device_info:
            if config_device_info.get("type") == "example":
                continue
            if config_device_info.get("status") == "template":
                continue

        # Get cached info (from parallel identification above)
        cached_info = cached_devices.get(ip, {})

        # If not in memory cache, try loading from persistent cache
        # (This can happen if Tasmota detection saved to cache but wasn't loaded initially)
        if not cached_info:
            from lab_testing.utils.device_cache import get_cached_device_info

            cached_info = get_cached_device_info(ip) or {}
            if cached_info:
                cached_devices[ip] = cached_info  # Store in memory for later use

        # Use cached/identified info
        if cached_info and cached_info.get("device_found"):
            # Use cached identification
            device_id = cached_info.get("device_id") or (
                config_device_info.get("device_id")
                if config_device_info
                else f"device_{ip.replace('.', '_')}"
            )
            friendly_name = cached_info.get("friendly_name") or (
                config_device_info.get("name")
                if config_device_info
                else cached_info.get("hostname") or f"Device at {ip}"
            )
            device_type = "other"  # Will be determined from config if available
            status = "online"
            hostname = cached_info.get("hostname")
        elif cached_info and cached_info.get("hostname"):
            # Has hostname but not fully identified
            device_id = (
                config_device_info.get("device_id")
                if config_device_info
                else f"device_{ip.replace('.', '_')}"
            )
            friendly_name = cached_info.get("hostname") or (
                config_device_info.get("name") if config_device_info else f"Device at {ip}"
            )
            device_type = "other"
            status = "discovered"
            hostname = cached_info.get("hostname")
        else:
            # Device not identified - use defaults
            device_id = (
                config_device_info.get("device_id")
                if config_device_info
                else f"device_{ip.replace('.', '_')}"
            )
            friendly_name = (
                config_device_info.get("name") if config_device_info else f"Device at {ip}"
            )
            device_type = "other"
            status = "discovered"
            hostname = None

        # Try to match device by hostname if not matched by IP
        if not config_device_info and hostname:
            # Search config for device with matching hostname
            for dev_id, dev_info in configured_devices.items():
                if dev_info.get("hostname") == hostname or dev_id == hostname:
                    config_device_info = {
                        "device_id": dev_id,
                        "name": dev_info.get("name", "Unknown"),
                        "type": dev_info.get("device_type", "other"),
                        "status": dev_info.get("status", "unknown"),
                    }
                    device_id = dev_id
                    break

        # Try to match by device_id from cache if available
        if not config_device_info and cached_info and cached_info.get("device_id"):
            cached_device_id = cached_info.get("device_id")
            if cached_device_id in configured_devices:
                dev_info = configured_devices[cached_device_id]
                config_device_info = {
                    "device_id": cached_device_id,
                    "name": dev_info.get("name", "Unknown"),
                    "type": dev_info.get("device_type", "other"),
                    "status": dev_info.get("status", "unknown"),
                }
                device_id = cached_device_id

        # Get device type and full details from config if device is configured
        if config_device_info:
            device_id = config_device_info.get("device_id", device_id)
            device_type = config_device_info.get("type", "other")
            # Fix: config uses "device_type" not "type"
            full_device_data = configured_devices.get(device_id, {})
            if full_device_data:
                device_type = full_device_data.get("device_type", device_type)
            friendly_name = (
                full_device_data.get("friendly_name")
                or full_device_data.get("name")
                or friendly_name
            )
            hostname = full_device_data.get("hostname") or hostname
            status = "online"  # Known device that's online

            # Override device type if Tasmota/test equipment detected (detection is authoritative)
            if cached_info:
                if cached_info.get("tasmota_detected"):
                    device_type = "tasmota_device"
                elif cached_info.get("test_equipment_detected"):
                    device_type = "test_equipment"
        else:
            # Use cached hostname if available
            if not hostname and cached_info:
                hostname = cached_info.get("hostname")

            # Check for detected device types (Tasmota, test equipment)
            if cached_info.get("tasmota_detected"):
                device_type = "tasmota_device"
            elif cached_info.get("test_equipment_detected"):
                device_type = "test_equipment"
            # Infer device type from hostname patterns
            elif hostname:
                hostname_lower = hostname.lower()
                if "eink" in hostname_lower:
                    device_type = "eink_board"
                elif "sentai" in hostname_lower:
                    device_type = "sentai_board"
                # Keep existing logic for other patterns
                elif any(x in hostname_lower for x in ["board", "dev", "test", "lab"]):
                    device_type = "development_board"
                elif any(x in hostname_lower for x in ["router", "switch", "gateway"]):
                    device_type = "network_device"

        if device_type not in by_type:
            by_type[device_type] = []

        # Get full device data if available
        full_device_data = configured_devices.get(device_id, {}) if config_device_info else {}

        # Get firmware version from cache/identified info
        firmware_info = None
        if cached_info:
            firmware_info = cached_info.get("firmware")

        # Get SSH error from cache if available
        ssh_error = None
        ssh_error_type = None
        if cached_info:
            ssh_error = cached_info.get("ssh_error")
            ssh_error_type = cached_info.get("ssh_error_type")

        # Get Tasmota power info from cache if available
        tasmota_power_state = None
        tasmota_power_watts = None
        if cached_info and cached_info.get("tasmota_detected"):
            tasmota_power_state = cached_info.get("tasmota_power_state")
            tasmota_power_watts = cached_info.get("tasmota_power_watts")

        # Collect all device details
        device_entry = {
            "id": device_id,
            "friendly_name": friendly_name,
            "name": (
                full_device_data.get("name", friendly_name) if full_device_data else friendly_name
            ),
            "hostname": hostname or full_device_data.get("hostname"),
            "ip": ip,
            "status": status,
            "latency_ms": host.get("latency_ms"),
            "last_tested": full_device_data.get("last_tested") if full_device_data else None,
            "firmware": firmware_info,
            "discovered_via_vpn": vpn_connected,  # Mark if discovered via VPN
            "ssh_error": ssh_error,  # SSH connection error if any
            "ssh_error_type": ssh_error_type,  # Type of SSH error
            "tasmota_power_state": tasmota_power_state,  # Tasmota power state (on/off)
            "tasmota_power_watts": tasmota_power_watts,  # Tasmota power consumption in Watts
        }

        # Add additional device details from config if available
        if full_device_data:
            device_entry.update(
                {
                    "device_type": full_device_data.get("device_type", device_type),
                    "description": full_device_data.get("description"),
                    "model": full_device_data.get("model"),
                    "manufacturer": full_device_data.get("manufacturer"),
                    "serial_number": full_device_data.get("serial_number"),
                    "ports": full_device_data.get("ports", {}),
                    "ssh_user": full_device_data.get("ssh_user"),
                    "equipment_type": full_device_data.get("equipment_type"),  # For test equipment
                }
            )
            # Use friendly_name from config if available
            if full_device_data.get("friendly_name"):
                device_entry["friendly_name"] = full_device_data.get("friendly_name")
        else:
            device_entry["device_type"] = device_type
            # For test equipment, get equipment_type from cache if available
            if device_type == "test_equipment" and cached_info:
                device_entry["equipment_type"] = cached_info.get("equipment_type")
            # If we have hostname from cache but device not in config, use hostname as friendly name
            if hostname and hostname != f"Device at {ip}":
                device_entry["friendly_name"] = hostname

        # Add power switch relationship if device is powered by a Tasmota switch
        if full_device_data:
            power_switch_id = full_device_data.get("power_switch")
            if power_switch_id and power_switch_id in configured_devices:
                switch_info = configured_devices[power_switch_id]
                device_entry["power_switch"] = {
                    "device_id": power_switch_id,
                    "friendly_name": switch_info.get("friendly_name")
                    or switch_info.get("name", power_switch_id),
                    "ip": switch_info.get("ip"),
                }

        # Add cache age/last seen timestamp
        if cached_info:
            cached_at = cached_info.get("cached_at")
            if cached_at:
                import time

                cache_age_seconds = time.time() - cached_at
                device_entry["cache_age_seconds"] = cache_age_seconds
                if cache_age_seconds < 60:
                    device_entry["last_seen"] = f"{int(cache_age_seconds)}s ago"
                elif cache_age_seconds < 3600:
                    device_entry["last_seen"] = f"{int(cache_age_seconds / 60)}m ago"
                elif cache_age_seconds < 86400:
                    device_entry["last_seen"] = f"{int(cache_age_seconds / 3600)}h ago"
                else:
                    device_entry["last_seen"] = f"{int(cache_age_seconds / 86400)}d ago"
            else:
                device_entry["last_seen"] = "Unknown"

        by_type[device_type].append(device_entry)
        discovered_devices.append(ip)

    # Assign indexed friendly names for devices without explicit friendly names
    # Only assign if device doesn't have a friendly_name from config
    for device_type, device_list in by_type.items():
        if device_type in ["tasmota_device", "eink_board", "sentai_board"]:
            # Sort devices by IP for consistent ordering
            device_list.sort(key=lambda d: d.get("ip", ""))

            # Assign indexed friendly names
            for index, device in enumerate(device_list, start=1):
                # Only assign if no friendly_name from config or if it's a generic name
                current_friendly = device.get("friendly_name", "")

                # Check if it's a generic name that should be replaced
                # Generic names: empty, "Device at IP", or hostname-based names without type indicator
                is_generic = (
                    not current_friendly
                    or current_friendly.startswith("Device at ")
                    or (
                        device_type == "tasmota_device"
                        and "Tasmota" not in current_friendly
                        and not current_friendly.startswith("IoT")
                    )
                    or (
                        device_type == "eink_board"
                        and "E-ink" not in current_friendly
                        and "eink" not in current_friendly.lower()
                        and not any(x in current_friendly.lower() for x in ["board", "jaguar"])
                    )
                    or (
                        device_type == "sentai_board"
                        and "Sentai" not in current_friendly
                        and "sentai" not in current_friendly.lower()
                        and not any(x in current_friendly.lower() for x in ["board", "jaguar"])
                    )
                )

                # Don't override if device has a configured friendly_name (unless it's generic)
                if is_generic:
                    if device_type == "tasmota_device":
                        device["friendly_name"] = f"tasmota-device-{index}"
                    elif device_type == "eink_board":
                        device["friendly_name"] = f"eink-board-{index}"
                    elif device_type == "sentai_board":
                        device["friendly_name"] = f"sentai-board-{index}"

    # Apply filters
    filtered_devices_by_type = {}
    for device_type, device_list in by_type.items():
        filtered_list = device_list

        # Filter by device type
        if device_type_filter:
            if device_type != device_type_filter:
                continue

        # Filter by status
        if status_filter:
            filtered_list = [d for d in filtered_list if d.get("status") == status_filter]

        # Filter by search query
        if search_query:
            search_lower = search_query.lower()
            filtered_list = [
                d
                for d in filtered_list
                if (
                    search_lower in (d.get("ip", "") or "").lower()
                    or search_lower in (d.get("hostname", "") or "").lower()
                    or search_lower in (d.get("friendly_name", "") or "").lower()
                    or search_lower in (d.get("device_id", "") or "").lower()
                    or search_lower in (d.get("id", "") or "").lower()
                )
            ]

        # Filter by SSH status
        if ssh_status_filter:
            ssh_status_filter_lower = ssh_status_filter.lower()
            filtered_list = [
                d for d in filtered_list if _get_ssh_status(d).lower() == ssh_status_filter_lower
            ]

        # Filter by power state (for Tasmota devices)
        if power_state_filter:
            power_state_filter_lower = power_state_filter.lower()
            filtered_list = [
                d
                for d in filtered_list
                if d.get("tasmota_power_state", "").lower() == power_state_filter_lower
            ]

        if filtered_list:
            filtered_devices_by_type[device_type] = filtered_list

    # Calculate summary statistics
    summary_stats = {}
    if show_summary:
        # Count by type
        type_counts = {}
        for device_type, device_list in filtered_devices_by_type.items():
            type_counts[device_type] = len(device_list)

        # Count by status
        status_counts = {}
        for device_type, device_list in filtered_devices_by_type.items():
            for device in device_list:
                status = device.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

        # Count by SSH status
        ssh_status_counts = {}
        for device_type, device_list in filtered_devices_by_type.items():
            for device in device_list:
                ssh_status = _get_ssh_status(device)
                ssh_status_counts[ssh_status] = ssh_status_counts.get(ssh_status, 0) + 1

        summary_stats = {
            "by_type": type_counts,
            "by_status": status_counts,
            "by_ssh_status": ssh_status_counts,
            "total": sum(len(devices) for devices in filtered_devices_by_type.values()),
        }

    # Apply sorting if requested
    if sort_by:
        import ipaddress

        def _get_sort_key(device: Dict[str, Any]) -> Any:
            """Get sort key for a device based on sort_by field"""
            if sort_by == "ip":
                # Sort IPs numerically
                try:
                    return ipaddress.IPv4Address(device.get("ip", "0.0.0.0"))
                except:
                    return device.get("ip", "")
            elif sort_by == "friendly_name":
                return (device.get("friendly_name") or device.get("name", "")).lower()
            elif sort_by == "status":
                return device.get("status", "unknown")
            elif sort_by == "last_seen":
                # Extract numeric value from "Xs ago", "Xm ago", "Xh ago", "Xd ago", or "Unknown"
                last_seen = device.get("last_seen", "Unknown")
                if last_seen == "Unknown":
                    return float("inf")  # Put Unknown at the end
                try:
                    # Parse "Xs ago", "Xm ago", etc.
                    if last_seen.endswith("s ago"):
                        return int(last_seen.replace("s ago", ""))
                    if last_seen.endswith("m ago"):
                        return int(last_seen.replace("m ago", "")) * 60
                    if last_seen.endswith("h ago"):
                        return int(last_seen.replace("h ago", "")) * 3600
                    if last_seen.endswith("d ago"):
                        return int(last_seen.replace("d ago", "")) * 86400
                except:
                    return float("inf")
                return float("inf")
            else:
                # Default: sort by IP
                try:
                    return ipaddress.IPv4Address(device.get("ip", "0.0.0.0"))
                except:
                    return device.get("ip", "")

        # Sort each device list
        for device_type, device_list in filtered_devices_by_type.items():
            reverse = sort_order.lower() == "desc"
            # Special handling for last_seen - reverse makes sense (newest first)
            if sort_by == "last_seen" and reverse:
                # For last_seen desc, we want smallest numbers first (most recent)
                filtered_devices_by_type[device_type] = sorted(
                    device_list, key=_get_sort_key, reverse=False
                )
            else:
                filtered_devices_by_type[device_type] = sorted(
                    device_list, key=_get_sort_key, reverse=reverse
                )

    # Apply limit if requested
    if limit and limit > 0:
        # Flatten all devices, apply limit, then regroup
        all_devices_flat = []
        for device_type, device_list in filtered_devices_by_type.items():
            for device in device_list:
                device["_type"] = device_type
                all_devices_flat.append(device)

        # Apply limit
        all_devices_flat = all_devices_flat[:limit]

        # Regroup by type
        filtered_devices_by_type = {}
        for device in all_devices_flat:
            device_type = device.pop("_type")
            if device_type not in filtered_devices_by_type:
                filtered_devices_by_type[device_type] = []
            filtered_devices_by_type[device_type].append(device)

    # Get infrastructure info
    infrastructure = config.get("lab_infrastructure", {})

    return {
        "success": True,
        "total_devices": sum(len(devices) for devices in filtered_devices_by_type.values()),
        "devices_by_type": filtered_devices_by_type,
        "target_network": target_network,
        "vpn_connected": vpn_connected,
        "lab_networks": infrastructure.get("network_access", {}).get("lab_networks", []),
        "summary": f"Found {sum(len(devices) for devices in filtered_devices_by_type.values())} device(s) on {target_network}",
        "summary_stats": summary_stats if show_summary else None,
        "filters_applied": {
            "device_type": device_type_filter,
            "status": status_filter,
            "search": search_query,
            "ssh_status": ssh_status_filter,
            "power_state": power_state_filter,
            "force_refresh": force_refresh,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "limit": limit,
        },
    }


def test_device(device_id_or_name: str) -> Dict[str, Any]:
    """
    Test connectivity to a specific device.

    Supports both device_id and friendly_name lookup.

    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)

    Returns:
        Dictionary with test results
    """
    # Resolve to actual device_id
    device_id = resolve_device_identifier(device_id_or_name)
    if not device_id:
        error_msg = f"Device '{device_id_or_name}' not found in configuration"
        logger.error(error_msg)
        raise DeviceNotFoundError(error_msg, device_id=device_id_or_name)

    config = load_device_config()
    devices = config.get("devices", {})

    device = devices[device_id]
    ip = device.get("ip")

    if not ip:
        error_msg = f"Device '{device_id}' has no IP address configured"
        logger.error(error_msg)
        raise DeviceConnectionError(error_msg, device_id=device_id)

    # Test connectivity
    try:
        # Use faster ping for parallel operations: 1 packet with shorter timeout
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,  # Reduced timeout for faster parallel operations
        )

        reachable = result.returncode == 0

        # Test SSH if device has SSH port
        # Try to use SSH connection pool first (faster if connection exists)
        ssh_available = False
        ssh_port = device.get("ports", {}).get("ssh", 22)
        if device.get("ports", {}).get("ssh"):
            # Try SSH connection pool first (if connection exists, this is instant)
            try:
                from lab_testing.utils.ssh_pool import get_persistent_ssh_connection

                username = device.get("ssh_user", "root")
                master = get_persistent_ssh_connection(ip, username, device_id, ssh_port)
                if master and master.poll() is None:
                    # Connection exists, test with a quick SSH command
                    from lab_testing.utils.ssh_pool import execute_via_pool

                    test_result = execute_via_pool(ip, username, "echo test", device_id, ssh_port)
                    ssh_available = test_result.returncode == 0
                else:
                    # No connection, use netcat for quick port check
                    ssh_result = subprocess.run(
                        ["nc", "-z", "-w", "2", ip, str(ssh_port)],
                        check=False,
                        capture_output=True,
                        timeout=5,
                    )
                    ssh_available = ssh_result.returncode == 0
            except Exception:
                # Fallback to netcat if SSH pool check fails
                ssh_result = subprocess.run(
                    ["nc", "-z", "-w", "2", ip, str(ssh_port)],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
                ssh_available = ssh_result.returncode == 0

        friendly_name = device.get("friendly_name") or device.get("name", device_id)

        return {
            "success": True,
            "device_id": device_id,
            "friendly_name": friendly_name,
            "device_name": device.get("name", "Unknown"),
            "ip": ip,
            "ping_reachable": reachable,
            "ssh_available": ssh_available,
            "ping_output": result.stdout if reachable else result.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "device_id": device_id,
            "ip": ip,
            "error": "Connection test timed out",
        }
    except Exception as e:
        return {"success": False, "device_id": device_id, "ip": ip, "error": f"Test failed: {e!s}"}


def ssh_to_device(
    device_id_or_name: str, command: str, username: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute an SSH command on a device.

    Supports both device_id and friendly_name lookup.

    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)
        command: Command to execute
        username: SSH username (optional, uses device default if not specified)

    Returns:
        Dictionary with command results
    """
    # Resolve to actual device_id
    device_id = resolve_device_identifier(device_id_or_name)
    if not device_id:
        error_msg = f"Device '{device_id_or_name}' not found"
        logger.error(error_msg)
        raise DeviceNotFoundError(error_msg, device_id=device_id_or_name)

    config = load_device_config()
    devices = config.get("devices", {})

    device = devices[device_id]
    ip = device.get("ip")
    ssh_port = device.get("ports", {}).get("ssh", 22)

    if not ip:
        error_msg = f"Device '{device_id}' has no IP address"
        logger.error(error_msg)
        raise DeviceConnectionError(error_msg, device_id=device_id)

    logger.debug(f"Executing SSH command on {device_id} ({ip}): {command}")

    # Determine username
    if not username:
        username = device.get("ssh_user", "root")

    # Record change for tracking
    from lab_testing.utils.change_tracker import record_ssh_command

    change_id = record_ssh_command(device_id, command)

    # Execute SSH command with preferred authentication
    # Try connection pool first, fallback to direct connection
    try:
        from lab_testing.utils.process_manager import ensure_single_process
        from lab_testing.utils.ssh_pool import execute_via_pool

        # Check if this command might conflict with existing processes
        # Extract process name from command for conflict detection
        process_pattern = None
        if command.strip():
            # Simple heuristic: use first word as process name
            first_word = command.strip().split()[0]
            if (
                first_word
                and "/" not in first_word
                and first_word not in ["echo", "test", "cat", "grep"]
            ):
                process_pattern = first_word
                # Ensure no conflicting process is running
                ensure_single_process(
                    ip,
                    username,
                    device_id,
                    process_pattern,
                    command,
                    kill_existing=True,
                    force_kill=False,
                )

        # Try using connection pool
        try:
            result = execute_via_pool(ip, username, command, device_id, ssh_port)
            logger.debug(f"Executed via connection pool: {device_id}")
        except Exception as pool_error:
            logger.debug(
                f"Connection pool failed for {device_id}, using direct connection: {pool_error}"
            )
            # Fallback to direct connection
            ssh_cmd = get_ssh_command(ip, username, command, device_id, use_password=False)

            # Add port if not default
            if ssh_port != 22:
                # Insert port option before username@ip
                port_idx = ssh_cmd.index(f"{username}@{ip}")
                ssh_cmd.insert(port_idx, "-p")
                ssh_cmd.insert(port_idx + 1, str(ssh_port))

            result = subprocess.run(
                ssh_cmd, check=False, capture_output=True, text=True, timeout=30
            )

        friendly_name = device.get("friendly_name") or device.get("name", device_id)

        return {
            "success": result.returncode == 0,
            "device_id": device_id,
            "friendly_name": friendly_name,
            "device_name": device.get("name", "Unknown"),
            "ip": ip,
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "change_id": change_id,  # Include change tracking ID
        }

    except subprocess.TimeoutExpired:
        error_msg = "SSH command timed out"
        logger.warning(f"SSH timeout for {device_id}: {command}")
        raise SSHError(error_msg, device_id=device_id, command=command)
    except Exception as e:
        error_msg = f"SSH execution failed: {e!s}"
        logger.error(f"SSH error for {device_id}: {e}", exc_info=True)
        raise SSHError(error_msg, device_id=device_id, command=command)


def resolve_device_identifier(identifier: str) -> Optional[str]:
    """
    Resolve a device identifier (device_id or friendly_name) to the actual device_id.

    Devices can be referenced by:
    - device_id (unique ID, typically from hostname/SOC ID)
    - friendly_name (user-friendly name configured in device config)

    Args:
        identifier: Device identifier (device_id or friendly_name)

    Returns:
        Actual device_id if found, None otherwise
    """
    config = load_device_config()
    devices = config.get("devices", {})

    # First, check if it's a direct device_id match
    if identifier in devices:
        return identifier

    # Then, search by friendly_name
    for device_id, device_info in devices.items():
        friendly_name = device_info.get("friendly_name") or device_info.get("name")
        if friendly_name and friendly_name.lower() == identifier.lower():
            return device_id

        # Also check if identifier matches the "name" field
        if device_info.get("name", "").lower() == identifier.lower():
            return device_id

    return None


def get_device_info(device_id_or_name: str) -> Optional[Dict[str, Any]]:
    """
    Get device information from configuration.

    Supports both device_id and friendly_name lookup.

    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)

    Returns:
        Device information dictionary or None if not found
    """
    # Resolve to actual device_id
    device_id = resolve_device_identifier(device_id_or_name)
    if not device_id:
        return None

    config = load_device_config()
    devices = config.get("devices", {})

    if device_id in devices:
        device = devices[device_id].copy()
        device["device_id"] = device_id
        # Ensure friendly_name is set (use name if friendly_name not set)
        if "friendly_name" not in device:
            device["friendly_name"] = device.get("name", device_id)
        return device
    return None
