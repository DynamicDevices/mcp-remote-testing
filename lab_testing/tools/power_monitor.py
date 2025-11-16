"""
Power Monitoring Tools for MCP Server
"""

import json
import subprocess
import sys
from typing import Any, Dict, Optional

from lab_testing.config import get_lab_devices_config, get_logs_dir, get_scripts_dir


def start_power_monitoring(
    device_id: Optional[str] = None,
    test_name: Optional[str] = None,
    duration: Optional[int] = None,
    monitor_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Start a power monitoring session.
    
    Supports both DMM (Digital Multimeter) and Tasmota devices for power measurement.
    - DMM: Direct power measurement via SCPI commands (test_equipment device type)
    - Tasmota: Power monitoring via Tasmota energy monitoring (tasmota_device with energy monitoring)

    Args:
        device_id: Target device ID or Tasmota switch ID (optional, uses DMM default if not specified)
        test_name: Name for this test session
        duration: Duration in seconds (optional, runs until stopped)
        monitor_type: Type of monitor to use - "dmm" or "tasmota" (auto-detected if not specified)

    Returns:
        Dictionary with monitoring session information
    """
    # Load device config to determine monitor type
    try:
        with open(get_lab_devices_config()) as f:
            config = json.load(f)
            devices = config.get("devices", {})
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load device configuration: {e!s}"
        }
    
    # Auto-detect monitor type if not specified
    if device_id and device_id in devices:
        device = devices[device_id]
        if not monitor_type:
            if device.get("device_type") == "tasmota_device":
                monitor_type = "tasmota"
            elif device.get("device_type") == "test_equipment":
                monitor_type = "dmm"
    
    # Default to DMM if not specified
    if not monitor_type:
        monitor_type = "dmm"
    
    if monitor_type == "tasmota":
        # Use Tasmota energy monitoring
        return _start_tasmota_power_monitoring(device_id, test_name, duration, devices)
    else:
        # Use DMM monitoring
        return _start_dmm_power_monitoring(device_id, test_name, duration, devices)


def _start_dmm_power_monitoring(
    device_id: Optional[str],
    test_name: Optional[str],
    duration: Optional[int],
    devices: Dict[str, Any]
) -> Dict[str, Any]:
    """Start DMM-based power monitoring"""
    scripts_dir = get_scripts_dir()
    monitor_script = scripts_dir / "current_monitor.py"

    if not monitor_script.exists():
        return {
            "success": False,
            "error": f"Power monitoring script not found: {monitor_script}",
            "suggestions": [
                "Ensure current_monitor.py script exists in scripts directory",
                "Or use Tasmota device for power monitoring with monitor_type='tasmota'"
            ]
        }

    # Build command
    cmd = [sys.executable, str(monitor_script)]

    if test_name:
        cmd.extend(["--test-name", test_name])

    if device_id and device_id in devices:
        device = devices[device_id]
        if device.get("device_type") == "test_equipment":
            ip = device.get("ip")
            if ip:
                cmd.extend(["--dmm-host", ip])

    # Start monitoring in background
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        return {
            "success": True,
            "monitor_type": "dmm",
            "process_id": process.pid,
            "test_name": test_name or "default",
            "command": " ".join(cmd),
            "message": f"DMM power monitoring started (PID: {process.pid})"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to start DMM power monitoring: {e!s}"
        }


def _start_tasmota_power_monitoring(
    device_id: Optional[str],
    test_name: Optional[str],
    duration: Optional[int],
    devices: Dict[str, Any]
) -> Dict[str, Any]:
    """Start Tasmota-based power monitoring"""
    if not device_id:
        return {
            "success": False,
            "error": "device_id is required for Tasmota power monitoring",
            "suggestions": [
                "Specify a Tasmota device ID that has energy monitoring enabled",
                "Use list_tasmota_devices to see available Tasmota devices"
            ]
        }
    
    if device_id not in devices:
        return {
            "success": False,
            "error": f"Tasmota device '{device_id}' not found in configuration"
        }
    
    device = devices[device_id]
    if device.get("device_type") != "tasmota_device":
        return {
            "success": False,
            "error": f"Device '{device_id}' is not a Tasmota device",
            "suggestions": [
                "Use a device with device_type='tasmota_device'",
                "Or use DMM monitoring with monitor_type='dmm'"
            ]
        }
    
    # Import here to avoid circular dependency
    from lab_testing.tools.tasmota_control import tasmota_control
    
    # Test Tasmota energy monitoring
    test_result = tasmota_control(device_id, "energy")
    if not test_result.get("success"):
        return {
            "success": False,
            "error": f"Tasmota device '{device_id}' does not support energy monitoring",
            "tasmota_error": test_result.get("error"),
            "suggestions": [
                "Ensure Tasmota device has energy monitoring enabled",
                "Check Tasmota device configuration",
                "Use DMM monitoring as alternative"
            ]
        }
    
    # For Tasmota, we'll poll energy data periodically
    # This is a simplified implementation - in practice, you'd want a background process
    return {
        "success": True,
        "monitor_type": "tasmota",
        "device_id": device_id,
        "test_name": test_name or "default",
        "message": f"Tasmota power monitoring ready for device '{device_id}'. Use tasmota_control with 'energy' action to get power data.",
        "note": "Tasmota monitoring requires periodic polling. Consider using a monitoring script for continuous monitoring."
    }


def get_power_logs(test_name: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """
    Get recent power monitoring logs.

    Args:
        test_name: Filter by test name (optional)
        limit: Maximum number of log files to return

    Returns:
        Dictionary with log file information
    """
    logs_dir = get_logs_dir() / "power_logs"

    if not logs_dir.exists():
        return {
            "success": False,
            "error": f"Logs directory not found: {logs_dir}"
        }

    # Find log files
    log_files = []
    for log_file in sorted(logs_dir.glob("*.csv"), reverse=True):
        if test_name and test_name not in log_file.name:
            continue

        stat = log_file.stat()
        log_files.append({
            "filename": log_file.name,
            "path": str(log_file),
            "size": stat.st_size,
            "modified": stat.st_mtime
        })

        if len(log_files) >= limit:
            break

    return {
        "success": True,
        "logs_dir": str(logs_dir),
        "log_files": log_files,
        "count": len(log_files)
    }

