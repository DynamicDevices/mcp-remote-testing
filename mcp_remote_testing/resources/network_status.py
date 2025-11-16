"""
Network Status Resource Provider
"""

import subprocess
from typing import Any, Dict

from mcp_remote_testing.tools.vpn_manager import get_vpn_status


def get_network_status() -> Dict[str, Any]:
    """Get current network and VPN status as a resource"""
    vpn_status = get_vpn_status()

    # Get additional network info
    network_info = {
        "vpn": vpn_status
    }

    # Try to get routing info
    try:
        route_result = subprocess.run(
            ["ip", "route", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if route_result.returncode == 0:
            network_info["routes"] = route_result.stdout.split('\n')[:10]  # First 10 routes
    except Exception:
        pass

    return network_info

