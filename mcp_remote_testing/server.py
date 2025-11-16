#!/usr/bin/env python3
"""
Lab Testing MCP Server

Model Context Protocol server for remote embedded hardware development and testing.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# MCP SDK imports
# Note: MCP SDK structure may vary - adjust imports based on actual SDK version
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
except ImportError:
    try:
        # Alternative import structure
        from mcp import Server
        from mcp.stdio import stdio_server
        from mcp.types import Tool, TextContent, EmbeddedResource
    except ImportError:
        print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
        print("Note: You may need to install from: https://github.com/modelcontextprotocol/python-sdk", file=sys.stderr)
        sys.exit(1)

# Local imports
from mcp_remote_testing.config import validate_config
from mcp_remote_testing.tools.device_manager import list_devices, test_device, ssh_to_device
from mcp_remote_testing.tools.vpn_manager import connect_vpn, disconnect_vpn, get_vpn_status
from mcp_remote_testing.tools.power_monitor import start_power_monitoring, get_power_logs
from mcp_remote_testing.tools.tasmota_control import tasmota_control, list_tasmota_devices
from mcp_remote_testing.tools.ota_manager import (
    check_ota_status, trigger_ota_update, list_containers,
    deploy_container, get_system_status
)
from mcp_remote_testing.tools.batch_operations import batch_operation, regression_test, get_device_groups
from mcp_remote_testing.tools.power_analysis import analyze_power_logs, monitor_low_power, compare_power_profiles
from mcp_remote_testing.resources.device_inventory import get_device_inventory
from mcp_remote_testing.resources.network_status import get_network_status
from mcp_remote_testing.resources.help import get_help_content

try:
    from mcp_remote_testing.version import __version__
except ImportError:
    __version__ = "0.1.0"

# Initialize MCP server
server = Server("lab-testing-mcp")


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="list_devices",
            description="List all configured lab devices with their status, IP addresses, and device types",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="test_device",
            description="Test connectivity to a specific lab device by device ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier from the device inventory"
                    }
                },
                "required": ["device_id"]
            }
        ),
        Tool(
            name="ssh_to_device",
            description="Execute an SSH command on a lab device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier from the device inventory"
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to execute via SSH"
                    },
                    "username": {
                        "type": "string",
                        "description": "SSH username (optional, uses device default if not specified)"
                    }
                },
                "required": ["device_id", "command"]
            }
        ),
        Tool(
            name="vpn_status",
            description="Get current WireGuard VPN connection status",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="connect_vpn",
            description="Connect to WireGuard VPN for lab network access",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="disconnect_vpn",
            description="Disconnect from WireGuard VPN",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="start_power_monitoring",
            description="Start a power monitoring session for a device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Target device ID (optional, uses DMM default if not specified)"
                    },
                    "test_name": {
                        "type": "string",
                        "description": "Name for this test session"
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Duration in seconds (optional, runs until stopped)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_power_logs",
            description="Get recent power monitoring log files",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type": "string",
                        "description": "Filter by test name (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of log files to return",
                        "default": 10
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="tasmota_control",
            description="Control a Tasmota power switch device (on, off, toggle, status, energy)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Tasmota device ID"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["on", "off", "toggle", "status", "energy"],
                        "description": "Action to perform"
                    }
                },
                "required": ["device_id", "action"]
            }
        ),
        Tool(
            name="list_tasmota_devices",
            description="List all configured Tasmota devices",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
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
                        "enum": ["all", "tools", "resources", "workflows", "troubleshooting", "examples"]
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="check_ota_status",
            description="Check Foundries.io OTA update status for a device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier"
                    }
                },
                "required": ["device_id"]
            }
        ),
        Tool(
            name="trigger_ota_update",
            description="Trigger Foundries.io OTA update for a device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier"
                    },
                    "target": {
                        "type": "string",
                        "description": "Target to update to (optional, uses device default)"
                    }
                },
                "required": ["device_id"]
            }
        ),
        Tool(
            name="list_containers",
            description="List Docker containers on a device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier"
                    }
                },
                "required": ["device_id"]
            }
        ),
        Tool(
            name="deploy_container",
            description="Deploy/update a container on a device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier"
                    },
                    "container_name": {
                        "type": "string",
                        "description": "Container name"
                    },
                    "image": {
                        "type": "string",
                        "description": "Container image to deploy"
                    }
                },
                "required": ["device_id", "container_name", "image"]
            }
        ),
        Tool(
            name="get_system_status",
            description="Get comprehensive system status (uptime, load, memory, disk, kernel)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier"
                    }
                },
                "required": ["device_id"]
            }
        ),
        Tool(
            name="batch_operation",
            description="Execute operation on multiple devices (for racks/regression testing)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of device identifiers"
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["test", "ssh", "ota_check", "system_status", "list_containers"],
                        "description": "Operation to perform"
                    },
                    "command": {
                        "type": "string",
                        "description": "Command for SSH operation (required if operation=ssh)"
                    },
                    "username": {
                        "type": "string",
                        "description": "SSH username (optional)"
                    }
                },
                "required": ["device_ids", "operation"]
            }
        ),
        Tool(
            name="regression_test",
            description="Run regression test sequence on multiple devices",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_group": {
                        "type": "string",
                        "description": "Device group/tag to test (optional)"
                    },
                    "device_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific device IDs to test (optional)"
                    },
                    "test_sequence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of test operations (default: test, system_status, ota_check)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_device_groups",
            description="Get devices organized by groups/tags (for rack management)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="analyze_power_logs",
            description="Analyze power logs for low power characteristics and suspend/resume detection",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type": "string",
                        "description": "Filter by test name (optional)"
                    },
                    "device_id": {
                        "type": "string",
                        "description": "Filter by device (optional)"
                    },
                    "threshold_mw": {
                        "type": "number",
                        "description": "Power threshold in mW for low power detection (optional)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="monitor_low_power",
            description="Monitor device for low power consumption",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device identifier"
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Monitoring duration in seconds",
                        "default": 300
                    },
                    "threshold_mw": {
                        "type": "number",
                        "description": "Low power threshold in mW",
                        "default": 100.0
                    },
                    "sample_rate": {
                        "type": "number",
                        "description": "Sampling rate in Hz",
                        "default": 1.0
                    }
                },
                "required": ["device_id"]
            }
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
                        "description": "List of test names to compare"
                    },
                    "device_id": {
                        "type": "string",
                        "description": "Optional device filter"
                    }
                },
                "required": ["test_names"]
            }
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool execution requests"""

    try:
        if name == "list_devices":
            result = list_devices()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "test_device":
            device_id = arguments.get("device_id")
            if not device_id:
                return [TextContent(type="text", text=json.dumps({"error": "device_id is required"}, indent=2))]
            result = test_device(device_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "ssh_to_device":
            device_id = arguments.get("device_id")
            command = arguments.get("command")
            username = arguments.get("username")

            if not device_id or not command:
                return [TextContent(type="text", text=json.dumps({"error": "device_id and command are required"}, indent=2))]

            result = ssh_to_device(device_id, command, username)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "vpn_status":
            result = get_vpn_status()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "connect_vpn":
            result = connect_vpn()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "disconnect_vpn":
            result = disconnect_vpn()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "start_power_monitoring":
            device_id = arguments.get("device_id")
            test_name = arguments.get("test_name")
            duration = arguments.get("duration")
            result = start_power_monitoring(device_id, test_name, duration)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_power_logs":
            test_name = arguments.get("test_name")
            limit = arguments.get("limit", 10)
            result = get_power_logs(test_name, limit)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "tasmota_control":
            device_id = arguments.get("device_id")
            action = arguments.get("action")

            if not device_id or not action:
                return [TextContent(type="text", text=json.dumps({"error": "device_id and action are required"}, indent=2))]

            result = tasmota_control(device_id, action)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_tasmota_devices":
            result = list_tasmota_devices()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "help":
            topic = arguments.get("topic", "all")
            help_content = get_help_content()
            
            if topic == "all":
                return [TextContent(type="text", text=json.dumps(help_content, indent=2))]
            elif topic in help_content:
                return [TextContent(type="text", text=json.dumps({topic: help_content[topic]}, indent=2))]
            else:
                return [TextContent(type="text", text=json.dumps({
                    "error": f"Unknown topic: {topic}",
                    "available_topics": ["all", "tools", "resources", "workflows", "troubleshooting", "examples", "configuration"]
                }, indent=2))]
        
        elif name == "check_ota_status":
            device_id = arguments.get("device_id")
            if not device_id:
                return [TextContent(type="text", text=json.dumps({"error": "device_id is required"}, indent=2))]
            result = check_ota_status(device_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "trigger_ota_update":
            device_id = arguments.get("device_id")
            target = arguments.get("target")
            if not device_id:
                return [TextContent(type="text", text=json.dumps({"error": "device_id is required"}, indent=2))]
            result = trigger_ota_update(device_id, target)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "list_containers":
            device_id = arguments.get("device_id")
            if not device_id:
                return [TextContent(type="text", text=json.dumps({"error": "device_id is required"}, indent=2))]
            result = list_containers(device_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "deploy_container":
            device_id = arguments.get("device_id")
            container_name = arguments.get("container_name")
            image = arguments.get("image")
            if not all([device_id, container_name, image]):
                return [TextContent(type="text", text=json.dumps({"error": "device_id, container_name, and image are required"}, indent=2))]
            result = deploy_container(device_id, container_name, image)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_system_status":
            device_id = arguments.get("device_id")
            if not device_id:
                return [TextContent(type="text", text=json.dumps({"error": "device_id is required"}, indent=2))]
            result = get_system_status(device_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "batch_operation":
            device_ids = arguments.get("device_ids", [])
            operation = arguments.get("operation")
            if not device_ids or not operation:
                return [TextContent(type="text", text=json.dumps({"error": "device_ids and operation are required"}, indent=2))]
            result = batch_operation(device_ids, operation, **{k: v for k, v in arguments.items() if k not in ["device_ids", "operation"]})
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "regression_test":
            device_group = arguments.get("device_group")
            device_ids = arguments.get("device_ids")
            test_sequence = arguments.get("test_sequence")
            result = regression_test(device_group, device_ids, test_sequence)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_device_groups":
            result = get_device_groups()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "analyze_power_logs":
            test_name = arguments.get("test_name")
            device_id = arguments.get("device_id")
            threshold_mw = arguments.get("threshold_mw")
            result = analyze_power_logs(test_name, device_id, threshold_mw)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "monitor_low_power":
            device_id = arguments.get("device_id")
            duration = arguments.get("duration", 300)
            threshold_mw = arguments.get("threshold_mw", 100.0)
            sample_rate = arguments.get("sample_rate", 1.0)
            if not device_id:
                return [TextContent(type="text", text=json.dumps({"error": "device_id is required"}, indent=2))]
            result = monitor_low_power(device_id, duration, threshold_mw, sample_rate)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "compare_power_profiles":
            test_names = arguments.get("test_names", [])
            device_id = arguments.get("device_id")
            if not test_names:
                return [TextContent(type="text", text=json.dumps({"error": "test_names is required"}, indent=2))]
            result = compare_power_profiles(test_names, device_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"Tool execution failed: {str(e)}"}, indent=2))]


@server.list_resources()
async def handle_list_resources() -> List[EmbeddedResource]:
    """List all available resources"""
    return [
        EmbeddedResource(
            uri="device://inventory",
            name="Device Inventory",
            description="Complete inventory of all configured lab devices",
            mimeType="application/json"
        ),
        EmbeddedResource(
            uri="network://status",
            name="Network Status",
            description="Current network and VPN connection status",
            mimeType="application/json"
        ),
        EmbeddedResource(
            uri="config://lab_devices",
            name="Lab Devices Configuration",
            description="Raw lab devices configuration file",
            mimeType="application/json"
        ),
        EmbeddedResource(
            uri="help://usage",
            name="Help and Usage Documentation",
            description="Complete help documentation, usage examples, and best practices",
            mimeType="application/json"
        ),
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Handle resource read requests"""

    if uri == "device://inventory":
        inventory = get_device_inventory()
        return json.dumps(inventory, indent=2)

    elif uri == "network://status":
        status = get_network_status()
        return json.dumps(status, indent=2)

    elif uri == "config://lab_devices":
        from config import get_lab_devices_config
        config_path = get_lab_devices_config()
        try:
            with open(config_path, 'r') as f:
                return f.read()
        except Exception as e:
            return json.dumps({"error": f"Failed to read config: {str(e)}"}, indent=2)
    
    elif uri == "help://usage":
        help_content = get_help_content()
        return json.dumps(help_content, indent=2)
    
    else:
        return json.dumps({"error": f"Unknown resource: {uri}"}, indent=2)


async def main():
    """Main entry point for the MCP server"""
    # Validate configuration
    is_valid, errors = validate_config()
    if not is_valid:
        print("Configuration validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("\nNote: Some features may not work without proper configuration.", file=sys.stderr)

    # Run the server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

