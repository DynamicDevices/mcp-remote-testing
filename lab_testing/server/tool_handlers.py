"""
Tool Handlers for MCP Server

Contains all tool execution handlers. This module is separated from server.py
to improve maintainability and code organization.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json

# Import record_tool_call from server.py (defined there)
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Union

from mcp.types import ImageContent, TextContent

from lab_testing.resources.help import get_help_content

# Development auto-reload support
try:
    from lab_testing.server.dev_reload import is_dev_mode, reload_lab_testing_modules

    _DEV_MODE = is_dev_mode()
except ImportError:
    _DEV_MODE = False

    def reload_lab_testing_modules():
        return []


# Import all tool functions
from lab_testing.tools.batch_operations import (
    batch_operation,
    get_device_groups,
    regression_test,
)
from lab_testing.tools.credential_manager import (
    cache_device_credentials,
    check_ssh_key_status,
    install_ssh_key_on_device,
)
from lab_testing.tools.device_manager import (
    list_devices,
    ssh_to_device,
    test_device,
)
from lab_testing.tools.device_verification import (
    update_device_ip_if_changed,
    verify_device_by_ip,
    verify_device_identity,
)
from lab_testing.tools.ota_manager import (
    check_ota_status,
    deploy_container,
    get_firmware_version,
    get_system_status,
    list_containers,
    trigger_ota_update,
)
from lab_testing.tools.power_analysis import (
    analyze_power_logs,
    compare_power_profiles,
    monitor_low_power,
)
from lab_testing.tools.power_monitor import get_power_logs, start_power_monitoring
from lab_testing.tools.tasmota_control import (
    list_tasmota_devices,
    power_cycle_device,
    tasmota_control,
)
from lab_testing.tools.test_equipment import (
    list_test_equipment,
    query_test_equipment,
)
from lab_testing.tools.vpn_manager import (
    connect_vpn,
    disconnect_vpn,
    get_vpn_status,
)
from lab_testing.tools.vpn_setup import (
    check_wireguard_installed,
    create_config_template,
    get_setup_instructions,
    list_existing_configs,
    setup_networkmanager_connection,
)
from lab_testing.utils.error_helper import (
    format_error_response,
    format_tool_response,
    validate_device_identifier,
)
from lab_testing.utils.logger import get_logger, log_tool_result

_server_py = Path(__file__).parent.parent / "server.py"
if _server_py.exists():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lab_testing.server_module", _server_py)
    server_module = importlib.util.module_from_spec(spec)
    sys.modules["lab_testing.server_module"] = server_module
    spec.loader.exec_module(server_module)
    record_tool_call = server_module.record_tool_call
else:

    def record_tool_call(name: str, success: bool, duration: float):
        pass  # Fallback


logger = get_logger()


def _format_test_equipment_as_table(test_equip_result: Dict[str, Any]) -> str:
    """
    Format test equipment information as a markdown table.

    Args:
        test_equip_result: Result dictionary from list_test_equipment()

    Returns:
        Formatted markdown table string
    """
    if not test_equip_result.get("success", False):
        error = test_equip_result.get("error", "Unknown error")
        return f"**Error:** {error}"

    devices = test_equip_result.get("devices", [])
    count = test_equip_result.get("count", 0)

    if count == 0:
        return (
            "**No test equipment found.**\n\nRun `list_devices` to discover devices on the network."
        )

    lines = []
    lines.append(f"## Test Equipment ({count} device(s))\n")
    lines.append("| Friendly Name | IP Address | Type | Model | Manufacturer | Port | Configured |")
    lines.append("|---------------|------------|------|-------|--------------|------|------------|")

    for device in devices:
        friendly_name = device.get("friendly_name", "Unknown")[:30]
        ip = device.get("ip", "Unknown")
        equipment_type = device.get("equipment_type", "test_equipment").replace("_", " ").title()
        model = device.get("model", "Unknown")[:20]
        manufacturer = device.get("manufacturer", "Unknown")[:20]
        ports = device.get("ports", {})
        scpi_port = ports.get("scpi", device.get("port", "—"))
        configured = "✓" if device.get("configured", False) else "—"

        lines.append(
            f"| {friendly_name} | `{ip}` | {equipment_type} | {model} | {manufacturer} | {scpi_port} | {configured} |"
        )

    return "\n".join(lines)


def _format_tasmota_devices_as_table(tasmota_result: Dict[str, Any]) -> str:
    """
    Format Tasmota device information as a markdown table.

    Args:
        tasmota_result: Result dictionary from list_tasmota_devices()

    Returns:
        Formatted markdown table string
    """
    if not tasmota_result.get("success", False):
        error = tasmota_result.get("error", "Unknown error")
        return f"**Error:** {error}"

    devices = tasmota_result.get("devices", [])
    count = tasmota_result.get("count", 0)

    if count == 0:
        return "**No Tasmota devices configured.**"

    lines = []
    lines.append(f"## Tasmota Power Switches ({count} device(s))\n")
    lines.append("| Friendly Name | Device ID | IP Address | Type | Status | Controls |")
    lines.append("|---------------|-----------|------------|------|--------|----------|")

    for device in devices:
        friendly_name = device.get("friendly_name", "Unknown")[:25]
        device_id = device.get("id", device.get("device_id", "Unknown"))[:25]
        ip = device.get("ip", "Unknown")
        device_type = device.get("type", "unknown").replace("_", " ").title()
        status = device.get("status", "unknown")

        # Format status
        if status == "online":
            status_display = "🟢 Online"
        elif status == "offline":
            status_display = "🔴 Offline"
        else:
            status_display = "⚪ Unknown"

        # Get controlled devices
        controlled = device.get("controls_devices", [])
        if controlled:
            controlled_names = [
                d.get("friendly_name", d.get("name", "Unknown")) for d in controlled
            ]
            controlled_str = ", ".join(controlled_names[:3])  # Show first 3
            if len(controlled) > 3:
                controlled_str += f" (+{len(controlled) - 3} more)"
        else:
            controlled_str = "—"

        lines.append(
            f"| {friendly_name} | {device_id} | {ip} | {device_type} | {status_display} | {controlled_str} |"
        )

    return "\n".join(lines)


def _format_devices_as_table(devices_result: Dict[str, Any]) -> str:
    """
    Format device information as a markdown table for easy reading.
    Includes summary statistics, last seen timestamps, and power switch relationships.

    Args:
        devices_result: Result dictionary from list_devices()

    Returns:
        Formatted markdown table string
    """
    devices_by_type = devices_result.get("devices_by_type", {})
    total_devices = devices_result.get("total_devices", 0)
    summary_stats = devices_result.get("summary_stats")
    filters_applied = devices_result.get("filters_applied", {})
    target_network = devices_result.get("target_network", "Unknown")

    if total_devices == 0:
        filter_info = ""
        if any(filters_applied.values()):
            active_filters = [f"{k}: {v}" for k, v in filters_applied.items() if v]
            filter_info = f"\n\n**Filters applied:** {', '.join(active_filters)}"
        return f"**No devices found.**{filter_info}\n\nAdd devices to your `lab_devices.json` configuration file or run discovery on the target network."

    lines = []
    lines.append(f"## Device Inventory ({total_devices} total devices)")

    # Show summary statistics if available
    if summary_stats:
        lines.append("\n### Summary Statistics\n")
        type_counts = summary_stats.get("by_type", {})
        status_counts = summary_stats.get("by_status", {})
        ssh_status_counts = summary_stats.get("by_ssh_status", {})

        if type_counts:
            type_summary = ", ".join(
                [f"{v} {k.replace('_', ' ').title()}" for k, v in sorted(type_counts.items())]
            )
            lines.append(f"- **By Type:** {type_summary}")

        if status_counts:
            status_summary = ", ".join(
                [f"{v} {k.title()}" for k, v in sorted(status_counts.items())]
            )
            lines.append(f"- **By Status:** {status_summary}")

        if ssh_status_counts:
            ssh_summary = ", ".join(
                [f"{v} SSH {k.title()}" for k, v in sorted(ssh_status_counts.items())]
            )
            lines.append(f"- **By SSH Status:** {ssh_summary}")

        lines.append("")

    # Show filters if applied
    if any(filters_applied.values()):
        active_filters = []
        if filters_applied.get("device_type"):
            active_filters.append(f"Type: {filters_applied['device_type']}")
        if filters_applied.get("status"):
            active_filters.append(f"Status: {filters_applied['status']}")
        if filters_applied.get("search"):
            active_filters.append(f"Search: '{filters_applied['search']}'")
        if active_filters:
            lines.append(f"**Filters:** {', '.join(active_filters)}\n")

    lines.append(f"**Target Network:** {target_network}\n")

    # Create markdown table with additional columns
    lines.append(
        "| Friendly Name | IP Address | Status | Device ID | Type | Firmware | VPN | SSH Status | Last Seen | Power Switch |"
    )
    lines.append(
        "|---------------|------------|--------|-----------|------|----------|-----|------------|-----------|--------------|"
    )

    # Collect all devices with their types
    all_devices = []
    for device_type, device_list in devices_by_type.items():
        type_name = device_type.replace("_", " ").title()
        for device in device_list:
            device["_type"] = type_name
            all_devices.append(device)

    # Sort all devices by type, then by friendly name
    sorted_devices = sorted(
        all_devices,
        key=lambda x: (x.get("_type", ""), (x.get("friendly_name") or x.get("name", "")).lower()),
    )

    for device in sorted_devices:
        friendly_name = device.get("friendly_name") or device.get("name", "Unknown")
        device_id = device.get("id", "Unknown")
        ip = device.get("ip", "Unknown")
        status = device.get("status", "unknown")
        # Use device_type from device data, fallback to _type (which is the formatted type name)
        device_type = device.get("device_type") or device.get("_type", "Unknown")
        firmware = device.get("firmware")
        hostname = device.get("hostname")
        description = device.get("description")
        model = device.get("model")

        # Format status with emoji
        if status == "online":
            status_display = "🟢 Online"
        elif status == "offline":
            status_display = "🔴 Offline"
        elif status == "discovered":
            status_display = "🔵 Discovered"
        elif status == "verified":
            status_display = "✅ Verified"
        elif status == "template":
            status_display = "📋 Template"
        else:
            status_display = f"⚪ {status.title()}"

        # Format firmware version
        firmware_display = "—"
        if firmware:
            version_id = firmware.get("version_id", "")
            pretty_name = firmware.get("pretty_name", "")
            if version_id and version_id != "Unknown":
                firmware_display = version_id
            elif pretty_name and pretty_name != "Unknown":
                firmware_display = pretty_name[:20] + ("..." if len(pretty_name) > 20 else "")

        # Format VPN status
        discovered_via_vpn = device.get("discovered_via_vpn", False)
        vpn_display = "🔒 VPN" if discovered_via_vpn else "—"

        # Format SSH status/errors
        ssh_error = device.get("ssh_error")
        ssh_error_type = device.get("ssh_error_type")
        if ssh_error:
            if ssh_error_type == "timeout":
                ssh_display = "⏱️ Timeout"
            elif ssh_error_type == "connection_refused":
                ssh_display = "🚫 Refused"
            elif ssh_error_type == "auth_failed":
                ssh_display = "🔐 Auth Failed"
            else:
                ssh_display = "❌ SSH Error"
        elif hostname:
            ssh_display = "✅ OK"
        else:
            ssh_display = "—"

        # Format device type - use more descriptive names
        device_type_display = device_type.replace("_", " ").title()

        # For test equipment, show the specific equipment type (e.g., DMM)
        if device_type == "test_equipment":
            equipment_type = device.get("equipment_type")
            if equipment_type:
                # Capitalize and format (e.g., "dmm" -> "DMM", "power_supply" -> "Power Supply")
                device_type_display = (
                    equipment_type.upper()
                    if equipment_type in ["dmm", "oscilloscope"]
                    else equipment_type.replace("_", " ").title()
                )
            else:
                device_type_display = "Test Equipment"
        # For Tasmota devices, add power state and consumption
        elif device_type == "tasmota_device":
            # Get Tasmota power info from device data
            tasmota_power_state = device.get("tasmota_power_state")
            tasmota_power_watts = device.get("tasmota_power_watts")

            power_info = ""
            if tasmota_power_state:
                power_icon = "🟢" if tasmota_power_state == "on" else "🔴"
                power_info = f" {power_icon} {tasmota_power_state.upper()}"

            if tasmota_power_watts is not None:
                power_info += f" {tasmota_power_watts:.1f}W"

            if power_info:
                device_type_display = f"Tasmota Device{power_info}"
            else:
                device_type_display = "Tasmota Device"
        elif device_type_display == "Other":
            # Try to get more info from description or model
            if model:
                device_type_display = model[:20]
            elif description:
                device_type_display = description[:20] + ("..." if len(description) > 20 else "")
            # If still "Other" and we have hostname, use that as a hint
            elif hostname and hostname != device_id:
                # Try to infer type from hostname patterns
                hostname_lower = hostname.lower()
                if any(x in hostname_lower for x in ["board", "dev", "test", "lab"]):
                    device_type_display = "Lab Device"
                elif any(x in hostname_lower for x in ["router", "switch", "gateway"]):
                    device_type_display = "Network Device"
                else:
                    device_type_display = (
                        hostname[:20] if len(hostname) <= 20 else hostname[:17] + "..."
                    )
        elif device_type_display == "Eink Board":
            device_type_display = "E-ink Board"
        elif device_type_display == "Sentai Board":
            device_type_display = "Sentai Board"

        # Format hostname/identifier - prefer hostname, show device_id if no hostname
        if hostname and hostname != device_id:
            identifier_display = hostname
        else:
            identifier_display = device_id
        if len(identifier_display) > 25:
            identifier_display = identifier_display[:22] + "..."

        # Format last seen timestamp
        last_seen = device.get("last_seen", "—")
        if last_seen == "Unknown":
            last_seen = "—"

        # Format power switch relationship
        # For Tasmota devices, show their own power state (ON/OFF)
        tasmota_power_state = device.get("tasmota_power_state")
        if tasmota_power_state:
            # Tasmota device - show its own power state
            if tasmota_power_state.lower() == "on":
                power_switch_display = "🟢 ON"
            elif tasmota_power_state.lower() == "off":
                power_switch_display = "🔴 OFF"
            else:
                power_switch_display = f"⚪ {tasmota_power_state.upper()}"
        else:
            # Check if this device is controlled by a power switch
            power_switch = device.get("power_switch")
            if power_switch:
                switch_name = power_switch.get(
                    "friendly_name", power_switch.get("device_id", "Unknown")
                )
                power_switch_display = f"🔌 {switch_name[:20]}" + (
                    "..." if len(switch_name) > 20 else ""
                )
            else:
                power_switch_display = "—"

        # Truncate long names/IDs for table readability
        friendly_name_display = friendly_name[:30] + ("..." if len(friendly_name) > 30 else "")
        device_id_display = device_id[:20] + ("..." if len(device_id) > 20 else "")

        lines.append(
            f"| {friendly_name_display} | `{ip}` | {status_display} | `{identifier_display}` | {device_type_display} | {firmware_display} | {vpn_display} | {ssh_display} | {last_seen} | {power_switch_display} |"
        )

    # Add network info if available
    lab_networks = devices_result.get("lab_networks", [])
    if lab_networks:
        lines.append("\n### Lab Networks\n")
        for network in lab_networks:
            lines.append(f"- {network}")

    return "\n".join(lines)


def _record_tool_result(name: str, result: Dict[str, Any], request_id: str, start_time: float):
    """Helper to record tool result and metrics"""
    success = result.get("success", False)
    error = result.get("error")
    duration = time.time() - start_time
    log_tool_result(name, success, request_id, error)
    record_tool_call(name, success, duration)


def handle_tool(
    name: str, arguments: Dict[str, Any], request_id: str, start_time: float
) -> List[Union[TextContent, ImageContent]]:
    """
    Handle tool execution. This function routes tool calls to appropriate handlers.

    Args:
        name: Tool name
        arguments: Tool arguments
        request_id: Request ID for logging
        start_time: Start time for metrics

    Returns:
        List of TextContent responses
    """
    # Development mode: Auto-reload modules if they've changed
    # Note: We skip reloading tool_handlers itself to avoid breaking the current execution
    if _DEV_MODE:
        try:
            reloaded = reload_lab_testing_modules()
            # Filter out tool_handlers from reloaded list to avoid breaking current execution
            reloaded_filtered = [m for m in reloaded if m != "lab_testing.server.tool_handlers"]
            if reloaded_filtered:
                logger.info(
                    f"[{request_id}] 🔄 AUTO-RELOAD: Reloaded {len(reloaded_filtered)} module(s): {', '.join(reloaded_filtered)}"
                )
                print(
                    f"[DEV MODE] 🔄 Auto-reloaded {len(reloaded_filtered)} module(s): {', '.join(reloaded_filtered)}",
                    file=sys.stderr,
                )
            elif reloaded:
                logger.debug(
                    f"[{request_id}] Auto-reload: tool_handlers changed (will reload on next call)"
                )
            else:
                logger.debug(f"[{request_id}] Auto-reload check: No modules changed")
        except Exception as reload_error:
            # Don't let auto-reload errors break tool execution
            logger.warning(f"[{request_id}] Auto-reload error (non-fatal): {reload_error}")

    try:
        # Device Management
        if name == "list_devices":
            try:
                # Get filter parameters
                device_type_filter = arguments.get("device_type_filter")
                status_filter = arguments.get("status_filter")
                search_query = arguments.get("search_query")
                show_summary = arguments.get("show_summary", True)
                force_refresh = arguments.get("force_refresh", False)
                ssh_status_filter = arguments.get("ssh_status_filter")
                power_state_filter = arguments.get("power_state_filter")
                sort_by = arguments.get("sort_by")
                sort_order = arguments.get("sort_order", "asc")
                limit = arguments.get("limit")

                result = list_devices(
                    device_type_filter=device_type_filter,
                    status_filter=status_filter,
                    search_query=search_query,
                    show_summary=show_summary,
                    force_refresh=force_refresh,
                    ssh_status_filter=ssh_status_filter,
                    power_state_filter=power_state_filter,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    limit=limit,
                )
                _record_tool_result(name, result, request_id, start_time)
                # Format as table for better readability
                table_text = _format_devices_as_table(result)
                logger.info(
                    f"[{request_id}] list_devices: formatted text length={len(table_text)}, preview={table_text[:200]}"
                )
                if not table_text or not table_text.strip():
                    logger.error(f"[{request_id}] list_devices: formatted text is empty!")
                    return [
                        TextContent(
                            type="text", text="Error: Device list formatting returned empty result"
                        )
                    ]

                # Ensure TextContent is created correctly
                try:
                    # Ensure text is a string and not empty
                    if not isinstance(table_text, str):
                        table_text = str(table_text)
                    if not table_text.strip():
                        raise ValueError("Table text is empty after conversion")

                    # Create a brief summary that's always visible (first TextContent)
                    total_devices = result.get("total_devices", 0)
                    summary_stats = result.get("summary_stats", {})
                    type_counts = summary_stats.get("by_type", {})
                    status_counts = summary_stats.get("by_status", {})

                    # Build a concise one-line summary
                    summary_parts = [f"**{total_devices} devices**"]
                    if type_counts:
                        type_summary = ", ".join(
                            [
                                f"{v} {k.replace('_', ' ').title()}"
                                for k, v in sorted(type_counts.items())
                            ]
                        )
                        summary_parts.append(f"({type_summary})")
                    if status_counts:
                        online = status_counts.get("online", 0)
                        if online > 0:
                            summary_parts.append(f"— {online} online")

                    summary_text = " ".join(summary_parts)

                    # Combine summary and table into a single TextContent for better visibility
                    # The summary appears first, followed by the full table
                    combined_text = f"{summary_text}\n\n{table_text}"

                    # Create single TextContent with combined summary and table
                    combined_content = TextContent(type="text", text=combined_text)

                    # Verify the content was created correctly
                    if not hasattr(combined_content, "text") or not combined_content.text:
                        raise ValueError(
                            "Combined TextContent created but text attribute is missing or empty"
                        )

                    logger.info(
                        f"[{request_id}] list_devices: Created combined content (summary length={len(summary_text)}, table length={len(table_text)}, total={len(combined_text)})"
                    )

                    # Return single combined content item
                    result_list = [combined_content]
                    logger.debug(
                        f"[{request_id}] list_devices: Returning {len(result_list)} content item(s)"
                    )
                    return result_list
                except Exception as e:
                    logger.error(
                        f"[{request_id}] list_devices: Failed to create TextContent: {e}",
                        exc_info=True,
                    )
                    # Fallback: return as JSON
                    fallback_text = json.dumps(result, indent=2)
                    logger.warning(
                        f"[{request_id}] list_devices: Using JSON fallback, length={len(fallback_text)}"
                    )
                    return [TextContent(type="text", text=fallback_text)]
            except Exception as e:
                logger.error(f"[{request_id}] list_devices: Unexpected error: {e}", exc_info=True)
                # Return a safe error response
                error_msg = f"Error listing devices: {e!s}"
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": error_msg, "request_id": request_id}, indent=2),
                    )
                ]

        if name == "test_device":
            device_id = arguments.get("device_id")
            if not device_id:
                error_response = {
                    "error": "device_id is required",
                    "suggestions": [
                        "Provide a device_id or friendly_name",
                        "Use 'list_devices' to see available devices",
                        "You can use either the unique device_id or friendly_name",
                    ],
                    "related_tools": ["list_devices", "get_device_info"],
                    "example": {
                        "device_id": "imx93_eink_board_2",
                        "or": "friendly_name like 'E-ink Board 2'",
                    },
                }
                logger.warning(f"[{request_id}] {error_response['error']}")
                log_tool_result(name, False, request_id, error_response["error"])
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

            # Validate device identifier
            try:
                devices_config = list_devices()
                all_devices = {}
                for device_type, devices in devices_config.get("devices_by_type", {}).items():
                    for dev in devices:
                        all_devices[dev["id"]] = dev

                validation = validate_device_identifier(device_id, all_devices)
                if not validation["valid"] and validation["alternatives"]:
                    error_response = {
                        "error": f"Device '{device_id}' not found",
                        "suggestions": validation["suggestions"],
                        "alternatives": validation["alternatives"],
                        "related_tools": ["list_devices", "get_device_info"],
                    }
                    logger.warning(f"[{request_id}] {error_response['error']}")
                    log_tool_result(name, False, request_id, error_response["error"])
                    duration = time.time() - start_time
                    record_tool_call(name, False, duration)
                    return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
            except Exception:
                pass

            result = test_device(device_id)
            result = format_tool_response(result, name)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "ssh_to_device":
            device_id = arguments.get("device_id")
            command = arguments.get("command")
            username = arguments.get("username")

            if not device_id or not command:
                error_msg = "device_id and command are required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

            result = ssh_to_device(device_id, command, username)
            result = format_tool_response(result, name)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # VPN Management
        if name == "vpn_status":
            result = get_vpn_status()
            result = format_tool_response(result, name)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "connect_vpn":
            result = connect_vpn()
            result = format_tool_response(result, name)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "disconnect_vpn":
            result = disconnect_vpn()
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "vpn_statistics":
            from lab_testing.tools.vpn_manager import get_vpn_statistics

            result = get_vpn_statistics()
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "vpn_setup_instructions":
            result = get_setup_instructions()
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "check_wireguard_installed":
            result = check_wireguard_installed()
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "list_vpn_configs":
            result = list_existing_configs()
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "create_vpn_config_template":
            output_path = arguments.get("output_path")
            if output_path:
                output_path = Path(output_path)
            else:
                output_path = None
            result = create_config_template(output_path)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "setup_networkmanager_vpn":
            config_path = arguments.get("config_path")
            if config_path:
                config_path = Path(config_path)
            else:
                from lab_testing.config import get_vpn_config

                config_path = get_vpn_config()
                if not config_path:
                    error_msg = (
                        "No VPN config found. Create one first with create_vpn_config_template"
                    )
                    logger.warning(f"[{request_id}] {error_msg}")
                    log_tool_result(name, False, request_id, error_msg)
                    duration = time.time() - start_time
                    record_tool_call(name, False, duration)
                    return [
                        TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))
                    ]
            result = setup_networkmanager_connection(config_path)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Network Mapping
        if name == "create_network_map":
            networks = arguments.get("networks")
            scan_networks = arguments.get("scan_networks", True)
            test_configured_devices = arguments.get("test_configured_devices", True)
            max_hosts = arguments.get("max_hosts_per_network", 254)
            quick_mode = arguments.get("quick_mode", False)
            layout = arguments.get("layout", "lr")
            group_by = arguments.get("group_by", "type")
            show_details = arguments.get("show_details", False)
            show_metrics = arguments.get("show_metrics", True)
            show_alerts = arguments.get("show_alerts", True)
            show_history = arguments.get("show_history", False)
            export_format = arguments.get("export_format", "mermaid")
            export_path = arguments.get("export_path")

            # Get target network for display
            from lab_testing.config import get_target_network, get_target_network_friendly_name
            from lab_testing.tools.network_mapper import (
                convert_mermaid_to_png,
                create_network_map,
                generate_network_map_image,
                generate_network_map_mermaid,
                generate_network_map_visualization,
            )

            target_network = get_target_network()
            network_friendly_name = get_target_network_friendly_name()

            # Log the operation with target network info
            mode_info = "Quick mode (no network scan)" if quick_mode else "Full scan mode"
            logger.info(
                f"[{request_id}] Creating network map - Target: {target_network}, Mode: {mode_info}, Layout: {layout}, Group by: {group_by}"
            )

            # Create network map by scanning the network
            network_map = create_network_map(
                networks=networks,
                scan_networks=scan_networks,
                test_configured_devices=test_configured_devices,
                max_hosts_per_network=max_hosts,
                quick_mode=quick_mode,
                layout=layout,
                group_by=group_by,
                show_details=show_details,
                show_metrics=show_metrics,
                show_alerts=show_alerts,
                show_history=show_history,
                export_format=export_format,
                export_path=export_path,
            )

            # Generate Mermaid diagram (primary)
            mermaid_diagram = generate_network_map_mermaid(network_map)

            # Convert Mermaid diagram to PNG
            mermaid_png_base64 = convert_mermaid_to_png(mermaid_diagram, output_path=None)

            # Generate matplotlib PNG image visualization (fallback)
            image_base64 = generate_network_map_image(network_map, output_path=None)

            # Generate text visualization (for detailed info)
            visualization = generate_network_map_visualization(network_map, format="text")

            # Combine all visualizations in the result
            result = {
                "success": True,
                "network_map": network_map,
                "visualization": visualization,
                "mermaid_diagram": mermaid_diagram,
                "mermaid_png_base64": (
                    mermaid_png_base64[:50] + "..." if mermaid_png_base64 else None
                ),
                "image_base64": image_base64[:50] + "..." if image_base64 else None,
            }
            _record_tool_result(name, result, request_id, start_time)

            # Return PNG image as primary visualization (since Cursor doesn't render Mermaid yet)
            contents = []

            # Add PNG image from Mermaid conversion (preferred over matplotlib version)
            png_to_use = mermaid_png_base64 if mermaid_png_base64 else image_base64

            # Add PNG image as fallback if available
            # Try both ImageContent (MCP standard) and data URI in TextContent (for Cursor compatibility)
            if png_to_use:
                try:
                    # Return image as ImageContent (MCP standard format)
                    logger.info(
                        f"[{request_id}] Creating ImageContent: data length={len(png_to_use)}, source={'mermaid' if mermaid_png_base64 else 'matplotlib'}"
                    )
                    image_content = ImageContent(
                        type="image", data=png_to_use, mimeType="image/png"
                    )
                    contents.append(image_content)
                    logger.info(f"[{request_id}] ImageContent created successfully")

                    # Save high-resolution image to file for clickable link
                    import base64
                    import tempfile
                    from pathlib import Path

                    # Save to a file in the project directory for easy access
                    project_root = Path(__file__).parent.parent.parent
                    network_map_dir = project_root / "network_maps"
                    network_map_dir.mkdir(exist_ok=True)

                    # Create filename with timestamp
                    from datetime import datetime

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    image_file = network_map_dir / f"network_map_{timestamp}.png"

                    # Write the PNG data
                    with open(image_file, "wb") as f:
                        f.write(base64.b64decode(png_to_use))

                    # Also add as data URI in TextContent for inline viewing
                    data_uri = f"data:image/png;base64,{png_to_use}"
                    # Provide both embedded image and clickable link
                    # Use HTML anchor tag to make image clickable and enlargeable
                    image_text = (
                        f"\n\n"
                        f'<a href="{data_uri}" target="_blank" title="Click to enlarge">'
                        f'<img src="{data_uri}" alt="Network Map" style="max-width: 100%; cursor: pointer;" />'
                        f"</a>\n\n"
                        f"**Full-size image saved to:** `{image_file.relative_to(project_root)}`\n\n"
                    )
                    contents.append(TextContent(type="text", text=image_text))
                except Exception as e:
                    logger.error(
                        f"[{request_id}] Failed to create ImageContent: {e}", exc_info=True
                    )
                    # Fallback: save to temp file and include path
                    import base64
                    import tempfile

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(base64.b64decode(png_to_use))
                        tmp_path = tmp.name
                    contents.append(
                        TextContent(
                            type="text",
                            text=f"Network map image saved to: {tmp_path}\n\n{mermaid_diagram}",
                        )
                    )

            # Add Mermaid diagram text after the image (for copying/export if needed)
            # Note: Cursor doesn't render Mermaid diagrams interactively yet, so PNG is primary
            if mermaid_diagram:
                mermaid_note = (
                    "\n\n---\n\n"
                    "**Mermaid Diagram Source** (available for copying/export):\n\n"
                    f"{mermaid_diagram}\n\n"
                    "*Note: Cursor doesn't render Mermaid diagrams interactively yet. "
                    "Use the PNG image above for visualization, or copy the Mermaid code to render elsewhere.*\n"
                )
                contents.append(TextContent(type="text", text=mermaid_note))

            # Add summary as separate content with target network info
            summary = network_map.get("summary", {})
            if summary:
                mode_info = "Quick mode (no network scan)" if quick_mode else "Full scan mode"
                summary_text = (
                    f"\n\n---\n\n**Network Summary:**\n"
                    f"- Network: {network_friendly_name} ({target_network})\n"
                    f"- Mode: {mode_info}\n"
                    f"- Total Devices: {summary.get('total_configured_devices', 0)}\n"
                    f"- Online: {summary.get('online_devices', 0)}\n"
                    f"- Offline: {summary.get('offline_devices', 0)}\n"
                )
                contents.append(TextContent(type="text", text=summary_text))

            return contents

        # Device Verification
        if name == "verify_device_identity":
            device_id = arguments.get("device_id")
            ip = arguments.get("ip")
            if not device_id:
                error_msg = "device_id is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = verify_device_identity(device_id, ip)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "verify_device_by_ip":
            ip = arguments.get("ip")
            username = arguments.get("username", "root")
            ssh_port = arguments.get("ssh_port", 22)
            if not ip:
                error_msg = "ip is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = verify_device_by_ip(ip, username, ssh_port)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "update_device_ip":
            device_id = arguments.get("device_id")
            new_ip = arguments.get("new_ip")
            if not device_id or not new_ip:
                error_msg = "device_id and new_ip are required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = update_device_ip_if_changed(device_id, new_ip)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Power Monitoring
        if name == "start_power_monitoring":
            device_id = arguments.get("device_id")
            test_name = arguments.get("test_name")
            duration = arguments.get("duration")
            monitor_type = arguments.get("monitor_type")
            result = start_power_monitoring(device_id, test_name, duration, monitor_type)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "get_power_logs":
            test_name = arguments.get("test_name")
            limit = arguments.get("limit", 10)
            result = get_power_logs(test_name, limit)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Tasmota Control
        if name == "tasmota_control":
            device_id = arguments.get("device_id")
            action = arguments.get("action")

            if not device_id or not action:
                error_msg = "device_id and action are required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

            result = tasmota_control(device_id, action)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "list_tasmota_devices":
            result = list_tasmota_devices()
            _record_tool_result(name, result, request_id, start_time)
            # Format as table for better readability
            table_text = _format_tasmota_devices_as_table(result)
            return [TextContent(type="text", text=table_text)]

        # Test Equipment Management
        if name == "list_test_equipment":
            result = list_test_equipment()
            _record_tool_result(name, result, request_id, start_time)
            # Format as table for better readability
            table_text = _format_test_equipment_as_table(result)
            return [TextContent(type="text", text=table_text)]

        if name == "query_test_equipment":
            device_id_or_ip = arguments.get("device_id_or_ip")
            scpi_command = arguments.get("scpi_command")

            if not device_id_or_ip or not scpi_command:
                error_msg = "Both 'device_id_or_ip' and 'scpi_command' are required"
                logger.error(f"[{request_id}] {error_msg}")
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

            try:
                result = query_test_equipment(device_id_or_ip, scpi_command)
                _record_tool_result(name, result, request_id, start_time)

                if result.get("success"):
                    response_text = (
                        f"**SCPI Query Result:**\n\n"
                        f"- **Device**: {result.get('device_id_or_ip', device_id_or_ip)}\n"
                        f"- **IP**: {result.get('ip')}\n"
                        f"- **Port**: {result.get('port')}\n"
                        f"- **Command**: `{result.get('command')}`\n"
                        f"- **Response**: `{result.get('response')}`\n"
                    )
                else:
                    response_text = json.dumps(result, indent=2)

                return [TextContent(type="text", text=response_text)]
            except Exception as e:
                error_msg = f"Failed to query test equipment: {e!s}"
                logger.error(f"[{request_id}] {error_msg}", exc_info=True)
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

        if name == "power_cycle_device":
            device_id = arguments.get("device_id")
            off_duration = arguments.get("off_duration", 5)
            if not device_id:
                error_msg = "device_id is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = power_cycle_device(device_id, off_duration)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Help
        if name == "help":
            topic = arguments.get("topic", "all")
            help_content = get_help_content()

            if topic == "all":
                result = {"success": True, "content": help_content}
            elif topic in help_content:
                result = {"success": True, "content": {topic: help_content[topic]}}
            else:
                result = {
                    "success": False,
                    "error": f"Unknown topic: {topic}",
                    "available_topics": [
                        "all",
                        "tools",
                        "resources",
                        "workflows",
                        "troubleshooting",
                        "examples",
                        "configuration",
                    ],
                }

            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Device Management - Friendly Name Update
        if name == "cache_device_credentials":
            device_id = arguments.get("device_id")
            username = arguments.get("username")
            password = arguments.get("password")
            credential_type = arguments.get("credential_type", "ssh")

            if not device_id or not username:
                error_msg = "Both 'device_id' and 'username' are required"
                logger.error(f"[{request_id}] {error_msg}")
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

            try:
                result = cache_device_credentials(
                    device_id=device_id,
                    username=username,
                    password=password,
                    credential_type=credential_type,
                )
                _record_tool_result(name, result, request_id, start_time)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                error_msg = f"Failed to cache credentials: {e!s}"
                logger.error(f"[{request_id}] {error_msg}", exc_info=True)
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

        if name == "check_ssh_key_status":
            device_id = arguments.get("device_id")
            username = arguments.get("username")

            if not device_id:
                error_msg = "device_id is required"
                logger.error(f"[{request_id}] {error_msg}")
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

            try:
                result = check_ssh_key_status(device_id=device_id, username=username)
                _record_tool_result(name, result, request_id, start_time)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                error_msg = f"Failed to check SSH key status: {e!s}"
                logger.error(f"[{request_id}] {error_msg}", exc_info=True)
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

        if name == "install_ssh_key":
            device_id = arguments.get("device_id")
            username = arguments.get("username")
            password = arguments.get("password")

            if not device_id:
                error_msg = "device_id is required"
                logger.error(f"[{request_id}] {error_msg}")
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

            try:
                result = install_ssh_key_on_device(
                    device_id=device_id, username=username, password=password
                )
                _record_tool_result(name, result, request_id, start_time)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                error_msg = f"Failed to install SSH key: {e!s}"
                logger.error(f"[{request_id}] {error_msg}", exc_info=True)
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

        if name == "update_device_friendly_name":
            from lab_testing.utils.device_cache import update_cached_friendly_name

            ip = arguments.get("ip")
            friendly_name = arguments.get("friendly_name")

            if not ip or not friendly_name:
                error_msg = "Both 'ip' and 'friendly_name' are required"
                logger.error(f"[{request_id}] {error_msg}")
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

            try:
                success = update_cached_friendly_name(ip, friendly_name)
                if success:
                    result = {
                        "success": True,
                        "message": f"Updated friendly name for {ip} to '{friendly_name}'",
                        "ip": ip,
                        "friendly_name": friendly_name,
                    }
                    _record_tool_result(name, result, request_id, start_time)
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                error_msg = f"Device {ip} not found in cache. Run 'list_devices' first to discover and cache the device."
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            except Exception as e:
                error_msg = f"Failed to update friendly name: {e!s}"
                logger.error(f"[{request_id}] {error_msg}", exc_info=True)
                _record_tool_result(
                    name, {"success": False, "error": error_msg}, request_id, start_time
                )
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

        # OTA Management
        if name == "check_ota_status":
            device_id = arguments.get("device_id")
            if not device_id:
                error_msg = "device_id is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = check_ota_status(device_id)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "trigger_ota_update":
            device_id = arguments.get("device_id")
            target = arguments.get("target")
            if not device_id:
                error_msg = "device_id is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = trigger_ota_update(device_id, target)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "list_containers":
            device_id = arguments.get("device_id")
            if not device_id:
                error_msg = "device_id is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = list_containers(device_id)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "deploy_container":
            device_id = arguments.get("device_id")
            container_name = arguments.get("container_name")
            image = arguments.get("image")
            if not all([device_id, container_name, image]):
                error_msg = "device_id, container_name, and image are required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = deploy_container(device_id, container_name, image)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "get_system_status":
            device_id = arguments.get("device_id")
            if not device_id:
                error_msg = "device_id is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = get_system_status(device_id)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "get_firmware_version":
            device_id = arguments.get("device_id")
            if not device_id:
                error_msg = "device_id is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = get_firmware_version(device_id)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Batch Operations
        if name == "batch_operation":
            device_ids = arguments.get("device_ids", [])
            operation = arguments.get("operation")
            if not device_ids or not operation:
                error_msg = "device_ids and operation are required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = batch_operation(
                device_ids,
                operation,
                **{k: v for k, v in arguments.items() if k not in ["device_ids", "operation"]},
            )
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "regression_test":
            device_group = arguments.get("device_group")
            device_ids = arguments.get("device_ids")
            test_sequence = arguments.get("test_sequence")
            result = regression_test(device_group, device_ids, test_sequence)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "get_device_groups":
            result = get_device_groups()
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Power Analysis
        if name == "analyze_power_logs":
            test_name = arguments.get("test_name")
            device_id = arguments.get("device_id")
            threshold_mw = arguments.get("threshold_mw")
            result = analyze_power_logs(test_name, device_id, threshold_mw)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "monitor_low_power":
            device_id = arguments.get("device_id")
            duration = arguments.get("duration", 300)
            threshold_mw = arguments.get("threshold_mw", 100.0)
            sample_rate = arguments.get("sample_rate", 1.0)
            if not device_id:
                error_msg = "device_id is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration_time = time.time() - start_time
                record_tool_call(name, False, duration_time)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = monitor_low_power(device_id, duration, threshold_mw, sample_rate)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "compare_power_profiles":
            test_names = arguments.get("test_names", [])
            device_id = arguments.get("device_id")
            if not test_names:
                error_msg = "test_names is required"
                logger.warning(f"[{request_id}] {error_msg}")
                log_tool_result(name, False, request_id, error_msg)
                duration = time.time() - start_time
                record_tool_call(name, False, duration)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = compare_power_profiles(test_names, device_id)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Unknown tool
        error_msg = f"Unknown tool: {name}"
        logger.warning(f"[{request_id}] {error_msg}")
        log_tool_result(name, False, request_id, error_msg)
        duration = time.time() - start_time
        record_tool_call(name, False, duration)
        return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]

    except Exception as e:
        # Format error with helpful context
        error_response = format_error_response(
            e, context={"tool_name": name, "arguments": arguments, "request_id": request_id}
        )
        error_response["tool"] = name
        error_response["request_id"] = request_id
        logger.error(f"[{request_id}] Tool execution failed: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
