"""
Device Inventory Resource Provider
"""

import json
from typing import Any, Dict

from mcp_remote_testing.config import get_lab_devices_config


def get_device_inventory() -> Dict[str, Any]:
    """Get complete device inventory as a resource"""
    try:
        with open(get_lab_devices_config()) as f:
            config = json.load(f)
            return config
    except Exception as e:
        return {
            "error": f"Failed to load device inventory: {e!s}"
        }

