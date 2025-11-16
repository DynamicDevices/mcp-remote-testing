"""
OTA Update Management Tools for Foundries.io
"""

import json
import subprocess
import sys
from typing import Any, Dict, List, Optional

from mcp_remote_testing.config import get_lab_devices_config


def get_device_fio_info(device_id: str) -> Dict[str, Any]:
    """Get Foundries.io information for a device"""
    try:
        with open(get_lab_devices_config(), 'r') as f:
            config = json.load(f)
            devices = config.get("devices", {})
            
            if device_id not in devices:
                return {"error": f"Device {device_id} not found"}
            
            device = devices[device_id]
            return {
                "device_id": device_id,
                "name": device.get("name", "Unknown"),
                "ip": device.get("ip"),
                "fio_factory": device.get("fio_factory"),
                "fio_target": device.get("fio_target"),
                "fio_current": device.get("fio_current"),
                "fio_containers": device.get("fio_containers", [])
            }
    except Exception as e:
        return {"error": f"Failed to get device info: {str(e)}"}


def check_ota_status(device_id: str) -> Dict[str, Any]:
    """
    Check OTA update status for a device.
    
    Args:
        device_id: Device identifier
        
    Returns:
        OTA status information
    """
    device_info = get_device_fio_info(device_id)
    if "error" in device_info:
        return device_info
    
    ip = device_info.get("ip")
    if not ip:
        return {"error": "Device has no IP address"}
    
    # Check aktualizr status via SSH
    try:
        result = ssh_to_device(device_id, "aktualizr-info 2>/dev/null || echo 'aktualizr not available'")
        
        if result.get("success"):
            return {
                "device_id": device_id,
                "status": "checked",
                "output": result.get("stdout", ""),
                "current_target": device_info.get("fio_current"),
                "target": device_info.get("fio_target")
            }
        else:
            return {
                "device_id": device_id,
                "status": "error",
                "error": result.get("stderr", "Unknown error")
            }
    except Exception as e:
        return {"error": f"Failed to check OTA status: {str(e)}"}


def trigger_ota_update(device_id: str, target: Optional[str] = None) -> Dict[str, Any]:
    """
    Trigger OTA update for a device.
    
    Args:
        device_id: Device identifier
        target: Optional target to update to (uses device default if not specified)
        
    Returns:
        Update trigger result
    """
    device_info = get_device_fio_info(device_id)
    if "error" in device_info:
        return device_info
    
    ip = device_info.get("ip")
    if not ip:
        return {"error": "Device has no IP address"}
    
    update_target = target or device_info.get("fio_target")
    if not update_target:
        return {"error": "No target specified and device has no default target"}
    
    try:
        # Trigger update via aktualizr
        result = ssh_to_device(
            device_id,
            f"aktualizr-torizon --update --target {update_target} 2>&1 || aktualizr --update 2>&1"
        )
        
        return {
            "device_id": device_id,
            "target": update_target,
            "success": result.get("success", False),
            "output": result.get("stdout", ""),
            "error": result.get("stderr", "")
        }
    except Exception as e:
        return {"error": f"Failed to trigger OTA update: {str(e)}"}


def list_containers(device_id: str) -> Dict[str, Any]:
    """
    List containers on a device.
    
    Args:
        device_id: Device identifier
        
    Returns:
        Container list
    """
    device_info = get_device_fio_info(device_id)
    if "error" in device_info:
        return device_info
    
    try:
        result = ssh_to_device(device_id, "docker ps -a --format '{{.Names}}\t{{.Status}}\t{{.Image}}'")
        
        if result.get("success"):
            containers = []
            for line in result.get("stdout", "").strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        containers.append({
                            "name": parts[0],
                            "status": parts[1],
                            "image": parts[2]
                        })
            
            return {
                "device_id": device_id,
                "containers": containers,
                "count": len(containers)
            }
        else:
            return {
                "device_id": device_id,
                "error": result.get("stderr", "Failed to list containers")
            }
    except Exception as e:
        return {"error": f"Failed to list containers: {str(e)}"}


def deploy_container(device_id: str, container_name: str, image: str) -> Dict[str, Any]:
    """
    Deploy/update a container on a device.
    
    Args:
        device_id: Device identifier
        container_name: Container name
        image: Container image to deploy
        
    Returns:
        Deployment result
    """
    device_info = get_device_fio_info(device_id)
    if "error" in device_info:
        return device_info
    
    try:
        # Stop existing container, pull new image, start
        commands = [
            f"docker stop {container_name} 2>/dev/null || true",
            f"docker rm {container_name} 2>/dev/null || true",
            f"docker pull {image}",
            f"docker run -d --name {container_name} {image}"
        ]
        
        results = []
        for cmd in commands:
            result = ssh_to_device(device_id, cmd)
            results.append({
                "command": cmd,
                "success": result.get("success", False),
                "output": result.get("stdout", ""),
                "error": result.get("stderr", "")
            })
        
        return {
            "device_id": device_id,
            "container_name": container_name,
            "image": image,
            "steps": results,
            "success": all(r["success"] for r in results[:-1])  # Last step may fail if container already running
        }
    except Exception as e:
        return {"error": f"Failed to deploy container: {str(e)}"}


def get_system_status(device_id: str) -> Dict[str, Any]:
    """
    Get comprehensive system status for a device.
    
    Args:
        device_id: Device identifier
        
    Returns:
        System status information
    """
    device_info = get_device_fio_info(device_id)
    if "error" in device_info:
        return device_info
    
    try:
        # Collect system info
        status = {
            "device_id": device_id,
            "uptime": "",
            "load": "",
            "memory": "",
            "disk": "",
            "kernel": "",
            "fio_version": ""
        }
        
        # Get uptime
        result = ssh_to_device(device_id, "uptime")
        if result.get("success"):
            status["uptime"] = result.get("stdout", "").strip()
        
        # Get load average
        result = ssh_to_device(device_id, "cat /proc/loadavg")
        if result.get("success"):
            status["load"] = result.get("stdout", "").strip()
        
        # Get memory
        result = ssh_to_device(device_id, "free -h | grep Mem")
        if result.get("success"):
            status["memory"] = result.get("stdout", "").strip()
        
        # Get disk
        result = ssh_to_device(device_id, "df -h / | tail -1")
        if result.get("success"):
            status["disk"] = result.get("stdout", "").strip()
        
        # Get kernel version
        result = ssh_to_device(device_id, "uname -r")
        if result.get("success"):
            status["kernel"] = result.get("stdout", "").strip()
        
        # Get Foundries.io version if available
        result = ssh_to_device(device_id, "cat /etc/os-release | grep VERSION_ID || echo ''")
        if result.get("success"):
            status["fio_version"] = result.get("stdout", "").strip()
        
        return status
        
    except Exception as e:
        return {"error": f"Failed to get system status: {str(e)}"}

