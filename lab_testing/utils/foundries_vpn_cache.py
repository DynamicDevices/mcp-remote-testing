"""
Foundries VPN IP Address Cache

Caches Foundries device VPN IP addresses for quick lookups.
IPs are discovered from WireGuard server /etc/hosts file or fioctl.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from lab_testing.config import CACHE_DIR
from lab_testing.utils.logger import get_logger

logger = get_logger()

# Cache file path
VPN_IP_CACHE_FILE = CACHE_DIR / "foundries_vpn_ips.json"

# Cache expiration time (7 days - IPs don't change often)
CACHE_EXPIRY_SECONDS = 7 * 24 * 60 * 60

# Lock for cache file operations
_cache_lock = threading.Lock()


def _ensure_cache_dir():
    """Ensure cache directory exists"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_vpn_ip_cache() -> Dict[str, Any]:
    """Load VPN IP cache from file"""
    _ensure_cache_dir()

    if not VPN_IP_CACHE_FILE.exists():
        return {}

    try:
        with open(VPN_IP_CACHE_FILE) as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to load VPN IP cache (corrupted JSON): {e}")
        # Try to recover by backing up corrupted cache
        try:
            backup_file = VPN_IP_CACHE_FILE.with_suffix(".json.bak")
            import shutil

            if VPN_IP_CACHE_FILE.exists():
                shutil.copy2(VPN_IP_CACHE_FILE, backup_file)
                logger.info(f"Backed up corrupted cache to {backup_file}")
        except Exception:
            pass
        return {}
    except OSError as e:
        logger.warning(f"Failed to read VPN IP cache: {e}")
        return {}


def save_vpn_ip_cache(cache: Dict[str, Any]):
    """Save VPN IP cache to file (atomic write)"""
    with _cache_lock:
        _ensure_cache_dir()

        # Use atomic write: write to temp file, then rename
        temp_file = CACHE_DIR / f"{VPN_IP_CACHE_FILE.name}.tmp"

        try:
            with open(temp_file, "w") as f:
                json.dump(cache, f, indent=2)
                f.flush()
                import os

                os.fsync(f.fileno())

            # Atomic rename
            import os

            os.replace(str(temp_file), str(VPN_IP_CACHE_FILE))
        except OSError as e:
            logger.warning(f"Failed to save VPN IP cache: {e}")
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass


def get_vpn_ip(device_name: str) -> Optional[str]:
    """
    Get cached VPN IP address for a Foundries device.

    Args:
        device_name: Foundries device name (e.g., "imx8mm-jaguar-inst-2240a09dab86563")

    Returns:
        VPN IP address or None if not cached or expired
    """
    cache = load_vpn_ip_cache()
    entry = cache.get(device_name)

    if not entry:
        return None

    # Check if cache is expired
    cached_time = entry.get("cached_at", 0)
    if time.time() - cached_time > CACHE_EXPIRY_SECONDS:
        logger.debug(f"VPN IP cache expired for {device_name}")
        return None

    return entry.get("vpn_ip")


def cache_vpn_ip(device_name: str, vpn_ip: str, source: str = "unknown"):
    """
    Cache VPN IP address for a Foundries device.

    Args:
        device_name: Foundries device name
        vpn_ip: VPN IP address
        source: Source of the IP (e.g., "wireguard_server_hosts", "fioctl", "manual")
    """
    cache = load_vpn_ip_cache()

    cache[device_name] = {
        "vpn_ip": vpn_ip,
        "cached_at": time.time(),
        "source": source,
    }

    save_vpn_ip_cache(cache)
    logger.debug(f"Cached VPN IP for {device_name}: {vpn_ip} (source: {source})")


def get_all_cached_ips() -> Dict[str, Dict[str, Any]]:
    """
    Get all cached VPN IP addresses.

    Returns:
        Dictionary mapping device_name -> cache entry (with vpn_ip, cached_at, source)
    """
    cache = load_vpn_ip_cache()
    current_time = time.time()

    # Filter out expired entries
    valid_cache = {}
    for device_name, entry in cache.items():
        cached_time = entry.get("cached_at", 0)
        if current_time - cached_time <= CACHE_EXPIRY_SECONDS:
            valid_cache[device_name] = entry

    return valid_cache


def clear_vpn_ip_cache():
    """Clear all cached VPN IP addresses"""
    _ensure_cache_dir()
    if VPN_IP_CACHE_FILE.exists():
        VPN_IP_CACHE_FILE.unlink()
        logger.info("VPN IP cache cleared")


def remove_vpn_ip(device_name: str) -> bool:
    """
    Remove a device from the VPN IP cache.

    Args:
        device_name: Foundries device name to remove

    Returns:
        True if removed, False if not found
    """
    cache = load_vpn_ip_cache()

    if device_name not in cache:
        return False

    del cache[device_name]
    save_vpn_ip_cache(cache)
    logger.info(f"Removed VPN IP cache entry for {device_name}")
    return True
