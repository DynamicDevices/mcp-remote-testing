"""
Tool Definitions for MCP Server

Contains all Tool schema definitions for the MCP server.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

from typing import List

from mcp.types import Tool


def get_all_tools() -> List[Tool]:
    """Get all tool definitions for the MCP server"""
    return [
        Tool(
            name="list_devices",
            description=(
                "List all devices on the target network with their status, firmware, and relationships. "
                "Supports filtering by type, status, SSH status, power state, and search queries. "
                "Includes summary statistics. Supports sorting and limiting results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "device_type_filter": {
                        "type": "string",
                        "description": "Filter by device type (e.g., 'tasmota_device', 'eink_board', 'test_equipment', 'sentai_board')",
                    },
                    "status_filter": {
                        "type": "string",
                        "description": "Filter by status (e.g., 'online', 'offline', 'discovered')",
                    },
                    "search_query": {
                        "type": "string",
                        "description": "Search by IP address, hostname, friendly name, or device ID (case-insensitive)",
                    },
                    "show_summary": {
                        "type": "boolean",
                        "description": "Include summary statistics (counts by type/status) in response (default: true)",
                        "default": True,
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Bypass cache and rescan all devices (default: false)",
                        "default": False,
                    },
                    "ssh_status_filter": {
                        "type": "string",
                        "description": "Filter by SSH status (e.g., 'ok', 'error', 'refused', 'timeout', 'unknown')",
                    },
                    "power_state_filter": {
                        "type": "string",
                        "description": "Filter Tasmota devices by power state (e.g., 'on', 'off')",
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort results by field: 'ip', 'friendly_name', 'status', 'last_seen' (default: type then friendly_name)",
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order: 'asc' or 'desc' (default: 'asc')",
                        "enum": ["asc", "desc"],
                        "default": "asc",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of devices to return (default: no limit)",
                        "minimum": 1,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="test_device",
            description=(
                "Test connectivity to a specific lab device. "
                "Checks ping reachability and SSH availability. "
                "Supports both device_id (unique ID) and friendly_name. "
                "Best practice: Use this before running operations on devices. "
                "In DHCP environments, use 'verify_device_identity' to ensure correct device."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier (device_id or friendly_name). Use 'list_devices' to see available options.",
                    }
                },
                "required": ["device_id"],
            },
        ),
        Tool(
            name="ssh_to_device",
            description=(
                "Execute an SSH command on a lab device. "
                "Prefers SSH keys, uses sshpass for passwords if needed. "
                "Supports both device_id and friendly_name. "
                "Best practice: Test device connectivity first with 'test_device'. "
                "In DHCP environments, verify device identity with 'verify_device_identity'. "
                "All commands are tracked for security and debugging."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier (device_id or friendly_name). Use 'list_devices' to see available options.",
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to execute on the device (e.g., 'uptime', 'cat /etc/os-release')",
                    },
                    "username": {
                        "type": "string",
                        "description": "SSH username (optional, uses device default from config)",
                    },
                },
                "required": ["device_id", "command"],
            },
        ),
        Tool(
            name="vpn_status",
            description="Get current WireGuard VPN connection status",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="connect_vpn",
            description="Connect to the WireGuard VPN for lab network access",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="disconnect_vpn",
            description="Disconnect from the WireGuard VPN",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="vpn_setup_instructions",
            description="Get WireGuard VPN setup instructions and check current configuration",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="check_wireguard_installed",
            description="Check if WireGuard tools are installed on the system",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="list_vpn_configs",
            description="List existing WireGuard configuration files",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="create_vpn_config_template",
            description="Create a WireGuard configuration template file",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Path where to save the template (optional, defaults to secrets directory)",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="setup_networkmanager_vpn",
            description="Import WireGuard config into NetworkManager (allows connecting without root)",
            inputSchema={
                "type": "object",
                "properties": {
                    "config_path": {
                        "type": "string",
                        "description": "Path to WireGuard .conf file (optional, uses detected config if not specified)",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="vpn_statistics",
            description="Get detailed WireGuard VPN statistics (transfer data, handshakes, latency)",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="create_network_map",
            description="Create a visual map of running systems on the target network showing what's up and what isn't. Supports multiple layouts, export formats, device grouping, historical tracking, and performance metrics visualization.",
            inputSchema={
                "type": "object",
                "properties": {
                    "networks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Network CIDRs to scan (e.g., ['192.168.1.0/24']). If not provided, uses networks from config",
                    },
                    "scan_networks": {
                        "type": "boolean",
                        "description": "If true, actively scan networks for hosts (default: true)",
                        "default": True,
                    },
                    "test_configured_devices": {
                        "type": "boolean",
                        "description": "If true, test all configured devices (default: true)",
                        "default": True,
                    },
                    "max_hosts_per_network": {
                        "type": "integer",
                        "description": "Maximum hosts to scan per network (default: 254)",
                        "default": 254,
                    },
                    "quick_mode": {
                        "type": "boolean",
                        "description": "If true, skip network scanning and only show configured devices (faster, <5s). Use this if tool calls timeout (default: false)",
                        "default": False,
                    },
                    "layout": {
                        "type": "string",
                        "enum": ["lr", "tb", "radial", "hierarchical", "grid"],
                        "description": "Layout style: 'lr' (left-right, default), 'tb' (top-bottom), 'radial' (circular), 'hierarchical' (tree), 'grid' (grid layout)",
                        "default": "lr",
                    },
                    "group_by": {
                        "type": "string",
                        "enum": ["type", "status", "location", "power_circuit", "none"],
                        "description": "Group devices by: 'type' (device type), 'status' (online/offline), 'location' (physical location from config), 'power_circuit' (power switch), 'none' (no grouping)",
                        "default": "type",
                    },
                    "show_details": {
                        "type": "boolean",
                        "description": "If true, show detailed device information in node labels (firmware, MAC, last seen, etc.)",
                        "default": False,
                    },
                    "show_metrics": {
                        "type": "boolean",
                        "description": "If true, color-code devices by latency and show performance metrics",
                        "default": True,
                    },
                    "show_alerts": {
                        "type": "boolean",
                        "description": "If true, highlight devices with errors, warnings, or issues",
                        "default": True,
                    },
                    "show_history": {
                        "type": "boolean",
                        "description": "If true, show historical status changes and uptime indicators",
                        "default": False,
                    },
                    "export_format": {
                        "type": "string",
                        "enum": ["mermaid", "png", "svg", "pdf", "html", "json", "csv"],
                        "description": "Export format: 'mermaid' (Mermaid diagram, default), 'png' (PNG image), 'svg' (SVG image), 'pdf' (PDF document), 'html' (HTML report), 'json' (JSON data), 'csv' (CSV device list)",
                        "default": "mermaid",
                    },
                    "export_path": {
                        "type": "string",
                        "description": "Optional path to save exported file. If not provided, returns data inline.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="verify_device_identity",
            description="Verify that a device at a given IP matches expected identity by checking hostname/unique ID (important for DHCP)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier (device_id or friendly_name)",
                    },
                    "ip": {
                        "type": "string",
                        "description": "IP address to verify (optional, uses configured IP if not provided)",
                    },
                },
                "required": ["device_id"],
            },
        ),
        Tool(
            name="verify_device_by_ip",
            description="Identify which device (if any) is at a given IP address by checking hostname/unique ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IP address to check"},
                    "username": {
                        "type": "string",
                        "description": "SSH username (default: root)",
                        "default": "root",
                    },
                    "ssh_port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                        "default": 22,
                    },
                },
                "required": ["ip"],
            },
        ),
        Tool(
            name="update_device_ip",
            description="Verify device identity and update IP address in config if device is verified and IP has changed (for DHCP environments)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier (device_id or friendly_name)",
                    },
                    "new_ip": {
                        "type": "string",
                        "description": "New IP address to verify and potentially update",
                    },
                },
                "required": ["device_id", "new_ip"],
            },
        ),
        Tool(
            name="start_power_monitoring",
            description="Start a power monitoring session. Supports both DMM (Digital Multimeter) and Tasmota devices for power measurement",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier - DMM (test_equipment) or Tasmota device (tasmota_device) with energy monitoring (optional)",
                    },
                    "test_name": {
                        "type": "string",
                        "description": "Name for this test session (optional)",
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Monitoring duration in seconds (optional)",
                    },
                    "monitor_type": {
                        "type": "string",
                        "enum": ["dmm", "tasmota"],
                        "description": "Type of monitor to use - 'dmm' (default) or 'tasmota'. Auto-detected from device type if not specified",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_power_logs",
            description="Get recent power monitoring log files",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type": "string",
                        "description": "Filter by test name (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of log files to return",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="tasmota_control",
            description="Control a Tasmota device (power switch, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Tasmota device identifier"},
                    "action": {
                        "type": "string",
                        "enum": ["on", "off", "toggle", "status", "energy"],
                        "description": "Action to perform",
                    },
                },
                "required": ["device_id", "action"],
            },
        ),
        Tool(
            name="list_tasmota_devices",
            description="List all configured Tasmota devices and the devices they control",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="list_test_equipment",
            description="List all test equipment devices (DMM, oscilloscopes, etc.) found on the network. Includes both configured devices and auto-discovered devices.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="query_test_equipment",
            description="Send a SCPI command to test equipment (DMM, etc.) and get the response. Common commands: *IDN? (identify), MEAS:VOLT:DC? (measure DC voltage), MEAS:CURR:DC? (measure DC current)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id_or_ip": {
                        "type": "string",
                        "description": "Device ID from config or IP address of the test equipment",
                    },
                    "scpi_command": {
                        "type": "string",
                        "description": "SCPI command to send (e.g., '*IDN?', 'MEAS:VOLT:DC?')",
                    },
                },
                "required": ["device_id_or_ip", "scpi_command"],
            },
        ),
        Tool(
            name="power_cycle_device",
            description="Power cycle a device by controlling its Tasmota power switch (turns off, waits, then turns on)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier (device_id or friendly_name) to power cycle",
                    },
                    "off_duration": {
                        "type": "integer",
                        "description": "Duration in seconds to keep power off (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["device_id"],
            },
        ),
        Tool(
            name="help",
            description="Get help and usage documentation for the MCP server",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Specific topic (tools, resources, workflows, troubleshooting) or 'all' for complete help",
                        "enum": [
                            "all",
                            "tools",
                            "resources",
                            "workflows",
                            "troubleshooting",
                            "examples",
                        ],
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="check_ota_status",
            description="Check Foundries.io OTA update status for a device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": {"type": "string", "description": "Device identifier"}},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="trigger_ota_update",
            description="Trigger Foundries.io OTA update for a device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Device identifier"},
                    "target": {
                        "type": "string",
                        "description": "Target to update to (optional, uses device default)",
                    },
                },
                "required": ["device_id"],
            },
        ),
        Tool(
            name="list_containers",
            description="List Docker containers on a device",
            inputSchema={
                "type": "object",
                "properties": {"device_id": {"type": "string", "description": "Device identifier"}},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="deploy_container",
            description="Deploy/update a container on a device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Device identifier"},
                    "container_name": {"type": "string", "description": "Container name"},
                    "image": {"type": "string", "description": "Container image to deploy"},
                },
                "required": ["device_id", "container_name", "image"],
            },
        ),
        Tool(
            name="get_system_status",
            description="Get comprehensive system status (uptime, load, memory, disk, kernel)",
            inputSchema={
                "type": "object",
                "properties": {"device_id": {"type": "string", "description": "Device identifier"}},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="get_firmware_version",
            description="Get firmware/OS version information from /etc/os-release",
            inputSchema={
                "type": "object",
                "properties": {"device_id": {"type": "string", "description": "Device identifier"}},
                "required": ["device_id"],
            },
        ),
        Tool(
            name="batch_operation",
            description="Execute operation on multiple devices in parallel (for racks/regression testing)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of device identifiers",
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["test", "ssh", "ota_check", "system_status", "list_containers"],
                        "description": "Operation to perform",
                    },
                    "max_concurrent": {
                        "type": "integer",
                        "description": "Maximum concurrent operations (default: 5)",
                        "default": 5,
                    },
                    "command": {
                        "type": "string",
                        "description": "Command for SSH operation (required if operation=ssh)",
                    },
                    "username": {"type": "string", "description": "SSH username (optional)"},
                },
                "required": ["device_ids", "operation"],
            },
        ),
        Tool(
            name="regression_test",
            description="Run regression test sequence on multiple devices in parallel",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_group": {
                        "type": "string",
                        "description": "Device group/tag to test (optional)",
                    },
                    "device_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific device IDs to test (optional)",
                    },
                    "test_sequence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of test operations (default: test, system_status, ota_check)",
                    },
                    "max_concurrent": {
                        "type": "integer",
                        "description": "Maximum concurrent operations per test (default: 5)",
                        "default": 5,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_device_groups",
            description="Get devices organized by groups/tags (for rack management)",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="analyze_power_logs",
            description="Analyze power logs for low power characteristics and suspend/resume detection",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type": "string",
                        "description": "Filter by test name (optional)",
                    },
                    "device_id": {"type": "string", "description": "Filter by device (optional)"},
                    "threshold_mw": {
                        "type": "number",
                        "description": "Power threshold in mW for low power detection (optional)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="monitor_low_power",
            description="Monitor device for low power consumption",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Device identifier"},
                    "duration": {
                        "type": "integer",
                        "description": "Monitoring duration in seconds",
                        "default": 300,
                    },
                    "threshold_mw": {
                        "type": "number",
                        "description": "Low power threshold in mW",
                        "default": 100.0,
                    },
                    "sample_rate": {
                        "type": "number",
                        "description": "Sampling rate in Hz",
                        "default": 1.0,
                    },
                },
                "required": ["device_id"],
            },
        ),
        Tool(
            name="compare_power_profiles",
            description="Compare power consumption across multiple test runs",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of test names to compare",
                    },
                    "device_id": {"type": "string", "description": "Optional device filter"},
                },
                "required": ["test_names"],
            },
        ),
        Tool(
            name="update_device_friendly_name",
            description="Update the friendly name for a discovered device in the cache. This allows you to use a custom name when referencing devices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "IP address of the device",
                    },
                    "friendly_name": {
                        "type": "string",
                        "description": "New friendly name to set for the device",
                    },
                },
                "required": ["ip", "friendly_name"],
            },
        ),
    ]
