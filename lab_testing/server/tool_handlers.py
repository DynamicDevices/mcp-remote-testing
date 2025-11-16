"""
Tool Handlers for MCP Server

Contains all tool execution handlers. This module is separated from server.py
to improve maintainability and code organization.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from mcp.types import TextContent

# Import all tool functions
from lab_testing.tools.batch_operations import (
    batch_operation,
    get_device_groups,
    regression_test,
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
from lab_testing.tools.network_mapper import (
    create_network_map,
    generate_network_map_visualization,
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
from lab_testing.resources.help import get_help_content
from lab_testing.utils.error_helper import (
    format_error_response,
    format_tool_response,
    validate_device_identifier,
)
from lab_testing.utils.logger import get_logger, log_tool_result, record_tool_call

logger = get_logger()


def _record_tool_result(name: str, result: Dict[str, Any], request_id: str, start_time: float):
    """Helper to record tool result and metrics"""
    success = result.get("success", False)
    error = result.get("error")
    duration = time.time() - start_time
    log_tool_result(name, success, request_id, error)
    record_tool_call(name, success, duration)


def handle_tool(
    name: str,
    arguments: Dict[str, Any],
    request_id: str,
    start_time: float
) -> List[TextContent]:
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
    try:
        # Device Management
        if name == "list_devices":
            result = list_devices()
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "test_device":
            device_id = arguments.get("device_id")
            if not device_id:
                error_response = {
                    "error": "device_id is required",
                    "suggestions": [
                        "Provide a device_id or friendly_name",
                        "Use 'list_devices' to see available devices",
                        "You can use either the unique device_id or friendly_name"
                    ],
                    "related_tools": ["list_devices", "get_device_info"],
                    "example": {
                        "device_id": "imx93_eink_board_2",
                        "or": "friendly_name like 'E-ink Board 2'"
                    }
                }
                logger.warning(f"[{request_id}] {error_response['error']}")
                log_tool_result(name, False, request_id, error_response['error'])
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
                        "related_tools": ["list_devices", "get_device_info"]
                    }
                    logger.warning(f"[{request_id}] {error_response['error']}")
                    log_tool_result(name, False, request_id, error_response['error'])
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
                    error_msg = "No VPN config found. Create one first with create_vpn_config_template"
                    logger.warning(f"[{request_id}] {error_msg}")
                    log_tool_result(name, False, request_id, error_msg)
                    duration = time.time() - start_time
                    record_tool_call(name, False, duration)
                    return [TextContent(type="text", text=json.dumps({"error": error_msg}, indent=2))]
            result = setup_networkmanager_connection(config_path)
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Network Mapping
        if name == "create_network_map":
            networks = arguments.get("networks")
            scan_networks = arguments.get("scan_networks", True)
            test_configured_devices = arguments.get("test_configured_devices", True)
            max_hosts = arguments.get("max_hosts_per_network", 254)
            
            network_map = create_network_map(networks, scan_networks, test_configured_devices, max_hosts)
            visualization = generate_network_map_visualization(network_map, format="text")
            
            result = {
                "network_map": network_map,
                "visualization": visualization
            }
            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

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
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

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
                    "available_topics": ["all", "tools", "resources", "workflows", "troubleshooting", "examples", "configuration"]
                }

            _record_tool_result(name, result, request_id, start_time)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

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
            result = batch_operation(device_ids, operation, **{k: v for k, v in arguments.items() if k not in ["device_ids", "operation"]})
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
            e,
            context={
                "tool_name": name,
                "arguments": arguments,
                "request_id": request_id
            }
        )
        error_response["tool"] = name
        error_response["request_id"] = request_id
        logger.error(f"[{request_id}] Tool execution failed: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

