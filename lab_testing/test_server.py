#!/usr/bin/env python3
"""
Test script for MCP server components

Run this to verify the server components work before integrating with Cursor.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import sys

from lab_testing.utils.logger import get_logger

logger = get_logger()


def test_imports():
    """Test that all modules can be imported"""
    logger.info("Testing imports...")
    try:
        # Test imports (imported but not used - that's OK for import tests)
        from lab_testing.config import validate_config
        from lab_testing.resources.device_inventory import get_device_inventory
        from lab_testing.resources.network_status import get_network_status
        from lab_testing.tools.device_manager import list_devices, test_device
        from lab_testing.tools.power_monitor import get_power_logs
        from lab_testing.tools.tasmota_control import list_tasmota_devices
        from lab_testing.tools.vpn_manager import get_vpn_status

        logger.info("✓ All imports successful")
        return True
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False


def test_config():
    """Test configuration validation"""
    print("\nTesting configuration...")
    try:
        from lab_testing.config import get_lab_devices_config, validate_config

        is_valid, errors = validate_config()
        if is_valid:
            print("✓ Configuration valid")
            print(f"  Lab devices config: {get_lab_devices_config()}")
            return True
        print("✗ Configuration invalid:")
        for error in errors:
            print(f"  - {error}")
        return False
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False


def test_tools():
    """Test tool functions"""
    logger.info("\nTesting tools...")

    # Test list_devices
    try:
        from lab_testing.tools.device_manager import list_devices

        result = list_devices()
        logger.info(f"✓ list_devices: Found {result.get('total_devices', 0)} devices")
        logger.info(f"  Summary: {result.get('summary', 'N/A')}")
    except Exception as e:
        logger.error(f"✗ list_devices failed: {e}")
        return False

    # Test VPN status
    try:
        from lab_testing.tools.vpn_manager import get_vpn_status

        result = get_vpn_status()
        connected = result.get("connected", False)
        logger.info(f"✓ vpn_status: VPN {'connected' if connected else 'disconnected'}")
    except Exception as e:
        logger.error(f"✗ vpn_status failed: {e}")
        return False

    # Test Tasmota list
    try:
        from lab_testing.tools.tasmota_control import list_tasmota_devices

        result = list_tasmota_devices()
        if result.get("success"):
            count = result.get("count", 0)
            logger.info(f"✓ list_tasmota_devices: Found {count} Tasmota devices")
        else:
            logger.warning(f"⚠ list_tasmota_devices: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"✗ list_tasmota_devices failed: {e}")
        return False

    return True


def test_resources():
    """Test resource providers"""
    print("\nTesting resources...")

    try:
        from lab_testing.resources.device_inventory import get_device_inventory

        inventory = get_device_inventory()
        if "error" in inventory:
            print(f"⚠ device_inventory: {inventory['error']}")
        else:
            device_count = len(inventory.get("devices", {}))
            print(f"✓ device_inventory: Loaded {device_count} devices")
    except Exception as e:
        print(f"✗ device_inventory failed: {e}")
        return False

    try:
        from lab_testing.resources.network_status import get_network_status

        status = get_network_status()
        print("✓ network_status: Status retrieved")
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
        from mcp.types import EmbeddedResource, TextContent, Tool

        print("✓ MCP SDK imports successful (standard structure)")
        return True
    except ImportError:
        try:
            from mcp import Server
            from mcp.stdio import stdio_server
            from mcp.types import EmbeddedResource, TextContent, Tool

            print("✓ MCP SDK imports successful (alternative structure)")
            return True
        except ImportError:
            print("⚠ MCP SDK not found (expected if not installed)")
            print(
                "  Install with: pip3 install git+https://github.com/modelcontextprotocol/python-sdk.git"
            )
            return True  # Don't fail test if SDK not installed


def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("MCP Server Component Tests")
    logger.info("=" * 60)

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
    print("Some tests failed. Please fix issues before integrating.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
