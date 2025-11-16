"""
Health Check Resource Provider

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import time
from typing import Any, Dict

from lab_testing.config import validate_config
from lab_testing.tools.vpn_manager import get_vpn_status
from lab_testing.utils.logger import get_logger
from lab_testing.utils.ssh_pool import get_pool_status

# Server start time for uptime calculation
_server_start_time = time.time()

# Metrics tracking
_metrics = {
    "tool_calls": {},
    "tool_errors": {},
    "total_calls": 0,
    "total_errors": 0
}


def record_tool_call(tool_name: str, success: bool, duration: float = 0.0):
    """
    Record tool call for metrics.
    
    Args:
        tool_name: Name of the tool
        success: Whether call succeeded
        duration: Execution duration in seconds
    """
    _metrics["total_calls"] += 1

    if tool_name not in _metrics["tool_calls"]:
        _metrics["tool_calls"][tool_name] = {
            "count": 0,
            "success": 0,
            "errors": 0,
            "total_duration": 0.0,
            "avg_duration": 0.0
        }

    _metrics["tool_calls"][tool_name]["count"] += 1
    _metrics["tool_calls"][tool_name]["total_duration"] += duration

    if success:
        _metrics["tool_calls"][tool_name]["success"] += 1
    else:
        _metrics["tool_calls"][tool_name]["errors"] += 1
        _metrics["total_errors"] += 1
        if tool_name not in _metrics["tool_errors"]:
            _metrics["tool_errors"][tool_name] = 0
        _metrics["tool_errors"][tool_name] += 1

    # Update average duration
    count = _metrics["tool_calls"][tool_name]["count"]
    total = _metrics["tool_calls"][tool_name]["total_duration"]
    _metrics["tool_calls"][tool_name]["avg_duration"] = total / count if count > 0 else 0.0


def get_health_status() -> Dict[str, Any]:
    """
    Get comprehensive health status of the MCP server.
    
    Returns:
        Health status dictionary
    """
    logger = get_logger()

    # Calculate uptime
    uptime_seconds = time.time() - _server_start_time
    uptime_hours = uptime_seconds / 3600

    # Validate configuration
    config_valid, config_errors = validate_config()

    # Check VPN status
    try:
        vpn_status = get_vpn_status()
        vpn_connected = vpn_status.get("connected", False)
    except Exception as e:
        logger.warning(f"Failed to get VPN status: {e}")
        vpn_connected = False
        vpn_status = {"error": str(e)}

    # Calculate success rate
    success_rate = 0.0
    if _metrics["total_calls"] > 0:
        success_count = _metrics["total_calls"] - _metrics["total_errors"]
        success_rate = (success_count / _metrics["total_calls"]) * 100

    # Get top tools by usage
    top_tools = sorted(
        _metrics["tool_calls"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:5]

    # Get SSH connection pool status
    try:
        pool_status = get_pool_status()
    except Exception as e:
        logger.warning(f"Failed to get pool status: {e}")
        pool_status = {"error": str(e)}

    health_status = {
        "status": "healthy" if config_valid and success_rate > 95 else "degraded",
        "uptime_seconds": int(uptime_seconds),
        "uptime_hours": round(uptime_hours, 2),
        "server_start_time": _server_start_time,
        "configuration": {
            "valid": config_valid,
            "errors": config_errors if not config_valid else []
        },
        "vpn": {
            "connected": vpn_connected,
            "status": vpn_status
        },
        "ssh_pool": pool_status,
        "metrics": {
            "total_calls": _metrics["total_calls"],
            "total_errors": _metrics["total_errors"],
            "success_rate_percent": round(success_rate, 2),
            "top_tools": [
                {
                    "tool": name,
                    "calls": data["count"],
                    "success": data["success"],
                    "errors": data["errors"],
                    "avg_duration_seconds": round(data["avg_duration"], 3)
                }
                for name, data in top_tools
            ]
        },
        "timestamp": time.time()
    }

    return health_status


def get_metrics() -> Dict[str, Any]:
    """
    Get detailed metrics.
    
    Returns:
        Metrics dictionary
    """
    return {
        "tool_calls": _metrics["tool_calls"].copy(),
        "tool_errors": _metrics["tool_errors"].copy(),
        "total_calls": _metrics["total_calls"],
        "total_errors": _metrics["total_errors"],
        "success_rate": round(
            ((_metrics["total_calls"] - _metrics["total_errors"]) / _metrics["total_calls"] * 100)
            if _metrics["total_calls"] > 0 else 0.0,
            2
        )
    }

