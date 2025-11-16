#!/usr/bin/env python3
"""
Test script for MCP server components

Run this to verify the server components work before integrating with Cursor.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import sys
from pathlib import Path

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        from mcp_remote_testing.config import validate_config
        from mcp_remote_testing.tools.device_manager import list_devices, test_device
        from mcp_remote_testing.tools.vpn_manager import get_vpn_status
        from mcp_remote_testing.tools.power_monitor import get_power_logs
        from mcp_remote_testing.tools.tasmota_control import list_tasmota_devices
        from mcp_remote_testing.resources.device_inventory import get_device_inventory
        from mcp_remote_testing.resources.network_status import get_network_status
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_config():
    """Test configuration validation"""
    print("\nTesting configuration...")
    try:
        from mcp_remote_testing.config import validate_config, get_lab_devices_config
        is_valid, errors = validate_config()
        if is_valid:
            print("✓ Configuration valid")
            print(f"  Lab devices config: {get_lab_devices_config()}")
            return True
        else:
            print("✗ Configuration invalid:")
            for error in errors:
                print(f"  - {error}")
            return False
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_tools():
    """Test tool functions"""
    print("\nTesting tools...")

    # Test list_devices
    try:
        from mcp_remote_testing.tools.device_manager import list_devices
        result = list_devices()
        print(f"✓ list_devices: Found {result.get('total_devices', 0)} devices")
        print(f"  Summary: {result.get('summary', 'N/A')}")
    except Exception as e:
        print(f"✗ list_devices failed: {e}")
        return False
    
    # Test VPN status
    try:
        from mcp_remote_testing.tools.vpn_manager import get_vpn_status
        result = get_vpn_status()
        connected = result.get('connected', False)
        print(f"✓ vpn_status: VPN {'connected' if connected else 'disconnected'}")
    except Exception as e:
        print(f"✗ vpn_status failed: {e}")
        return False
    
    # Test Tasmota list
    try:
        from mcp_remote_testing.tools.tasmota_control import list_tasmota_devices
        result = list_tasmota_devices()
        if result.get('success'):
            count = result.get('count', 0)
            print(f"✓ list_tasmota_devices: Found {count} Tasmota devices")
        else:
            print(f"⚠ list_tasmota_devices: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"✗ list_tasmota_devices failed: {e}")
        return False

    return True

def test_resources():
    """Test resource providers"""
    print("\nTesting resources...")

    try:
        from mcp_remote_testing.resources.device_inventory import get_device_inventory
        inventory = get_device_inventory()
        if 'error' in inventory:
            print(f"⚠ device_inventory: {inventory['error']}")
        else:
            device_count = len(inventory.get('devices', {}))
            print(f"✓ device_inventory: Loaded {device_count} devices")
    except Exception as e:
        print(f"✗ device_inventory failed: {e}")
        return False
    
    try:
        from mcp_remote_testing.resources.network_status import get_network_status
        status = get_network_status()
        print(f"✓ network_status: Status retrieved")
    except Exception as e:
        print(f"✗ network_status failed: {e}")
        return False

    return True

def test_mcp_sdk():
    """Test MCP SDK availability"""
    print("\nTesting MCP SDK...")

    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent, EmbeddedResource
        print("✓ MCP SDK imports successful (standard structure)")
        return True
    except ImportError:
        try:
            from mcp import Server
            from mcp.stdio import stdio_server
            from mcp.types import Tool, TextContent, EmbeddedResource
            print("✓ MCP SDK imports successful (alternative structure)")
            return True
        except ImportError:
            print("⚠ MCP SDK not found (expected if not installed)")
            print("  Install with: pip3 install git+https://github.com/modelcontextprotocol/python-sdk.git")
            return True  # Don't fail test if SDK not installed

def main():
    """Run all tests"""
    print("=" * 60)
    print("MCP Server Component Tests")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Tools", test_tools()))
    results.append(("Resources", test_resources()))
    results.append(("MCP SDK", test_mcp_sdk()))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("All tests passed! Server is ready for integration.")
        return 0
    else:
        print("Some tests failed. Please fix issues before integrating.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

