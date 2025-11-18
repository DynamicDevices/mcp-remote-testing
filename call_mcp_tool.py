#!/usr/bin/env python3
"""Call MCP tool directly using the same handler as the MCP server"""
import sys
import time

from mcp.types import ImageContent, TextContent

from lab_testing.server.tool_handlers import handle_tool

# Simulate MCP tool call exactly as the server would receive it
request_id = "mcp_request_001"
start_time = time.time()
arguments = {"quick_mode": True, "scan_networks": False, "test_configured_devices": True}

print("Calling create_network_map via MCP tool handler...")
print("=" * 70)

# Call the tool handler (same code path as MCP server uses)
result = handle_tool("create_network_map", arguments, request_id, start_time)

print(f"Returned {len(result)} content item(s):\n")

# Format output as MCP would return it
for i, content in enumerate(result, 1):
    if isinstance(content, TextContent):
        if content.text.startswith("```mermaid"):
            print(f"Content {i}: TextContent (Mermaid Diagram)")
            print("=" * 70)
            print(content.text)
            print("=" * 70)
        else:
            print(f"Content {i}: TextContent")
            print(content.text)
    elif isinstance(content, ImageContent):
        print(f"Content {i}: ImageContent")
        print(f"  MIME Type: {content.mimeType}")
        print(f"  Data length: {len(content.data)} bytes (base64)")
