"""
SSH Connection Pool for Reusing Connections

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import subprocess
import time
from threading import Lock
from typing import Dict, Optional, Tuple

from lab_testing.utils.credentials import check_ssh_key_installed
from lab_testing.utils.logger import get_logger

logger = get_logger()

# Connection pool: device_id -> (process, last_used_time)
_connection_pool: Dict[str, Tuple[subprocess.Popen, float]] = {}
_pool_lock = Lock()

# Connection timeout (seconds of inactivity before closing)
CONNECTION_TIMEOUT = 300  # 5 minutes

# Maximum pool size
MAX_POOL_SIZE = 10


def _cleanup_stale_connections():
    """Remove stale connections from pool"""
    global _connection_pool
    current_time = time.time()
    to_remove = []

    with _pool_lock:
        for device_id, (process, last_used) in list(_connection_pool.items()):
            # Check if connection is still alive
            if process.poll() is not None:
                # Process has terminated
                to_remove.append(device_id)
                logger.debug(f"Removing terminated connection for {device_id}")
            elif current_time - last_used > CONNECTION_TIMEOUT:
                # Connection timed out
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except Exception:
                    process.kill()
                to_remove.append(device_id)
                logger.debug(f"Removing timed out connection for {device_id}")

        for device_id in to_remove:
            del _connection_pool[device_id]


def get_persistent_ssh_connection(
    device_ip: str, username: str, device_id: str, ssh_port: int = 22
) -> Optional[subprocess.Popen]:
    """
    Get or create a persistent SSH connection for a device.

    Args:
        device_ip: Device IP address
        username: SSH username
        device_id: Device identifier
        ssh_port: SSH port (default: 22)

    Returns:
        SSH process (master connection) or None if connection failed
    """
    _cleanup_stale_connections()

    # Check if we already have a connection
    with _pool_lock:
        if device_id in _connection_pool:
            process, _last_used = _connection_pool[device_id]
            if process.poll() is None:  # Still alive
                # Update last used time
                _connection_pool[device_id] = (process, time.time())
                logger.debug(f"Reusing existing SSH connection for {device_id}")
                return process
            # Process died, remove it
            del _connection_pool[device_id]
            logger.debug(f"SSH connection for {device_id} died, will recreate")

    # Check pool size limit
    with _pool_lock:
        if len(_connection_pool) >= MAX_POOL_SIZE:
            logger.warning(
                f"Connection pool full ({MAX_POOL_SIZE}), cleaning up oldest connections"
            )
            # Remove oldest connection
            oldest = min(_connection_pool.items(), key=lambda x: x[1][1])
            device_to_remove = oldest[0]
            process_to_remove = oldest[1][0]
            try:
                process_to_remove.terminate()
                process_to_remove.wait(timeout=2)
            except Exception:
                process_to_remove.kill()
            del _connection_pool[device_to_remove]
            logger.debug(f"Removed oldest connection for {device_to_remove}")

    # Create new SSH master connection using ControlMaster
    # This allows multiplexing multiple commands over one connection
    control_path = f"/tmp/ssh_mcp_{device_id}_{device_ip.replace('.', '_')}"

    # Check if key-based auth works
    if not check_ssh_key_installed(device_ip, username):
        logger.debug(f"SSH key not installed for {device_id}, cannot use connection pooling")
        return None

    try:
        # Create master connection
        ssh_cmd = [
            "ssh",
            "-o",
            "ControlMaster=yes",
            "-o",
            f"ControlPath={control_path}",
            "-o",
            "ControlPersist=300",  # Keep master alive for 5 minutes
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=10",
            "-p",
            str(ssh_port),
            "-N",  # No command, just establish connection
            f"{username}@{device_ip}",
        ]

        process = subprocess.Popen(
            ssh_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )

        # Wait a moment to see if connection succeeds
        time.sleep(0.5)
        if process.poll() is None:
            # Connection established
            with _pool_lock:
                _connection_pool[device_id] = (process, time.time())
            logger.info(f"Created persistent SSH connection for {device_id}")
            return process
        # Connection failed
        stderr = process.stderr.read().decode() if process.stderr else ""
        logger.warning(f"Failed to create SSH master connection for {device_id}: {stderr}")
        return None

    except Exception as e:
        logger.error(f"Error creating SSH connection for {device_id}: {e}", exc_info=True)
        return None


def execute_via_pool(
    device_ip: str, username: str, command: str, device_id: str, ssh_port: int = 22
) -> subprocess.CompletedProcess:
    """
    Execute SSH command using connection pool if available, otherwise fallback to direct connection.

    Args:
        device_ip: Device IP address
        username: SSH username
        command: Command to execute
        device_id: Device identifier
        ssh_port: SSH port

    Returns:
        CompletedProcess result
    """
    # Try to use pooled connection
    master = get_persistent_ssh_connection(device_ip, username, device_id, ssh_port)

    if master and master.poll() is None:
        # Use ControlMaster connection
        control_path = f"/tmp/ssh_mcp_{device_id}_{device_ip.replace('.', '_')}"
        ssh_cmd = [
            "ssh",
            "-o",
            f"ControlPath={control_path}",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-p",
            str(ssh_port),
            f"{username}@{device_ip}",
            command,
        ]
        logger.debug(f"Executing via connection pool: {device_id}")
    else:
        # Fallback to direct connection
        from lab_testing.utils.credentials import get_ssh_command

        ssh_cmd = get_ssh_command(device_ip, username, command, device_id, use_password=False)
        if ssh_port != 22:
            port_idx = ssh_cmd.index(f"{username}@{device_ip}")
            ssh_cmd.insert(port_idx, "-p")
            ssh_cmd.insert(port_idx + 1, str(ssh_port))
        logger.debug(f"Executing via direct connection: {device_id}")

    return subprocess.run(ssh_cmd, check=False, capture_output=True, text=True, timeout=30)


def close_connection(device_id: str):
    """Close and remove connection from pool"""
    with _pool_lock:
        if device_id in _connection_pool:
            process, _ = _connection_pool[device_id]
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                process.kill()
            del _connection_pool[device_id]
            logger.debug(f"Closed SSH connection for {device_id}")


def close_all_connections():
    """Close all connections in pool"""
    with _pool_lock:
        for device_id, (process, _) in list(_connection_pool.items()):
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                process.kill()
        _connection_pool.clear()
        logger.info("Closed all SSH connections")


def get_pool_status() -> Dict[str, any]:
    """Get status of connection pool"""
    _cleanup_stale_connections()
    with _pool_lock:
        return {
            "size": len(_connection_pool),
            "max_size": MAX_POOL_SIZE,
            "connections": [
                {
                    "device_id": device_id,
                    "alive": process.poll() is None,
                    "last_used_seconds_ago": int(time.time() - last_used),
                }
                for device_id, (process, last_used) in _connection_pool.items()
            ],
        }
