"""
Process Management for Remote Commands

Tracks and manages running processes to prevent conflicts from duplicate executions.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from lab_testing.utils.logger import get_logger
from lab_testing.utils.ssh_pool import execute_via_pool

logger = get_logger()

# Track processes by device_id and process pattern
_process_tracking: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))


def find_running_processes(
    device_ip: str, username: str, device_id: str, process_pattern: str
) -> List[Tuple[int, str]]:
    """
    Find running processes matching a pattern on a remote device.

    Args:
        device_ip: Device IP address
        username: SSH username
        device_id: Device identifier
        process_pattern: Process name or command pattern to search for

    Returns:
        List of (PID, command) tuples
    """
    try:
        # Use pgrep or ps to find processes
        # Try pgrep first (more reliable)
        cmd = (
            f"pgrep -af '{process_pattern}' || ps aux | grep -E '{process_pattern}' | grep -v grep"
        )
        result = execute_via_pool(device_ip, username, cmd, device_id)

        if result.returncode != 0:
            # Fallback to ps if pgrep fails
            cmd = f"ps aux | grep -E '{process_pattern}' | grep -v grep"
            result = execute_via_pool(device_ip, username, cmd, device_id)

        if result.returncode != 0 or not result.stdout.strip():
            return []

        processes = []
        for line in result.stdout.strip().split("\n"):
            if not line or "grep" in line:
                continue
            # Parse ps output: USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
            parts = line.split()
            if len(parts) >= 2:
                try:
                    pid = int(parts[1])
                    # Get full command (everything after TIME)
                    cmd_start = line.find(parts[10]) if len(parts) > 10 else len(line)
                    command = line[cmd_start:].strip()
                    processes.append((pid, command))
                except (ValueError, IndexError):
                    continue

        return processes

    except Exception as e:
        logger.warning(f"Failed to find processes on {device_id}: {e}")
        return []


def kill_stale_processes(
    device_ip: str,
    username: str,
    device_id: str,
    process_pattern: str,
    kill_timeout: int = 5,
    force: bool = False,
) -> Dict[str, any]:
    """
    Kill stale processes matching a pattern on a remote device.

    Args:
        device_ip: Device IP address
        username: SSH username
        device_id: Device identifier
        process_pattern: Process name or command pattern to kill
        kill_timeout: Seconds to wait before force kill
        force: If True, use SIGKILL immediately

    Returns:
        Dictionary with kill results
    """
    processes = find_running_processes(device_ip, username, device_id, process_pattern)

    if not processes:
        return {
            "killed": 0,
            "pids": [],
            "message": f"No processes found matching '{process_pattern}'",
        }

    killed_pids = []
    failed_pids = []

    for pid, command in processes:
        try:
            # Try graceful kill first (SIGTERM)
            if not force:
                kill_cmd = f"kill -TERM {pid}"
                result = execute_via_pool(device_ip, username, kill_cmd, device_id)

            if result.returncode == 0:
                # Wait a moment, then check if still running
                time.sleep(0.5)
                # Check if process still exists
                check_cmd = f"kill -0 {pid} 2>/dev/null && echo 'running' || echo 'dead'"
                check_result = execute_via_pool(device_ip, username, check_cmd, device_id)

                if "running" in check_result.stdout:
                    # Process still alive, force kill
                    logger.debug(f"Process {pid} still running, force killing")
                    kill_cmd = f"kill -KILL {pid}"
                    result = execute_via_pool(device_ip, username, kill_cmd, device_id)

            else:
                # Force kill immediately
                kill_cmd = f"kill -KILL {pid}"
                result = execute_via_pool(device_ip, username, kill_cmd, device_id)

            if result.returncode == 0:
                killed_pids.append(pid)
                logger.info(f"Killed process {pid} on {device_id}: {command[:50]}")
            else:
                failed_pids.append(pid)
                logger.warning(f"Failed to kill process {pid} on {device_id}: {result.stderr}")

        except Exception as e:
            failed_pids.append(pid)
            logger.error(f"Error killing process {pid} on {device_id}: {e}")

    return {
        "killed": len(killed_pids),
        "pids": killed_pids,
        "failed": len(failed_pids),
        "failed_pids": failed_pids,
        "message": f"Killed {len(killed_pids)} process(es), {len(failed_pids)} failed",
    }


def ensure_single_process(
    device_ip: str,
    username: str,
    device_id: str,
    process_pattern: str,
    command: str,
    kill_existing: bool = True,
    force_kill: bool = False,
) -> Tuple[bool, Optional[Dict[str, any]]]:
    """
    Ensure only one instance of a process is running. Kill existing if needed.

    Args:
        device_ip: Device IP address
        username: SSH username
        device_id: Device identifier
        process_pattern: Pattern to match existing processes
        command: Command to run (for tracking)
        kill_existing: If True, kill existing processes before starting new one
        force_kill: If True, use SIGKILL immediately

    Returns:
        Tuple of (success, kill_result_dict)
    """
    existing = find_running_processes(device_ip, username, device_id, process_pattern)

    if not existing:
        return True, None

    if not kill_existing:
        return False, {
            "error": f"Process already running: {existing[0][1][:50]}",
            "pids": [pid for pid, _ in existing],
        }

    # Kill existing processes
    kill_result = kill_stale_processes(
        device_ip, username, device_id, process_pattern, force=force_kill
    )

    if kill_result["failed"] > 0:
        logger.warning(
            f"Some processes failed to kill on {device_id}: {kill_result['failed_pids']}"
        )

    return kill_result["killed"] > 0 or len(existing) == 0, kill_result


def track_process(device_id: str, process_pattern: str, pid: int):
    """Track a process for later cleanup"""
    _process_tracking[device_id][process_pattern].append(pid)
    logger.debug(f"Tracking process {pid} for {device_id}:{process_pattern}")


def cleanup_tracked_processes(
    device_ip: str, username: str, device_id: str, process_pattern: Optional[str] = None
):
    """
    Clean up tracked processes for a device.

    Args:
        device_ip: Device IP address
        username: SSH username
        device_id: Device identifier
        process_pattern: Specific pattern to clean (None = all)
    """
    if device_id not in _process_tracking:
        return

    patterns = [process_pattern] if process_pattern else list(_process_tracking[device_id].keys())

    for pattern in patterns:
        if pattern not in _process_tracking[device_id]:
            continue

        pids = _process_tracking[device_id][pattern]
        for pid in pids:
            try:
                kill_cmd = f"kill -TERM {pid} 2>/dev/null || kill -KILL {pid} 2>/dev/null || true"
                execute_via_pool(device_ip, username, kill_cmd, device_id)
                logger.debug(f"Cleaned up tracked process {pid} on {device_id}")
            except Exception as e:
                logger.warning(f"Failed to cleanup process {pid} on {device_id}: {e}")

        _process_tracking[device_id][pattern].clear()


def get_process_status(
    device_ip: str, username: str, device_id: str, process_pattern: str
) -> Dict[str, any]:
    """
    Get status of processes matching a pattern.

    Returns:
        Dictionary with process information
    """
    processes = find_running_processes(device_ip, username, device_id, process_pattern)

    return {
        "pattern": process_pattern,
        "count": len(processes),
        "processes": [
            {"pid": pid, "command": cmd[:100]} for pid, cmd in processes  # Truncate long commands
        ],
    }
