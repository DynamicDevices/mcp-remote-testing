"""
Remote Access Tools for SSH Tunnels and Serial Port Access

Supports:
- SSH tunnels through VPN for direct device access
- Serial port access via remote Linux laptops (for low power/bootup debugging)

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import subprocess
from typing import Any, Dict, Optional

from lab_testing.exceptions import DeviceConnectionError, DeviceNotFoundError, SSHError
from lab_testing.tools.device_manager import get_device_info as _get_device_info
from lab_testing.utils.credentials import get_ssh_command
from lab_testing.utils.logger import get_logger

logger = get_logger()


def create_ssh_tunnel(
    device_id: str,
    local_port: Optional[int] = None,
    remote_port: int = 22,
    tunnel_type: str = "local",
) -> Dict[str, Any]:
    """
    Create an SSH tunnel to a device through VPN.

    Args:
        device_id: Device identifier
        local_port: Local port to bind (auto-assigned if None)
        remote_port: Remote SSH port (default: 22)
        tunnel_type: "local" (forward local port) or "remote" (reverse tunnel)

    Returns:
        Tunnel information
    """
    device_info = get_device_info(device_id)
    if not device_info:
        raise DeviceNotFoundError(f"Device {device_id} not found", device_id=device_id)

    ip = device_info.get("ip")
    username = device_info.get("ssh_user", "root")

    if not ip:
        raise DeviceConnectionError(f"Device {device_id} has no IP address", device_id=device_id)

    # Auto-assign local port if not specified
    if local_port is None:
        # Find an available port (simple approach: use a high port)
        import socket

        sock = socket.socket()
        sock.bind(("", 0))
        local_port = sock.getsockname()[1]
        sock.close()

    try:
        if tunnel_type == "local":
            # Local port forwarding: -L local_port:remote_host:remote_port
            ssh_cmd = [
                "ssh",
                "-N",
                "-f",  # -N: no command, -f: background
                "-L",
                f"{local_port}:{ip}:{remote_port}",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ServerAliveInterval=60",
                f"{username}@{ip}",
            ]
        else:
            # Remote port forwarding: -R remote_port:local_host:local_port
            ssh_cmd = [
                "ssh",
                "-N",
                "-f",
                "-R",
                f"{remote_port}:localhost:{local_port}",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ServerAliveInterval=60",
                f"{username}@{ip}",
            ]

        # Use credential helper for SSH command
        ssh_cmd = get_ssh_command(ip, username, "", device_id, use_password=False)
        # Replace empty command with tunnel options
        ssh_cmd = ssh_cmd[:-1]  # Remove empty command
        ssh_cmd.extend(["-N", "-f", "-L", f"{local_port}:{ip}:{remote_port}"])

        result = subprocess.run(ssh_cmd, check=False, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            logger.info(
                f"SSH tunnel created for {device_id}: localhost:{local_port} -> {ip}:{remote_port}"
            )
            return {
                "success": True,
                "device_id": device_id,
                "tunnel_type": tunnel_type,
                "local_port": local_port,
                "remote_host": ip,
                "remote_port": remote_port,
                "connection_string": f"ssh -p {local_port} {username}@localhost",
                "message": f"Tunnel active. Connect with: ssh -p {local_port} {username}@localhost",
            }
        error_msg = f"Failed to create SSH tunnel: {result.stderr}"
        logger.error(error_msg)
        raise SSHError(error_msg, device_id=device_id)

    except subprocess.TimeoutExpired:
        raise SSHError("SSH tunnel creation timed out", device_id=device_id)
    except Exception as e:
        logger.error(f"SSH tunnel creation failed for {device_id}: {e}", exc_info=True)
        raise SSHError(f"Tunnel creation failed: {e!s}", device_id=device_id)


def list_ssh_tunnels() -> Dict[str, Any]:
    """List active SSH tunnels"""
    try:
        # Find SSH processes with -L or -R options
        result = subprocess.run(
            ["ps", "aux"], check=False, capture_output=True, text=True, timeout=5
        )

        tunnels = []
        for line in result.stdout.split("\n"):
            if "ssh" in line and ("-L" in line or "-R" in line):
                tunnels.append(line.strip())

        return {"success": True, "tunnel_count": len(tunnels), "tunnels": tunnels}
    except Exception as e:
        logger.error(f"Failed to list SSH tunnels: {e}")
        return {"error": f"Failed to list tunnels: {e!s}"}


def close_ssh_tunnel(
    local_port: Optional[int] = None, device_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Close an SSH tunnel.

    Args:
        local_port: Local port of tunnel to close
        device_id: Device ID (alternative to local_port)
    """
    try:
        if device_id:
            device_info = get_device_info(device_id)
            if device_info:
                ip = device_info.get("ip")
                # Find tunnel by device IP
                result = subprocess.run(
                    ["ps", "aux"], check=False, capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "ssh" in line and ip in line and ("-L" in line or "-R" in line):
                        # Extract PID
                        parts = line.split()
                        if len(parts) > 1:
                            pid = int(parts[1])
                            subprocess.run(["kill", str(pid)], check=False, timeout=5)
                            logger.info(f"Closed SSH tunnel for {device_id} (PID {pid})")
                            return {"success": True, "device_id": device_id, "pid": pid}

        if local_port:
            # Find tunnel by local port
            result = subprocess.run(
                ["lsof", "-ti", f":{local_port}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                pid = int(result.stdout.strip())
                subprocess.run(["kill", str(pid)], check=False, timeout=5)
                logger.info(f"Closed SSH tunnel on port {local_port} (PID {pid})")
                return {"success": True, "local_port": local_port, "pid": pid}

        return {"error": "No tunnel found to close"}

    except Exception as e:
        logger.error(f"Failed to close SSH tunnel: {e}")
        return {"error": f"Failed to close tunnel: {e!s}"}


def access_serial_port(
    remote_laptop_id: str,
    serial_device: str = "/dev/ttyACM0",
    baud_rate: int = 115200,
    duration: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Access serial port on a remote Linux laptop via SSH.

    Useful for:
    - Low power operation with WiFi disabled
    - Bootup problems
    - Direct serial logging

    Args:
        remote_laptop_id: Device ID of the remote Linux laptop
        serial_device: Serial device path (e.g., /dev/ttyACM0, /dev/ttyUSB0)
        baud_rate: Baud rate (default: 115200)
        duration: Duration in seconds (None = continuous)

    Returns:
        Connection information
    """
    device_info = get_device_info(remote_laptop_id)
    if not device_info:
        raise DeviceNotFoundError(
            f"Remote laptop {remote_laptop_id} not found", device_id=remote_laptop_id
        )

    ip = device_info.get("ip")
    username = device_info.get("ssh_user", "root")

    if not ip:
        raise DeviceConnectionError(
            f"Remote laptop {remote_laptop_id} has no IP address", device_id=remote_laptop_id
        )

    # Check if serial device exists on remote laptop
    check_cmd = f"test -c {serial_device} && echo 'EXISTS' || echo 'NOT_FOUND'"
    result = subprocess.run(
        get_ssh_command(ip, username, check_cmd, remote_laptop_id, use_password=False),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    if "NOT_FOUND" in result.stdout:
        # Try to list available serial devices
        list_cmd = "ls -la /dev/tty{ACM,USB}* 2>/dev/null || echo 'NONE'"
        list_result = subprocess.run(
            get_ssh_command(ip, username, list_cmd, remote_laptop_id, use_password=False),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        available = list_result.stdout.strip() if list_result.returncode == 0 else "Unknown"

        return {
            "error": f"Serial device {serial_device} not found on {remote_laptop_id}",
            "available_devices": available,
            "suggestion": "Use list_serial_devices to find available devices",
        }

    # Create SSH command to access serial port
    # Use screen or minicom for serial access
    screen_cmd = f"screen {serial_device} {baud_rate}"
    minicom_cmd = f"minicom -D {serial_device} -b {baud_rate}"

    # Try screen first (more common)
    test_screen = subprocess.run(
        get_ssh_command(ip, username, "which screen", remote_laptop_id, use_password=False),
        check=False,
        capture_output=True,
        timeout=5,
    )

    if test_screen.returncode == 0:
        command = screen_cmd
        tool = "screen"
    else:
        # Fallback to minicom
        test_minicom = subprocess.run(
            get_ssh_command(ip, username, "which minicom", remote_laptop_id, use_password=False),
            check=False,
            capture_output=True,
            timeout=5,
        )
        if test_minicom.returncode == 0:
            command = minicom_cmd
            tool = "minicom"
        else:
            return {
                "error": "Neither screen nor minicom available on remote laptop",
                "suggestion": "Install screen or minicom on the remote laptop",
            }

    # Create interactive SSH session command
    ssh_cmd = get_ssh_command(ip, username, command, remote_laptop_id, use_password=False)
    # Remove BatchMode for interactive session
    if "-o" in ssh_cmd and "BatchMode" in ssh_cmd:
        idx = ssh_cmd.index("-o")
        ssh_cmd.pop(idx)  # Remove -o
        ssh_cmd.pop(idx)  # Remove BatchMode=yes

    return {
        "success": True,
        "remote_laptop_id": remote_laptop_id,
        "serial_device": serial_device,
        "baud_rate": baud_rate,
        "tool": tool,
        "command": " ".join(ssh_cmd),
        "connection_instructions": f"Run: {' '.join(ssh_cmd)}",
        "note": "This is an interactive session. Use Ctrl+A then K to exit screen, or Ctrl+A then X for minicom.",
        "duration": duration,
    }


def list_serial_devices(remote_laptop_id: str) -> Dict[str, Any]:
    """
    List available serial devices on a remote Linux laptop.

    Args:
        remote_laptop_id: Device ID of the remote Linux laptop

    Returns:
        List of available serial devices
    """
    device_info = get_device_info(remote_laptop_id)
    if not device_info:
        raise DeviceNotFoundError(
            f"Remote laptop {remote_laptop_id} not found", device_id=remote_laptop_id
        )

    ip = device_info.get("ip")
    username = device_info.get("ssh_user", "root")

    if not ip:
        raise DeviceConnectionError(
            f"Remote laptop {remote_laptop_id} has no IP address", device_id=remote_laptop_id
        )

    # List USB CDC and USB serial devices
    list_cmd = "ls -la /dev/tty{ACM,USB}* 2>/dev/null | awk '{print $10, $5, $6}' || echo 'NONE'"

    try:
        result = subprocess.run(
            get_ssh_command(ip, username, list_cmd, remote_laptop_id, use_password=False),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        devices = []
        if result.returncode == 0 and "NONE" not in result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip() and "/dev/" in line:
                    parts = line.split()
                    if len(parts) >= 1:
                        devices.append(
                            {
                                "device": parts[0],
                                "major": parts[1] if len(parts) > 1 else "unknown",
                                "minor": parts[2] if len(parts) > 2 else "unknown",
                            }
                        )

        return {
            "success": True,
            "remote_laptop_id": remote_laptop_id,
            "devices": devices,
            "count": len(devices),
        }

    except Exception as e:
        logger.error(f"Failed to list serial devices on {remote_laptop_id}: {e}")
        raise SSHError(f"Failed to list serial devices: {e!s}", device_id=remote_laptop_id)


def get_device_info(device_id: str) -> Optional[Dict[str, Any]]:
    """Get device information from config (wrapper)"""
    return _get_device_info(device_id)
