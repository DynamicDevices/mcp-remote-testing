"""
Batch Operations for Multiple Devices
Supports racks of boards for regression testing
"""

import json
from typing import Any, Dict, List, Optional

from mcp_remote_testing.config import get_lab_devices_config


def get_device_groups() -> Dict[str, List[str]]:
    """Get devices organized by groups/tags"""
    try:
        with open(get_lab_devices_config()) as f:
            config = json.load(f)
            devices = config.get("devices", {})

            groups = {}
            for device_id, device_info in devices.items():
                # Group by device type
                device_type = device_info.get("device_type", "other")
                if device_type not in groups:
                    groups[device_type] = []
                groups[device_type].append(device_id)

                # Group by tags if present
                tags = device_info.get("tags", [])
                for tag in tags:
                    if tag not in groups:
                        groups[tag] = []
                    if device_id not in groups[tag]:
                        groups[tag].append(device_id)

            return groups
    except Exception as e:
        return {"error": f"Failed to get device groups: {e!s}"}


def batch_operation(
    device_ids: List[str],
    operation: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute operation on multiple devices.
    
    Args:
        device_ids: List of device identifiers
        operation: Operation to perform (test, ssh, ota_check, etc.)
        **kwargs: Operation-specific parameters
        
    Returns:
        Results for each device
    """
    results = {}

    for device_id in device_ids:
        try:
            if operation == "test":
                from mcp_remote_testing.tools.device_manager import test_device
                results[device_id] = test_device(device_id)
            elif operation == "ssh":
                from mcp_remote_testing.tools.device_manager import ssh_to_device
                command = kwargs.get("command", "")
                username = kwargs.get("username")
                results[device_id] = ssh_to_device(device_id, command, username)
            elif operation == "ota_check":
                from mcp_remote_testing.tools.ota_manager import check_ota_status
                results[device_id] = check_ota_status(device_id)
            elif operation == "system_status":
                from mcp_remote_testing.tools.ota_manager import get_system_status
                results[device_id] = get_system_status(device_id)
            elif operation == "list_containers":
                from mcp_remote_testing.tools.ota_manager import list_containers
                results[device_id] = list_containers(device_id)
            else:
                results[device_id] = {"error": f"Unknown operation: {operation}"}
        except Exception as e:
            results[device_id] = {"error": f"Operation failed: {e!s}"}

    # Summary
    success_count = sum(1 for r in results.values() if r.get("success") or "error" not in str(r))
    total_count = len(device_ids)

    return {
        "operation": operation,
        "total_devices": total_count,
        "successful": success_count,
        "failed": total_count - success_count,
        "results": results
    }


def regression_test(
    device_group: Optional[str] = None,
    device_ids: Optional[List[str]] = None,
    test_sequence: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Run regression test sequence on multiple devices.
    
    Args:
        device_group: Device group/tag to test (optional)
        device_ids: Specific device IDs to test (optional)
        test_sequence: List of test operations to run
        
    Returns:
        Test results
    """
    # Determine devices to test
    if device_ids:
        target_devices = device_ids
    elif device_group:
        groups = get_device_groups()
        target_devices = groups.get(device_group, [])
        if not target_devices:
            return {"error": f"Device group '{device_group}' not found"}
    else:
        return {"error": "Must specify either device_group or device_ids"}

    # Default test sequence
    if not test_sequence:
        test_sequence = [
            "test",  # Connectivity test
            "system_status",  # System health
            "ota_check"  # OTA status
        ]

    # Run test sequence
    all_results = {}
    for test_op in test_sequence:
        result = batch_operation(target_devices, test_op)
        all_results[test_op] = result

    # Overall summary
    total_tests = len(test_sequence) * len(target_devices)
    successful_tests = sum(
        r.get("successful", 0) for r in all_results.values()
    )

    return {
        "device_group": device_group,
        "device_ids": target_devices,
        "test_sequence": test_sequence,
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "failed_tests": total_tests - successful_tests,
        "results": all_results
    }

