"""
Tasmota Device Control Tools for MCP Server
"""

import json
import subprocess
import sys
from typing import Any, Dict, Optional

from mcp_remote_testing.config import get_lab_devices_config, get_scripts_dir


def tasmota_control(
    device_id: str,
    action: str,
    value: Optional[str] = None
) -> Dict[str, Any]:
    """
    Control a Tasmota device (power switch, etc.).

    Args:
        device_id: Tasmota device ID
        action: Action to perform (on, off, toggle, status, energy)
        value: Optional value for the action

    Returns:
        Dictionary with control results
    """
    scripts_dir = get_scripts_dir()
    tasmota_script = scripts_dir / "tasmota_controller.py"

    if not tasmota_script.exists():
        return {
            "success": False,
            "error": f"Tasmota controller script not found: {tasmota_script}"
        }

    # Load device config to verify device exists
    try:
        with open(get_lab_devices_config(), 'r') as f:
            config = json.load(f)
            devices = config.get("devices", {})

            if device_id not in devices:
                return {
                    "success": False,
                    "error": f"Device '{device_id}' not found in configuration"
                }

            device = devices[device_id]
            if device.get("device_type") != "tasmota_device":
                return {
                    "success": False,
                    "error": f"Device '{device_id}' is not a Tasmota device"
                }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load device configuration: {str(e)}"
        }

    # Build command based on action
    cmd = [sys.executable, str(tasmota_script), "--device", device_id]

    if action == "on":
        cmd.append("--on")
    elif action == "off":
        cmd.append("--off")
    elif action == "toggle":
        cmd.append("--toggle")
    elif action == "status":
        cmd.append("--status")
    elif action == "energy":
        cmd.append("--energy")
    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}. Valid actions: on, off, toggle, status, energy"
        }

    # Execute command
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            # Try to parse JSON output if available
            try:
                output_data = json.loads(result.stdout)
                return {
                    "success": True,
                    "device_id": device_id,
                    "action": action,
                    "result": output_data
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "device_id": device_id,
                    "action": action,
                    "output": result.stdout,
                    "message": "Command executed successfully"
                }
        else:
            return {
                "success": False,
                "device_id": device_id,
                "action": action,
                "error": result.stderr or result.stdout
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "device_id": device_id,
            "error": "Command timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "device_id": device_id,
            "error": f"Command execution failed: {str(e)}"
        }


def list_tasmota_devices() -> Dict[str, Any]:
    """
    List all configured Tasmota devices.

    Returns:
        Dictionary with Tasmota device list
    """
    try:
        with open(get_lab_devices_config(), 'r') as f:
            config = json.load(f)
            devices = config.get("devices", {})

            tasmota_devices = []
            for device_id, device_info in devices.items():
                if device_info.get("device_type") == "tasmota_device":
                    tasmota_devices.append({
                        "id": device_id,
                        "name": device_info.get("name", "Unknown"),
                        "ip": device_info.get("ip", "Unknown"),
                        "type": device_info.get("tasmota_type", "unknown"),
                        "version": device_info.get("version", "Unknown"),
                        "status": device_info.get("status", "unknown")
                    })

            return {
                "success": True,
                "devices": tasmota_devices,
                "count": len(tasmota_devices)
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load Tasmota devices: {str(e)}"
        }

