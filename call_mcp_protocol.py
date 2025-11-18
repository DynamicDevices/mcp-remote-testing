#!/usr/bin/env python3
"""Call MCP tool through the actual MCP protocol using the MCP client SDK"""
import asyncio
import sys
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("Error: MCP client SDK not available")
    sys.exit(1)

async def call_mcp_tool():
    """Call create_network_map tool via MCP protocol"""
    server_script = Path(__file__).parent / "lab_testing" / "server.py"
    project_root = Path(__file__).parent
    
    # Set up server parameters with PYTHONPATH
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_script)],
        env=env
    )
    
    print("Connecting to MCP server via stdio protocol...")
    print("="*70)
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            # Call the tool
            print("\nCalling create_network_map tool...")
            result = await session.call_tool(
                "create_network_map",
                {
                    "quick_mode": True,
                    "scan_networks": False,
                    "test_configured_devices": True
                }
            )
            
            print(f"\nTool returned {len(result.content)} content item(s):\n")
            
            # Display results
            for i, content in enumerate(result.content, 1):
                if hasattr(content, 'text'):
                    if content.text.startswith('```mermaid'):
                        print(f"Content {i}: Mermaid Diagram")
                        print("="*70)
                        print(content.text)
                        print("="*70)
                    else:
                        print(f"Content {i}: Text")
                        print(content.text)
                elif hasattr(content, 'data'):
                    print(f"Content {i}: Image")
                    print(f"  MIME Type: {content.mimeType}")
                    print(f"  Data length: {len(content.data)} bytes")
            
            return result

if __name__ == "__main__":
    try:
        result = asyncio.run(call_mcp_tool())
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
