"""
Tasmota Device Control Tools for MCP Server
"""

import json
import subprocess
import sys
from typing import Any, Dict, List, Optional

from lab_testing.config import get_lab_devices_config, get_scripts_dir


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
        with open(get_lab_devices_config()) as f:
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
            "error": f"Failed to load device configuration: {e!s}"
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
            check=False, capture_output=True,
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
            "error": f"Command execution failed: {e!s}"
        }


def list_tasmota_devices() -> Dict[str, Any]:
    """
    List all configured Tasmota devices.

    Returns:
        Dictionary with Tasmota device list
    """
    try:
        with open(get_lab_devices_config()) as f:
            config = json.load(f)
            devices = config.get("devices", {})

            tasmota_devices = []
            for device_id, device_info in devices.items():
                if device_info.get("device_type") == "tasmota_device":
                    tasmota_devices.append({
                        "id": device_id,
                        "name": device_info.get("name", "Unknown"),
                        "friendly_name": device_info.get("friendly_name") or device_info.get("name", device_id),
                        "ip": device_info.get("ip", "Unknown"),
                        "type": device_info.get("tasmota_type", "unknown"),
                        "version": device_info.get("version", "Unknown"),
                        "status": device_info.get("status", "unknown"),
                        "controls_devices": _get_devices_controlled_by(device_id, config)
                    })

            return {
                "success": True,
                "devices": tasmota_devices,
                "count": len(tasmota_devices)
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load Tasmota devices: {e!s}"
        }


def _get_devices_controlled_by(tasmota_device_id: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get list of devices controlled by a Tasmota switch"""
    devices = config.get("devices", {})
    controlled = []
    
    for device_id, device_info in devices.items():
        power_switch = device_info.get("power_switch")
        if power_switch == tasmota_device_id:
            controlled.append({
                "device_id": device_id,
                "friendly_name": device_info.get("friendly_name") or device_info.get("name", device_id),
                "name": device_info.get("name", "Unknown"),
                "device_type": device_info.get("device_type", "unknown")
            })
    
    return controlled


def get_power_switch_for_device(device_id_or_name: str) -> Optional[Dict[str, Any]]:
    """
    Get the Tasmota power switch that controls a device.
    
    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)
    
    Returns:
        Dictionary with power switch info, or None if not found
    """
    try:
        from lab_testing.tools.device_manager import resolve_device_identifier
        
        # Resolve to actual device_id
        device_id = resolve_device_identifier(device_id_or_name)
        if not device_id:
            return None
        
        with open(get_lab_devices_config()) as f:
            config = json.load(f)
            devices = config.get("devices", {})
            
            if device_id not in devices:
                return None
            
            device = devices[device_id]
            power_switch_id = device.get("power_switch")
            
            if not power_switch_id:
                return None
            
            # Get Tasmota device info
            if power_switch_id in devices:
                switch_info = devices[power_switch_id]
                return {
                    "tasmota_device_id": power_switch_id,
                    "tasmota_name": switch_info.get("name", "Unknown"),
                    "tasmota_friendly_name": switch_info.get("friendly_name") or switch_info.get("name", power_switch_id),
                    "tasmota_ip": switch_info.get("ip"),
                    "tasmota_type": switch_info.get("tasmota_type", "unknown")
                }
            
            return None
    except Exception as e:
        return None


def power_cycle_device(device_id_or_name: str, off_duration: int = 5) -> Dict[str, Any]:
    """
    Power cycle a device by controlling its Tasmota power switch.
    
    Supports both device_id and friendly_name lookup.
    
    Args:
        device_id_or_name: Device identifier (device_id or friendly_name) to power cycle
        off_duration: Duration in seconds to keep power off (default: 5)
    
    Returns:
        Dictionary with power cycle results
    """
    import time
    from lab_testing.tools.device_manager import resolve_device_identifier
    
    # Resolve to actual device_id
    device_id = resolve_device_identifier(device_id_or_name)
    if not device_id:
        return {
            "success": False,
            "error": f"Device '{device_id_or_name}' not found in configuration",
            "suggestions": [
                "Use 'list_devices' to see available devices",
                "You can use either device_id or friendly_name"
            ]
        }
    
    # Get power switch mapping
    power_switch = get_power_switch_for_device(device_id)
    
    if not power_switch:
        return {
            "success": False,
            "error": f"No power switch configured for device '{device_id}'. Add 'power_switch' field to device config.",
            "suggestions": [
                "Check device configuration for 'power_switch' field",
                "Use 'list_tasmota_devices' to see available switches",
                "Add 'power_switch': 'tasmota_device_id' to device config"
            ]
        }
    
    tasmota_id = power_switch["tasmota_device_id"]
    
    try:
        # Turn power off
        off_result = tasmota_control(tasmota_id, "off")
        if not off_result.get("success"):
            return {
                "success": False,
                "error": f"Failed to turn off power switch '{tasmota_id}'",
                "tasmota_error": off_result.get("error")
            }
        
        # Wait for off duration
        time.sleep(off_duration)
        
        # Turn power on
        on_result = tasmota_control(tasmota_id, "on")
        if not on_result.get("success"):
            return {
                "success": False,
                "error": f"Failed to turn on power switch '{tasmota_id}'",
                "tasmota_error": on_result.get("error"),
                "warning": "Device power was turned off but failed to turn back on"
            }
        
        return {
            "success": True,
            "device_id": device_id,
            "power_switch": power_switch,
            "off_duration": off_duration,
            "message": f"Device '{device_id}' power cycled successfully via '{power_switch['tasmota_friendly_name']}'"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Power cycle failed: {e!s}",
            "device_id": device_id,
            "power_switch": power_switch
        }

