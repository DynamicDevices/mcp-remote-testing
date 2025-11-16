"""
Power Monitoring Tools for MCP Server
"""

import json
import subprocess
import sys
from typing import Any, Dict, Optional

from mcp_remote_testing.config import get_lab_devices_config, get_scripts_dir, get_logs_dir


def start_power_monitoring(
    device_id: Optional[str] = None,
    test_name: Optional[str] = None,
    duration: Optional[int] = None
) -> Dict[str, Any]:
    """
    Start a power monitoring session.

    Args:
        device_id: Target device ID (optional, uses DMM default if not specified)
        test_name: Name for this test session
        duration: Duration in seconds (optional, runs until stopped)

    Returns:
        Dictionary with monitoring session information
    """
    scripts_dir = get_scripts_dir()
    monitor_script = scripts_dir / "current_monitor.py"

    if not monitor_script.exists():
        return {
            "success": False,
            "error": f"Power monitoring script not found: {monitor_script}"
        }

    # Build command
    cmd = [sys.executable, str(monitor_script)]

    if test_name:
        cmd.extend(["--test-name", test_name])

    if device_id:
        # Load device config to get DMM IP
        try:
            with open(get_lab_devices_config(), 'r') as f:
                config = json.load(f)
                devices = config.get("devices", {})
                if device_id in devices:
                    device = devices[device_id]
                    if device.get("device_type") == "test_equipment":
                        ip = device.get("ip")
                        if ip:
                            cmd.extend(["--dmm-host", ip])
        except Exception:
            pass

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
            "process_id": process.pid,
            "test_name": test_name or "default",
            "command": " ".join(cmd),
            "message": f"Power monitoring started (PID: {process.pid})"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to start power monitoring: {str(e)}"
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

