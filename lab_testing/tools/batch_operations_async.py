"""
Async Batch Operations for Multiple Devices

Supports parallel execution for faster regression testing.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from lab_testing.config import get_lab_devices_config
from lab_testing.utils.logger import get_logger

logger = get_logger()


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
        logger.error(f"Failed to get device groups: {e}")
        return {"error": f"Failed to get device groups: {e!s}"}


async def _run_operation_async(device_id: str, operation: str, semaphore: asyncio.Semaphore, **kwargs) -> tuple:
    """
    Run a single operation on a device asynchronously.
    
    Args:
        device_id: Device identifier
        operation: Operation to perform
        semaphore: Semaphore for concurrency control
        **kwargs: Operation-specific parameters
        
    Returns:
        Tuple of (device_id, result)
    """
    async with semaphore:
        try:
            logger.debug(f"Executing {operation} on {device_id}")

            if operation == "test":
                from lab_testing.tools.device_manager import test_device
                # Run in thread pool since it's synchronous
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, test_device, device_id)
            elif operation == "ssh":
                from lab_testing.tools.device_manager import ssh_to_device
                command = kwargs.get("command", "")
                username = kwargs.get("username")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, ssh_to_device, device_id, command, username)
            elif operation == "ota_check":
                from lab_testing.tools.ota_manager import check_ota_status
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, check_ota_status, device_id)
            elif operation == "system_status":
                from lab_testing.tools.ota_manager import get_system_status
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, get_system_status, device_id)
            elif operation == "list_containers":
                from lab_testing.tools.ota_manager import list_containers
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, list_containers, device_id)
            else:
                result = {"error": f"Unknown operation: {operation}"}

            logger.debug(f"Completed {operation} on {device_id}: {'success' if result.get('success') else 'failed'}")
            return device_id, result

        except Exception as e:
            logger.error(f"Operation {operation} failed for {device_id}: {e}", exc_info=True)
            return device_id, {"error": f"Operation failed: {e!s}"}


async def batch_operation_async(
    device_ids: List[str],
    operation: str,
    max_concurrent: int = 5,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute operation on multiple devices in parallel.
    
    Args:
        device_ids: List of device identifiers
        operation: Operation to perform (test, ssh, ota_check, etc.)
        max_concurrent: Maximum concurrent operations (default: 5)
        **kwargs: Operation-specific parameters
        
    Returns:
        Results for each device with summary
    """
    if not device_ids:
        return {"error": "No devices specified"}

    if not operation:
        return {"error": "No operation specified"}

    logger.info(f"Starting async batch operation '{operation}' on {len(device_ids)} devices (max_concurrent={max_concurrent})")

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)

    # Create tasks for all devices
    tasks = [
        _run_operation_async(device_id, operation, semaphore, **kwargs)
        for device_id in device_ids
    ]

    # Execute all tasks in parallel
    start_time = asyncio.get_event_loop().time()
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    duration = asyncio.get_event_loop().time() - start_time

    # Process results
    results = {}
    for item in results_list:
        if isinstance(item, Exception):
            logger.error(f"Task raised exception: {item}", exc_info=True)
            continue
        device_id, result = item
        results[device_id] = result

    # Calculate summary
    success_count = sum(1 for r in results.values() if r.get("success") or "error" not in str(r))
    total_count = len(device_ids)

    logger.info(f"Batch operation completed in {duration:.2f}s: {success_count}/{total_count} successful")

    return {
        "operation": operation,
        "total_devices": total_count,
        "successful": success_count,
        "failed": total_count - success_count,
        "duration_seconds": round(duration, 2),
        "max_concurrent": max_concurrent,
        "results": results
    }


async def regression_test_async(
    device_group: Optional[str] = None,
    device_ids: Optional[List[str]] = None,
    test_sequence: Optional[List[str]] = None,
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """
    Run regression test sequence on multiple devices in parallel.
    
    Args:
        device_group: Device group/tag to test (optional)
        device_ids: Specific device IDs to test (optional)
        test_sequence: List of test operations to run
        max_concurrent: Maximum concurrent operations per test
        
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

    logger.info(f"Starting async regression test on {len(target_devices)} devices with sequence: {test_sequence}")

    # Run test sequence (each test runs in parallel across devices)
    all_results = {}
    total_start_time = asyncio.get_event_loop().time()

    for test_op in test_sequence:
        logger.debug(f"Running test operation: {test_op}")
        result = await batch_operation_async(target_devices, test_op, max_concurrent=max_concurrent)
        all_results[test_op] = result

    total_duration = asyncio.get_event_loop().time() - total_start_time

    # Overall summary
    total_tests = len(test_sequence) * len(target_devices)
    successful_tests = sum(
        r.get("successful", 0) for r in all_results.values()
    )

    logger.info(f"Regression test completed in {total_duration:.2f}s: {successful_tests}/{total_tests} tests passed")

    return {
        "device_group": device_group,
        "device_ids": target_devices,
        "test_sequence": test_sequence,
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "failed_tests": total_tests - successful_tests,
        "total_duration_seconds": round(total_duration, 2),
        "max_concurrent": max_concurrent,
        "results": all_results
    }

