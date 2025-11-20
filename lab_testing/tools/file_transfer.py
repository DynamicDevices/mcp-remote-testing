"""
File Transfer Tools for Remote Devices

Tools for copying files to/from remote devices and syncing directories.
Optimized for speed using multiplexed SSH connections (ControlMaster) and parallel transfers.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lab_testing.exceptions import DeviceNotFoundError
from lab_testing.tools.device_manager import load_device_config, resolve_device_identifier
from lab_testing.utils.credentials import get_credential
from lab_testing.utils.device_access import _get_vpn_server_connection_info, get_unified_device_info
from lab_testing.utils.logger import get_logger
from lab_testing.utils.ssh_pool import get_persistent_ssh_connection

logger = get_logger()


def _extract_scp_error(stderr_text: str) -> str:
    """
    Extract the actual error message from scp/ssh stderr output.
    Filters out banners/motd and returns the actual error line.

    Args:
        stderr_text: Raw stderr output from scp/ssh command

    Returns:
        Clean error message
    """
    if not stderr_text:
        return "Unknown error"

    # Split into lines and filter out empty lines
    error_lines = [line.strip() for line in stderr_text.split("\n") if line.strip()]

    # Look for actual error lines (usually start with "scp:" or "ssh:")
    for line in reversed(error_lines):  # Check from end (most recent)
        if line.startswith("scp:") or line.startswith("ssh:"):
            return line

    # If no scp/ssh prefix found, use the last non-empty line
    if error_lines:
        return error_lines[-1]

    return "Unknown error"


def copy_file_to_device(
    device_id: str,
    local_path: str,
    remote_path: str,
    username: Optional[str] = None,
    preserve_permissions: bool = True,
) -> Dict[str, Any]:
    """
    Copy a file from local machine to remote device.

    Supports both Foundries devices (via VPN IP) and local config devices.
    Automatically falls back to VPN server connection for Foundries devices if direct connection fails.

    Args:
        device_id: Device identifier (Foundries device name or local device ID)
        local_path: Local file path to copy
        remote_path: Remote destination path on device
        username: SSH username (optional, uses device default)
        preserve_permissions: Preserve file permissions and timestamps (default: True)

    Returns:
        Dictionary with operation results
    """
    # Use unified device access to get device info (works for both Foundries and local devices)
    device_info = get_unified_device_info(device_id)
    if "error" in device_info:
        return {
            "success": False,
            "error": device_info["error"],
            "device_id": device_id,
        }

    ip = device_info.get("ip")
    if not ip:
        error_msg = f"Device '{device_id}' has no IP address"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
        }

    device_type = device_info.get("device_type", "unknown")
    resolved_device_id = device_info.get("device_id", device_id)

    # Check local file exists
    local_file = Path(local_path)
    if not local_file.exists():
        error_msg = f"Local file not found: {local_path}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "local_path": local_path,
        }

    if not local_file.is_file():
        error_msg = f"Local path is not a file: {local_path}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "local_path": local_path,
        }

    # Determine username
    if not username:
        username = device_info.get("username", "root")
        # Try to get from cached credentials for local devices
        if device_type == "local":
            cred = get_credential(resolved_device_id, "ssh")
            if cred and cred.get("username"):
                username = cred["username"]

    ssh_port = device_info.get("ssh_port", 22)

    try:
        # Get or create multiplexed SSH connection for faster transfers (only for local devices)
        # Foundries devices may need VPN server fallback, so skip multiplexing for them initially
        control_path = f"/tmp/ssh_mcp_{resolved_device_id}_{ip.replace('.', '_')}"
        master = None
        if device_type == "local":
            master = get_persistent_ssh_connection(ip, username, resolved_device_id, ssh_port)

        # Build scp command with ControlMaster for multiplexing
        scp_cmd = ["scp"]

        if master and master.poll() is None:
            # Use existing multiplexed connection (much faster)
            scp_cmd.extend(["-o", f"ControlPath={control_path}"])
            logger.debug(f"Using multiplexed SSH connection for {resolved_device_id}")
        else:
            # Fallback to direct connection
            scp_cmd.extend(["-o", "StrictHostKeyChecking=no"])
            scp_cmd.extend(["-o", "BatchMode=yes"])
            logger.debug(f"Using direct SSH connection for {resolved_device_id}")

        # Preserve permissions if requested
        if preserve_permissions:
            scp_cmd.append("-p")  # Preserve modification times, access times, and modes

        # Add compression for faster transfers over slow links
        scp_cmd.append("-C")  # Enable compression

        # Add source and destination
        scp_cmd.append(str(local_file))
        scp_cmd.append(f"{username}@{ip}:{remote_path}")

        # Execute scp
        result = subprocess.run(scp_cmd, check=False, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            logger.info(f"Successfully copied {local_path} to {resolved_device_id}:{remote_path}")
            return {
                "success": True,
                "device_id": resolved_device_id,
                "device_type": device_type,
                "connection_method": "direct",
                "ip": ip,
                "local_path": str(local_path),
                "remote_path": remote_path,
                "message": f"File copied successfully to {remote_path}",
            }

        # If direct connection failed and this is a Foundries device, try VPN server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct scp failed for Foundries device {device_id}, trying VPN server fallback"
            )
            return _copy_file_to_device_via_vpn_server(
                device_info, local_path, remote_path, username, preserve_permissions
            )

        actual_error = _extract_scp_error(result.stderr.strip() if result.stderr else "")
        error_msg = f"Failed to copy file: {actual_error}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
            "device_type": device_type,
            "connection_method": "direct",
            "local_path": str(local_path),
            "remote_path": remote_path,
            "suggestions": [
                "Check SSH key is installed: check_ssh_key_status(device_id)",
                "Verify device is online: test_device(device_id)",
                "Check remote directory exists: ssh_to_device(device_id, 'mkdir -p $(dirname remote_path)')",
            ],
        }

    except subprocess.TimeoutExpired:
        # If timeout and this is a Foundries device, try VPN server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct scp timed out for Foundries device {device_id}, trying VPN server fallback"
            )
            return _copy_file_to_device_via_vpn_server(
                device_info, local_path, remote_path, username, preserve_permissions
            )
        error_msg = "File copy timed out (60 seconds)"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
            "device_type": device_type,
            "connection_method": "direct",
        }
    except Exception as e:
        error_msg = f"Failed to copy file: {e!s}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }


def _copy_file_to_device_via_vpn_server(
    device_info: Dict[str, Any],
    local_path: str,
    remote_path: str,
    username: str,
    preserve_permissions: bool,
) -> Dict[str, Any]:
    """
    Copy file to Foundries device through VPN server (fallback when direct connection fails).

    Args:
        device_info: Device information dictionary from unified device access
        local_path: Local file path to copy
        remote_path: Remote destination path on device
        username: SSH username for device
        preserve_permissions: Preserve file permissions

    Returns:
        Dictionary with operation results
    """
    device_ip = device_info["ip"]
    device_id = device_info["device_id"]
    device_password = "fio"  # Default Foundries device password

    # Get VPN server connection info
    server_info = _get_vpn_server_connection_info()
    server_host = server_info["server_host"]
    server_port = server_info["server_port"]
    server_user = server_info["server_user"]
    server_password = server_info["server_password"]

    logger.debug(
        f"Copying file to Foundries device {device_id} ({device_ip}) through VPN server {server_host}:{server_port}"
    )

    local_file = Path(local_path)
    if not local_file.exists():
        return {
            "success": False,
            "error": f"Local file not found: {local_path}",
            "device_id": device_id,
            "connection_method": "through_vpn_server",
        }

    try:
        # Two-step copy: local -> VPN server -> device
        # Step 1: Copy file to VPN server temp location
        import tempfile
        import uuid

        temp_filename = f"mcp_transfer_{uuid.uuid4().hex[:8]}"
        server_temp_path = f"/tmp/{temp_filename}"

        # Copy to server
        server_scp_cmd = ["scp"]
        server_scp_cmd.extend(["-o", "StrictHostKeyChecking=no"])
        server_scp_cmd.extend(["-o", "UserKnownHostsFile=/dev/null"])
        server_scp_cmd.extend(["-P", str(server_port)])
        if preserve_permissions:
            server_scp_cmd.append("-p")
        server_scp_cmd.append("-C")  # Compression
        server_scp_cmd.append(str(local_file))
        server_scp_cmd.append(f"{server_user}@{server_host}:{server_temp_path}")

        if server_password:
            server_scp_cmd = ["sshpass", "-p", server_password] + server_scp_cmd

        server_result = subprocess.run(
            server_scp_cmd, check=False, capture_output=True, text=True, timeout=60
        )

        if server_result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to copy file to VPN server: {server_result.stderr.strip() or 'Unknown error'}",
                "device_id": device_id,
                "connection_method": "through_vpn_server",
            }

        # Step 2: Copy from server to device
        device_password = "fio"  # Default Foundries device password
        device_scp_cmd = f"sshpass -p '{device_password}' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {server_temp_path} {username}@{device_ip}:{remote_path} && rm -f {server_temp_path}"

        # SSH to server and execute scp to device
        ssh_to_server_cmd = ["ssh"]
        ssh_to_server_cmd.extend(["-o", "StrictHostKeyChecking=no"])
        ssh_to_server_cmd.extend(["-o", "UserKnownHostsFile=/dev/null"])
        ssh_to_server_cmd.extend(["-p", str(server_port)])
        ssh_to_server_cmd.append(f"{server_user}@{server_host}")

        if server_password:
            ssh_to_server_cmd = ["sshpass", "-p", server_password] + ssh_to_server_cmd

        ssh_to_server_cmd.append(device_scp_cmd)

        # Execute nested command
        result = subprocess.run(
            ssh_to_server_cmd, check=False, capture_output=True, text=True, timeout=120
        )

        if result.returncode == 0:
            logger.info(
                f"Successfully copied {local_path} to {device_id}:{remote_path} via VPN server"
            )
            return {
                "success": True,
                "device_id": device_id,
                "device_type": device_info.get("device_type", "foundries"),
                "connection_method": "through_vpn_server",
                "ip": device_ip,
                "local_path": str(local_path),
                "remote_path": remote_path,
                "message": f"File copied successfully to {remote_path} via VPN server",
            }

        actual_error = _extract_scp_error(result.stderr.strip() if result.stderr else "")
        error_msg = f"Failed to copy file via VPN server: {actual_error}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
            "device_type": device_info.get("device_type", "foundries"),
            "connection_method": "through_vpn_server",
            "local_path": str(local_path),
            "remote_path": remote_path,
            "suggestions": [
                "Check VPN server connectivity",
                "Verify device is reachable from VPN server",
                "Check device-to-device communication is enabled",
            ],
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "File copy via VPN server timed out (120 seconds)",
            "device_id": device_id,
            "connection_method": "through_vpn_server",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to copy file via VPN server: {e!s}",
            "device_id": device_id,
            "connection_method": "through_vpn_server",
        }


def copy_file_from_device(
    device_id: str,
    remote_path: str,
    local_path: str,
    username: Optional[str] = None,
    preserve_permissions: bool = True,
) -> Dict[str, Any]:
    """
    Copy a file from remote device to local machine.

    Supports both Foundries devices (via VPN IP) and local config devices.
    Automatically falls back to VPN server connection for Foundries devices if direct connection fails.

    Args:
        device_id: Device identifier (Foundries device name or local device ID)
        remote_path: Remote file path on device
        local_path: Local destination path
        username: SSH username (optional, uses device default)
        preserve_permissions: Preserve file permissions and timestamps (default: True)

    Returns:
        Dictionary with operation results
    """
    # Use unified device access to get device info (works for both Foundries and local devices)
    device_info = get_unified_device_info(device_id)
    if "error" in device_info:
        return {
            "success": False,
            "error": device_info["error"],
            "device_id": device_id,
        }

    ip = device_info.get("ip")
    if not ip:
        error_msg = f"Device '{device_id}' has no IP address"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
        }

    device_type = device_info.get("device_type", "unknown")
    resolved_device_id = device_info.get("device_id", device_id)

    # Determine username
    if not username:
        username = device_info.get("username", "root")
        # Try to get from cached credentials for local devices
        if device_type == "local":
            cred = get_credential(resolved_device_id, "ssh")
            if cred and cred.get("username"):
                username = cred["username"]

    ssh_port = device_info.get("ssh_port", 22)

    # Ensure local directory exists
    local_file = Path(local_path)
    local_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Get or create multiplexed SSH connection for faster transfers (only for local devices)
        # Foundries devices may need VPN server fallback, so skip multiplexing for them initially
        control_path = f"/tmp/ssh_mcp_{resolved_device_id}_{ip.replace('.', '_')}"
        master = None
        if device_type == "local":
            master = get_persistent_ssh_connection(ip, username, resolved_device_id, ssh_port)

        # Build scp command with ControlMaster for multiplexing
        scp_cmd = ["scp"]

        if master and master.poll() is None:
            # Use existing multiplexed connection (much faster)
            scp_cmd.extend(["-o", f"ControlPath={control_path}"])
            logger.debug(f"Using multiplexed SSH connection for {resolved_device_id}")
        else:
            # Fallback to direct connection
            scp_cmd.extend(["-o", "StrictHostKeyChecking=no"])
            scp_cmd.extend(["-o", "BatchMode=yes"])
            logger.debug(f"Using direct SSH connection for {resolved_device_id}")

        # Preserve permissions if requested
        if preserve_permissions:
            scp_cmd.append("-p")  # Preserve modification times, access times, and modes

        # Add compression for faster transfers over slow links
        scp_cmd.append("-C")  # Enable compression

        # Add source and destination
        scp_cmd.append(f"{username}@{ip}:{remote_path}")
        scp_cmd.append(str(local_file))

        # Execute scp
        result = subprocess.run(scp_cmd, check=False, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            logger.info(
                f"Successfully copied {remote_path} from {resolved_device_id} to {local_path}"
            )
            return {
                "success": True,
                "device_id": resolved_device_id,
                "device_type": device_type,
                "connection_method": "direct",
                "ip": ip,
                "remote_path": remote_path,
                "local_path": str(local_file),
                "message": f"File copied successfully to {local_path}",
            }

        # If direct connection failed and this is a Foundries device, try VPN server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct scp failed for Foundries device {device_id}, trying VPN server fallback"
            )
            return _copy_file_from_device_via_vpn_server(
                device_info, remote_path, local_path, username, preserve_permissions
            )

        actual_error = _extract_scp_error(result.stderr.strip() if result.stderr else "")
        error_msg = f"Failed to copy file: {actual_error}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
            "device_type": device_type,
            "connection_method": "direct",
            "remote_path": remote_path,
            "local_path": str(local_path),
            "suggestions": [
                "Check SSH key is installed: check_ssh_key_status(device_id)",
                "Verify device is online: test_device(device_id)",
                f"Check remote file exists: ssh_to_device(device_id, 'ls -lh {remote_path}')",
            ],
        }

    except subprocess.TimeoutExpired:
        # If timeout and this is a Foundries device, try VPN server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct scp timed out for Foundries device {device_id}, trying VPN server fallback"
            )
            return _copy_file_from_device_via_vpn_server(
                device_info, remote_path, local_path, username, preserve_permissions
            )
        error_msg = "File copy timed out (60 seconds)"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
            "device_type": device_type,
            "connection_method": "direct",
        }
    except Exception as e:
        # If exception and this is a Foundries device, try VPN server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct scp exception for Foundries device {device_id}, trying VPN server fallback: {e}"
            )
            return _copy_file_from_device_via_vpn_server(
                device_info, remote_path, local_path, username, preserve_permissions
            )
        error_msg = f"Failed to copy file: {e!s}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
            "device_type": device_type,
            "connection_method": "direct",
        }


def _copy_file_from_device_via_vpn_server(
    device_info: Dict[str, Any],
    remote_path: str,
    local_path: str,
    username: str,
    preserve_permissions: bool,
) -> Dict[str, Any]:
    """
    Copy file from Foundries device through VPN server (fallback when direct connection fails).

    Args:
        device_info: Device information dictionary from unified device access
        remote_path: Remote file path on device
        local_path: Local destination path
        username: SSH username for device
        preserve_permissions: Preserve file permissions

    Returns:
        Dictionary with operation results
    """
    device_ip = device_info["ip"]
    device_id = device_info["device_id"]
    device_password = "fio"  # Default Foundries device password

    # Get VPN server connection info
    server_info = _get_vpn_server_connection_info()
    server_host = server_info["server_host"]
    server_port = server_info["server_port"]
    server_user = server_info["server_user"]
    server_password = server_info["server_password"]

    logger.debug(
        f"Copying file from Foundries device {device_id} ({device_ip}) through VPN server {server_host}:{server_port}"
    )

    local_file = Path(local_path)
    local_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Two-step copy: device -> VPN server -> local
        # Step 1: Copy file from device to VPN server temp location
        import tempfile
        import uuid

        temp_filename = f"mcp_transfer_{uuid.uuid4().hex[:8]}"
        server_temp_path = f"/tmp/{temp_filename}"

        # Copy from device to server
        device_password = "fio"  # Default Foundries device password
        device_scp_cmd = f"sshpass -p '{device_password}' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {username}@{device_ip}:{remote_path} {server_temp_path}"

        # SSH to server and execute scp from device
        ssh_to_server_cmd = ["ssh"]
        ssh_to_server_cmd.extend(["-o", "StrictHostKeyChecking=no"])
        ssh_to_server_cmd.extend(["-o", "UserKnownHostsFile=/dev/null"])
        ssh_to_server_cmd.extend(["-p", str(server_port)])
        ssh_to_server_cmd.append(f"{server_user}@{server_host}")

        if server_password:
            ssh_to_server_cmd = ["sshpass", "-p", server_password] + ssh_to_server_cmd

        ssh_to_server_cmd.append(device_scp_cmd)

        # Execute nested command
        result = subprocess.run(
            ssh_to_server_cmd, check=False, capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to copy file from device to VPN server: {result.stderr.strip() or 'Unknown error'}",
                "device_id": device_id,
                "connection_method": "through_vpn_server",
            }

        # Step 2: Copy from server to local
        server_scp_cmd = ["scp"]
        server_scp_cmd.extend(["-o", "StrictHostKeyChecking=no"])
        server_scp_cmd.extend(["-o", "UserKnownHostsFile=/dev/null"])
        server_scp_cmd.extend(["-P", str(server_port)])
        if preserve_permissions:
            server_scp_cmd.append("-p")
        server_scp_cmd.append("-C")  # Compression
        server_scp_cmd.append(f"{server_user}@{server_host}:{server_temp_path}")
        server_scp_cmd.append(str(local_file))

        if server_password:
            server_scp_cmd = ["sshpass", "-p", server_password] + server_scp_cmd

        # Also clean up temp file on server after copy
        server_scp_cmd_str = " ".join(server_scp_cmd)
        cleanup_cmd = f"{server_scp_cmd_str} && sshpass -p '{server_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {server_port} {server_user}@{server_host} 'rm -f {server_temp_path}'"

        result = subprocess.run(
            cleanup_cmd, shell=True, check=False, capture_output=True, text=True, timeout=60
        )

        if result.returncode == 0:
            logger.info(
                f"Successfully copied {remote_path} from {device_id} to {local_path} via VPN server"
            )
            return {
                "success": True,
                "device_id": device_id,
                "device_type": device_info.get("device_type", "foundries"),
                "connection_method": "through_vpn_server",
                "ip": device_ip,
                "remote_path": remote_path,
                "local_path": str(local_file),
                "message": f"File copied successfully to {local_path} via VPN server",
            }

        actual_error = _extract_scp_error(result.stderr.strip() if result.stderr else "")
        error_msg = f"Failed to copy file via VPN server: {actual_error}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
            "device_type": device_info.get("device_type", "foundries"),
            "connection_method": "through_vpn_server",
            "remote_path": remote_path,
            "local_path": str(local_path),
            "suggestions": [
                "Check VPN server connectivity",
                "Verify device is reachable from VPN server",
                "Check device-to-device communication is enabled",
                f"Check remote file exists: ssh_to_device(device_id, 'ls -lh {remote_path}')",
            ],
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "File copy via VPN server timed out (120 seconds)",
            "device_id": device_id,
            "connection_method": "through_vpn_server",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to copy file via VPN server: {e!s}",
            "device_id": device_id,
            "connection_method": "through_vpn_server",
        }


def sync_directory_to_device(
    device_id: str,
    local_dir: str,
    remote_dir: str,
    username: Optional[str] = None,
    exclude: Optional[list] = None,
    delete: bool = False,
) -> Dict[str, Any]:
    """
    Sync a local directory to remote device using rsync.
    More efficient than copying individual files for multiple files.

    Supports both Foundries devices (via VPN IP) and local config devices.
    Automatically falls back to VPN server connection for Foundries devices if direct connection fails.

    Args:
        device_id: Device identifier (Foundries device name or local device ID)
        local_dir: Local directory to sync
        remote_dir: Remote destination directory on device
        username: SSH username (optional, uses device default)
        exclude: List of patterns to exclude (e.g., ['*.pyc', '__pycache__'])
        delete: Delete files on remote that don't exist locally (default: False)

    Returns:
        Dictionary with operation results
    """
    # Use unified device access to get device info (works for both Foundries and local devices)
    device_info = get_unified_device_info(device_id)
    if "error" in device_info:
        return {
            "success": False,
            "error": device_info["error"],
            "device_id": device_id,
        }

    ip = device_info.get("ip")
    if not ip:
        error_msg = f"Device '{device_id}' has no IP address"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
        }

    device_type = device_info.get("device_type", "unknown")
    resolved_device_id = device_info.get("device_id", device_id)

    # Check local directory exists
    local_path = Path(local_dir)
    if not local_path.exists():
        error_msg = f"Local directory not found: {local_dir}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "local_dir": local_dir,
        }

    if not local_path.is_dir():
        error_msg = f"Local path is not a directory: {local_dir}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "local_dir": local_dir,
        }

    # Determine username
    if not username:
        username = device_info.get("username", "root")
        # Try to get from cached credentials for local devices
        if device_type == "local":
            cred = get_credential(resolved_device_id, "ssh")
            if cred and cred.get("username"):
                username = cred["username"]

    ssh_port = device_info.get("ssh_port", 22)

    try:
        # Check if rsync is available on remote device (use unified device access for SSH)
        from lab_testing.utils.device_access import ssh_to_unified_device

        rsync_check_result = ssh_to_unified_device(device_id, "which rsync")
        if (
            not rsync_check_result.get("success")
            or not rsync_check_result.get("stdout", "").strip()
        ):
            error_msg = "rsync is not installed on the remote device"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "device_id": resolved_device_id,
                "device_type": device_type,
                "local_dir": str(local_path),
                "remote_dir": remote_dir,
                "suggestions": [
                    "Install rsync on device: ssh_to_device(device_id, 'opkg install rsync') or equivalent",
                    "Use copy_files_to_device_parallel for multiple files instead",
                    "Use copy_file_to_device for individual files",
                    "Check device package manager: ssh_to_device(device_id, 'which opkg || which apt || which yum')",
                ],
            }

        # Get or create multiplexed SSH connection for faster transfers (only for local devices)
        control_path = f"/tmp/ssh_mcp_{resolved_device_id}_{ip.replace('.', '_')}"
        master = None
        if device_type == "local":
            master = get_persistent_ssh_connection(ip, username, resolved_device_id, ssh_port)

        # Build rsync command optimized for speed
        rsync_cmd = [
            "rsync",
            "-avz",  # -a: archive, -v: verbose, -z: compress
            "--partial",  # Keep partial files for resume
            "--progress",  # Show progress
        ]

        # Use multiplexed SSH connection if available (only for local devices)
        if master and master.poll() is None:
            # Use existing multiplexed connection (much faster for multiple files)
            rsync_cmd.extend(["-e", f"ssh -o ControlPath={control_path} -o BatchMode=yes"])
            logger.debug(f"Using multiplexed SSH connection for rsync to {resolved_device_id}")
        else:
            # Fallback to direct connection
            rsync_cmd.extend(["-e", "ssh -o StrictHostKeyChecking=no -o BatchMode=yes"])
            logger.debug(f"Using direct SSH connection for rsync to {resolved_device_id}")

        # Add exclude patterns
        if exclude:
            for pattern in exclude:
                rsync_cmd.extend(["--exclude", pattern])

        # Add delete flag
        if delete:
            rsync_cmd.append("--delete")

        # Add source and destination (trailing slash ensures directory contents are synced)
        source = str(local_path)
        if not source.endswith("/"):
            source += "/"
        rsync_cmd.append(source)
        rsync_cmd.append(f"{username}@{ip}:{remote_dir}")

        # Execute rsync
        result = subprocess.run(rsync_cmd, check=False, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            logger.info(f"Successfully synced {local_dir} to {resolved_device_id}:{remote_dir}")
            return {
                "success": True,
                "device_id": resolved_device_id,
                "device_type": device_type,
                "connection_method": "direct",
                "ip": ip,
                "local_dir": str(local_path),
                "remote_dir": remote_dir,
                "message": f"Directory synced successfully to {remote_dir}",
            }

        # If direct connection failed and this is a Foundries device, try VPN server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct rsync failed for Foundries device {device_id}, trying VPN server fallback"
            )
            return _sync_directory_to_device_via_vpn_server(
                device_info, local_dir, remote_dir, username, exclude, delete
            )

        error_msg = f"Failed to sync directory: {result.stderr.strip() or 'Unknown error'}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
            "device_type": device_type,
            "connection_method": "direct",
            "local_dir": str(local_path),
            "remote_dir": remote_dir,
            "suggestions": [
                "Check SSH key is installed: check_ssh_key_status(device_id)",
                "Verify device is online: test_device(device_id)",
                "Check rsync is installed on device: ssh_to_device(device_id, 'which rsync')",
                f"Ensure remote directory exists: ssh_to_device(device_id, 'mkdir -p {remote_dir}')",
            ],
        }

    except subprocess.TimeoutExpired:
        # If timeout and this is a Foundries device, try VPN server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct rsync timed out for Foundries device {device_id}, trying VPN server fallback"
            )
            return _sync_directory_to_device_via_vpn_server(
                device_info, local_dir, remote_dir, username, exclude, delete
            )
        error_msg = "Directory sync timed out (300 seconds)"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
            "device_type": device_type,
            "connection_method": "direct",
        }
    except Exception as e:
        # If exception and this is a Foundries device, try VPN server fallback
        if device_type == "foundries":
            logger.debug(
                f"Direct rsync exception for Foundries device {device_id}, trying VPN server fallback: {e}"
            )
            return _sync_directory_to_device_via_vpn_server(
                device_info, local_dir, remote_dir, username, exclude, delete
            )
        error_msg = f"Failed to sync directory: {e!s}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
            "device_type": device_type,
            "connection_method": "direct",
        }


def _sync_directory_to_device_via_vpn_server(
    device_info: Dict[str, Any],
    local_dir: str,
    remote_dir: str,
    username: str,
    exclude: Optional[list],
    delete: bool,
) -> Dict[str, Any]:
    """
    Sync directory to Foundries device through VPN server (fallback when direct connection fails).

    Args:
        device_info: Device information dictionary from unified device access
        local_dir: Local directory to sync
        remote_dir: Remote destination directory on device
        username: SSH username for device
        exclude: List of patterns to exclude
        delete: Delete files on remote that don't exist locally

    Returns:
        Dictionary with operation results
    """
    device_ip = device_info["ip"]
    device_id = device_info["device_id"]

    # Get VPN server connection info
    server_info = _get_vpn_server_connection_info()
    server_host = server_info["server_host"]
    server_port = server_info["server_port"]
    server_user = server_info["server_user"]
    server_password = server_info["server_password"]

    logger.debug(
        f"Syncing directory to Foundries device {device_id} ({device_ip}) through VPN server {server_host}:{server_port}"
    )

    local_path = Path(local_dir)
    if not local_path.exists() or not local_path.is_dir():
        return {
            "success": False,
            "error": f"Local directory not found or not a directory: {local_dir}",
            "device_id": device_id,
            "connection_method": "through_vpn_server",
        }

    try:
        # Build rsync command with ProxyJump via SSH -e option
        rsync_cmd = [
            "rsync",
            "-avz",  # -a: archive, -v: verbose, -z: compress
            "--partial",  # Keep partial files for resume
            "--progress",  # Show progress
        ]

        # Add ProxyJump via SSH -e option
        proxy_jump = f"{server_user}@{server_host}:{server_port}"
        ssh_options = f"ssh -o ProxyJump={proxy_jump} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
        rsync_cmd.extend(["-e", ssh_options])

        # Add server password if needed (wrap rsync with sshpass)
        if server_password:
            rsync_cmd = ["sshpass", "-p", server_password] + rsync_cmd

        # Add exclude patterns
        if exclude:
            for pattern in exclude:
                rsync_cmd.extend(["--exclude", pattern])

        # Add delete flag
        if delete:
            rsync_cmd.append("--delete")

        # Add source and destination (trailing slash ensures directory contents are synced)
        source = str(local_path)
        if not source.endswith("/"):
            source += "/"
        rsync_cmd.append(source)
        rsync_cmd.append(f"{username}@{device_ip}:{remote_dir}")

        # Execute rsync through VPN server
        result = subprocess.run(rsync_cmd, check=False, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            logger.info(
                f"Successfully synced {local_dir} to {device_id}:{remote_dir} via VPN server"
            )
            return {
                "success": True,
                "device_id": device_id,
                "device_type": device_info.get("device_type", "foundries"),
                "connection_method": "through_vpn_server",
                "ip": device_ip,
                "local_dir": str(local_path),
                "remote_dir": remote_dir,
                "message": f"Directory synced successfully to {remote_dir} via VPN server",
            }

        error_msg = (
            f"Failed to sync directory via VPN server: {result.stderr.strip() or 'Unknown error'}"
        )
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
            "device_type": device_info.get("device_type", "foundries"),
            "connection_method": "through_vpn_server",
            "local_dir": str(local_path),
            "remote_dir": remote_dir,
            "suggestions": [
                "Check VPN server connectivity",
                "Verify device is reachable from VPN server",
                "Check device-to-device communication is enabled",
                "Check rsync is installed on device",
            ],
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Directory sync via VPN server timed out (300 seconds)",
            "device_id": device_id,
            "connection_method": "through_vpn_server",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to sync directory via VPN server: {e!s}",
            "device_id": device_id,
            "connection_method": "through_vpn_server",
        }


def copy_files_to_device_parallel(
    device_id: str,
    file_pairs: List[Tuple[str, str]],
    username: Optional[str] = None,
    preserve_permissions: bool = True,
    max_workers: int = 5,
) -> Dict[str, Any]:
    """
    Copy multiple files to remote device in parallel using multiplexed SSH connections.
    Much faster than copying files sequentially - all transfers share the same SSH connection.

    Args:
        device_id: Device identifier (device_id or friendly_name)
        file_pairs: List of (local_path, remote_path) tuples
        username: SSH username (optional, uses device default)
        preserve_permissions: Preserve file permissions and timestamps (default: True)
        max_workers: Maximum number of parallel transfers (default: 5)

    Returns:
        Dictionary with operation results including individual file results
    """
    # Validate file_pairs
    if not file_pairs:
        error_msg = "No files to transfer (file_pairs is empty)"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
        }

    # Validate file_pairs format
    for pair in file_pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            error_msg = f"Invalid file pair format: {pair}. Expected [local_path, remote_path]"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "device_id": device_id,
            }

    # Resolve to actual device_id
    resolved_device_id = resolve_device_identifier(device_id)
    if not resolved_device_id:
        error_msg = f"Device '{device_id}' not found"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": device_id,
        }

    config = load_device_config()
    devices = config.get("devices", {})
    device = devices.get(resolved_device_id)

    if not device:
        error_msg = f"Device '{resolved_device_id}' not found in config"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }

    ip = device.get("ip")
    if not ip:
        error_msg = f"Device '{resolved_device_id}' has no IP address"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "device_id": resolved_device_id,
        }

    # Determine username
    if not username:
        username = device.get("ssh_user", "root")
        cred = get_credential(resolved_device_id, "ssh")
        if cred and cred.get("username"):
            username = cred["username"]

    ssh_port = device.get("ssh_port", 22)

    # Ensure all local files exist
    missing_files = []
    for local_path, _ in file_pairs:
        if not Path(local_path).exists():
            missing_files.append(local_path)

    if missing_files:
        return {
            "success": False,
            "error": f"Local files not found: {', '.join(missing_files)}",
            "missing_files": missing_files,
        }

    # Ensure multiplexed connection exists (shared by all transfers for maximum speed)
    control_path = f"/tmp/ssh_mcp_{resolved_device_id}_{ip.replace('.', '_')}"
    master = get_persistent_ssh_connection(ip, username, resolved_device_id, ssh_port)

    if not master or master.poll() is not None:
        logger.warning(
            f"Could not establish multiplexed connection for {resolved_device_id}, transfers will be slower"
        )

    # Copy files in parallel
    results = []
    successful = 0
    failed = 0

    def _copy_single_file(local_path: str, remote_path: str) -> Dict[str, Any]:
        """Copy a single file (used by ThreadPoolExecutor)"""
        try:
            # Build scp command with multiplexed connection
            scp_cmd = ["scp"]

            if master and master.poll() is None:
                scp_cmd.extend(["-o", f"ControlPath={control_path}"])
            else:
                scp_cmd.extend(["-o", "StrictHostKeyChecking=no"])
                scp_cmd.extend(["-o", "BatchMode=yes"])

            if preserve_permissions:
                scp_cmd.append("-p")

            scp_cmd.append("-C")  # Compression
            scp_cmd.append(str(local_path))
            scp_cmd.append(f"{username}@{ip}:{remote_path}")

            result = subprocess.run(
                scp_cmd, check=False, capture_output=True, text=True, timeout=120
            )

            return {
                "local_path": local_path,
                "remote_path": remote_path,
                "success": result.returncode == 0,
                "error": result.stderr.strip() if result.returncode != 0 else None,
            }
        except Exception as e:
            return {
                "local_path": local_path,
                "remote_path": remote_path,
                "success": False,
                "error": str(e),
            }

    # Execute transfers in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_copy_single_file, local_path, remote_path): (local_path, remote_path)
            for local_path, remote_path in file_pairs
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result["success"]:
                successful += 1
            else:
                failed += 1

    logger.info(
        f"Parallel file transfer to {resolved_device_id}: {successful} successful, {failed} failed"
    )

    return {
        "success": failed == 0,
        "device_id": resolved_device_id,
        "friendly_name": device.get("friendly_name") or device.get("name", resolved_device_id),
        "ip": ip,
        "total_files": len(file_pairs),
        "successful": successful,
        "failed": failed,
        "results": results,
        "message": f"Transferred {successful}/{len(file_pairs)} files successfully",
        "next_steps": (
            [
                "Review individual file results in 'results' field",
                "Verify files on device: ssh_to_device(device_id, 'ls -lh <remote_path>')",
            ]
            if failed == 0
            else [
                "Some files failed to transfer - check 'results' field for details",
                "Retry failed files individually: copy_file_to_device(device_id, local_path, remote_path)",
            ]
        ),
    }
