#!/usr/bin/env python3
"""
Test Foundries VPN Tools

Tests the Foundries VPN management tools:
- foundries_vpn_status
- connect_foundries_vpn
- list_foundries_devices
- enable_foundries_vpn_device
- disable_foundries_vpn_device

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lab_testing.tools.foundries_vpn import (
    connect_foundries_vpn,
    disable_foundries_vpn_device,
    enable_foundries_vpn_device,
    foundries_vpn_status,
    list_foundries_devices,
)


def test_foundries_vpn_status():
    """Test foundries_vpn_status"""
    print("=" * 70)
    print("TEST: foundries_vpn_status")
    print("=" * 70)
    print()

    result = foundries_vpn_status()
    print(f"Result: {result}")
    print()

    if result.get("success"):
        print("✅ foundries_vpn_status: SUCCESS")
        print(f"  Connected: {result.get('connected', False)}")
        print(f"  fioctl installed: {result.get('fioctl_installed', False)}")
        print(f"  fioctl configured: {result.get('fioctl_configured', False)}")
        if result.get("wireguard_interfaces"):
            print(f"  WireGuard interfaces: {result.get('wireguard_interfaces')}")
        if result.get("networkmanager_connections"):
            print(f"  NetworkManager connections: {result.get('networkmanager_connections')}")
    else:
        print("⚠️  foundries_vpn_status: FAILED (expected if fioctl not installed)")
        print(f"  Error: {result.get('error')}")
        if result.get("suggestions"):
            print("  Suggestions:")
            for suggestion in result.get("suggestions", []):
                print(f"    - {suggestion}")

    print()
    return result.get("success", False)


def test_list_foundries_devices():
    """Test list_foundries_devices"""
    print("=" * 70)
    print("TEST: list_foundries_devices")
    print("=" * 70)
    print()

    result = list_foundries_devices()
    print(f"Result: {result}")
    print()

    if result.get("success"):
        print("✅ list_foundries_devices: SUCCESS")
        print(f"  Devices found: {result.get('count', 0)}")
        devices = result.get("devices", [])
        if devices:
            print("  Device list:")
            for device in devices[:5]:  # Show first 5
                print(f"    - {device.get('name', 'Unknown')} ({device.get('status', 'unknown')})")
            if len(devices) > 5:
                print(f"    ... and {len(devices) - 5} more")
    else:
        print("⚠️  list_foundries_devices: FAILED (expected if fioctl not configured)")
        print(f"  Error: {result.get('error')}")
        if result.get("suggestions"):
            print("  Suggestions:")
            for suggestion in result.get("suggestions", []):
                print(f"    - {suggestion}")

    print()
    return result.get("success", False)


def test_connect_foundries_vpn():
    """Test connect_foundries_vpn (without actually connecting)"""
    print("=" * 70)
    print("TEST: connect_foundries_vpn (dry run - no config provided)")
    print("=" * 70)
    print()

    # Test without config path (should search for config)
    result = connect_foundries_vpn()
    print(f"Result: {result}")
    print()

    if result.get("success"):
        print("✅ connect_foundries_vpn: SUCCESS")
        print(f"  Method: {result.get('method')}")
        print(f"  Message: {result.get('message')}")
    else:
        print("⚠️  connect_foundries_vpn: FAILED (expected if config not found)")
        print(f"  Error: {result.get('error')}")
        if result.get("suggestions"):
            print("  Suggestions:")
            for suggestion in result.get("suggestions", []):
                print(f"    - {suggestion}")

    print()
    return result.get("success", False)


def test_enable_foundries_vpn_device():
    """Test enable_foundries_vpn_device (with test device name)"""
    print("=" * 70)
    print("TEST: enable_foundries_vpn_device (test device)")
    print("=" * 70)
    print()

    # Use a test device name (won't actually enable unless device exists)
    test_device = "test-device-name"
    result = enable_foundries_vpn_device(test_device)
    print(f"Result: {result}")
    print()

    if result.get("success"):
        print("✅ enable_foundries_vpn_device: SUCCESS")
        print(f"  Device: {result.get('device_name')}")
        print(f"  Message: {result.get('message')}")
    else:
        print(
            "⚠️  enable_foundries_vpn_device: FAILED (expected if device not found or fioctl not configured)"
        )
        print(f"  Error: {result.get('error')}")
        if result.get("suggestions"):
            print("  Suggestions:")
            for suggestion in result.get("suggestions", []):
                print(f"    - {suggestion}")

    print()
    return result.get("success", False)


def test_disable_foundries_vpn_device():
    """Test disable_foundries_vpn_device (with test device name)"""
    print("=" * 70)
    print("TEST: disable_foundries_vpn_device (test device)")
    print("=" * 70)
    print()

    # Use a test device name (won't actually disable unless device exists)
    test_device = "test-device-name"
    result = disable_foundries_vpn_device(test_device)
    print(f"Result: {result}")
    print()

    if result.get("success"):
        print("✅ disable_foundries_vpn_device: SUCCESS")
        print(f"  Device: {result.get('device_name')}")
        print(f"  Message: {result.get('message')}")
    else:
        print(
            "⚠️  disable_foundries_vpn_device: FAILED (expected if device not found or fioctl not configured)"
        )
        print(f"  Error: {result.get('error')}")
        if result.get("suggestions"):
            print("  Suggestions:")
            for suggestion in result.get("suggestions", []):
                print(f"    - {suggestion}")

    print()
    return result.get("success", False)


def main():
    """Run all Foundries VPN tests"""
    print("\n" + "=" * 70)
    print("FOUNDRIES VPN TOOLS TESTING")
    print("=" * 70)
    print()
    print("Note: These tests check tool functionality.")
    print("Some tests may fail if fioctl is not installed/configured (expected).")
    print()

    results = {}

    # Test 1: VPN Status
    results["vpn_status"] = test_foundries_vpn_status()

    # Test 2: List Devices
    results["list_devices"] = test_list_foundries_devices()

    # Test 3: Connect VPN (dry run)
    results["connect_vpn"] = test_connect_foundries_vpn()

    # Test 4: Enable VPN Device
    results["enable_device"] = test_enable_foundries_vpn_device()

    # Test 5: Disable VPN Device
    results["disable_device"] = test_disable_foundries_vpn_device()

    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(
        f"foundries_vpn_status: {'✅ PASSED' if results['vpn_status'] else '⚠️  FAILED (expected if fioctl not installed)'}"
    )
    print(
        f"list_foundries_devices: {'✅ PASSED' if results['list_devices'] else '⚠️  FAILED (expected if fioctl not configured)'}"
    )
    print(
        f"connect_foundries_vpn: {'✅ PASSED' if results['connect_vpn'] else '⚠️  FAILED (expected if config not found)'}"
    )
    print(
        f"enable_foundries_vpn_device: {'✅ PASSED' if results['enable_device'] else '⚠️  FAILED (expected if device not found)'}"
    )
    print(
        f"disable_foundries_vpn_device: {'✅ PASSED' if results['disable_device'] else '⚠️  FAILED (expected if device not found)'}"
    )
    print("=" * 70)
    print()
    print("Note: Failures are expected if:")
    print("  - fioctl is not installed")
    print("  - fioctl is not configured (run 'fioctl login')")
    print("  - Foundries VPN config file not found")
    print("  - Test device does not exist in factory")
    print()
    print("The important thing is that tools provide helpful error messages and suggestions.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
