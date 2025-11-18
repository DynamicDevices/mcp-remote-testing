#!/usr/bin/env python3
"""
Lab Testing MCP Server

Model Context Protocol server for remote embedded hardware development and testing.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later

Maintainer: Alex J Lennon <ajlennon@dynamicdevices.co.uk>
"""

import asyncio
import json
import sys
import time
import uuid
from typing import Any, Dict, List, Union

# MCP SDK imports
# Note: MCP SDK structure may vary - adjust imports based on actual SDK version
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        EmbeddedResource,
        ImageContent,
        TextContent,
        TextResourceContents,
        Tool,
    )
except ImportError:
    try:
        # Alternative import structure
        from mcp import Server
        from mcp.stdio import stdio_server
        from mcp.types import EmbeddedResource, TextContent, Tool
    except ImportError:
        print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
        print(
            "Note: You may need to install from: https://github.com/modelcontextprotocol/python-sdk",
            file=sys.stderr,
        )
        sys.exit(1)

# Local imports
from lab_testing.config import validate_config
from lab_testing.resources.device_inventory import get_device_inventory
from lab_testing.resources.health import get_health_status, record_tool_call
from lab_testing.resources.help import get_help_content
from lab_testing.utils.logger import get_logger, log_tool_call, log_tool_result, setup_logger

try:
    from lab_testing.version import __version__
except ImportError:
    __version__ = "0.1.0"

# Initialize logger
setup_logger()
logger = get_logger()

# Development mode: Set up auto-reload
try:
    from lab_testing.server.dev_reload import setup_auto_reload

    setup_auto_reload()
except ImportError:
    pass  # dev_reload module not available

# Initialize MCP server
server = Server("ai-lab-testing")


def _record_tool_result(name: str, result: Dict[str, Any], request_id: str, start_time: float):
    """Helper to record tool result and metrics"""
    success = result.get("success", False)
    error = result.get("error")
    duration = time.time() - start_time
    log_tool_result(name, success, request_id, error)
    record_tool_call(name, success, duration)


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List all available tools"""
    logger.debug("Listing tools")
    from lab_testing.server.tool_definitions import get_all_tools

    return get_all_tools()


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any]
) -> List[Union[TextContent, ImageContent]]:
    """Handle tool execution requests"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    log_tool_call(name, arguments, request_id)
    logger.debug(f"[{request_id}] Executing tool: {name}")

    # Route to tool handlers
    from lab_testing.server.tool_handlers import handle_tool

    return handle_tool(name, arguments, request_id, start_time)


@server.list_resources()
async def handle_list_resources() -> List[EmbeddedResource]:
    """List all available resources"""
    logger.debug("Listing resources")

    # For listing, we provide minimal content - full content is fetched via read_resource
    resources = [
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri="device://inventory",
                text="",  # Content fetched on-demand via read_resource
                mimeType="application/json",
            ),
        ),
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri="network://status",
                text="",  # Content fetched on-demand via read_resource
                mimeType="application/json",
            ),
        ),
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri="config://lab_devices",
                text="",  # Content fetched on-demand via read_resource
                mimeType="application/json",
            ),
        ),
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri="help://usage",
                text="",  # Content fetched on-demand via read_resource
                mimeType="application/json",
            ),
        ),
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri="health://status",
                text="",  # Content fetched on-demand via read_resource
                mimeType="application/json",
            ),
        ),
    ]
    return resources


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Handle resource read requests"""
    logger.debug(f"Reading resource: {uri}")

    if uri == "device://inventory":
        inventory = get_device_inventory()
        return json.dumps(inventory, indent=2)

    if uri == "network://status":
        from lab_testing.resources.network_status import get_network_status

        status = get_network_status()
        return json.dumps(status, indent=2)

    if uri == "config://lab_devices":
        from lab_testing.config import get_lab_devices_config

        config_path = get_lab_devices_config()
        try:
            with open(config_path) as f:
                return f.read()
        except Exception as e:
            return json.dumps({"error": f"Failed to read config: {e!s}"}, indent=2)

    if uri == "help://usage":
        help_content = get_help_content()
        return json.dumps(help_content, indent=2)

    if uri == "health://status":
        logger.debug("Reading health status resource")
        health_status = get_health_status()
        return json.dumps(health_status, indent=2)

    logger.warning(f"Unknown resource requested: {uri}")
    return json.dumps({"error": f"Unknown resource: {uri}"}, indent=2)


async def main():
    """Main entry point for the MCP server"""
    # Validate configuration
    is_valid, errors = validate_config()
    if not is_valid:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.warning("Some features may not work without proper configuration.")
    else:
        logger.info("Configuration validated successfully")

    # Run the server using stdio transport
    logger.info(f"MCP Server starting (version {__version__})")
    logger.info("Server ready, waiting for requests...")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
