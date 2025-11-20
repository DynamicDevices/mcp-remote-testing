"""
Foundries.io Device Management Tools for MCP Server

Provides tools for listing and managing Foundries devices in a factory.
Uses fioctl CLI to interact with FoundriesFactory API.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import subprocess
from typing import Any, Dict, Optional

# Import shared fioctl helpers from foundries_vpn module
from lab_testing.tools.foundries_vpn import (
    _check_fioctl_configured,
    _check_fioctl_installed,
    _get_fioctl_path,
)
from lab_testing.utils.foundries_vpn_cache import cache_vpn_ip, get_vpn_ip
from lab_testing.utils.logger import get_logger

logger = get_logger()


def list_foundries_devices(factory: Optional[str] = None) -> Dict[str, Any]:
    """
    List all Foundries devices in a factory.

    Uses fioctl to list devices in the FoundriesFactory. Includes device metadata
    such as name, target, status, apps, creation date, last seen, owner, tags, etc.
    Optionally includes VPN IP addresses if available.

    Args:
        factory: Optional factory name. If not provided, uses default factory from fioctl config.

    Returns:
        Dictionary with list of Foundries devices and metadata
    """
    try:
        # Check if fioctl is installed and configured
        fioctl_installed, fioctl_error = _check_fioctl_installed()
        if not fioctl_installed:
            return {
                "success": False,
                "error": fioctl_error,
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                ],
            }

        fioctl_configured, config_error = _check_fioctl_configured()
        if not fioctl_configured:
            return {
                "success": False,
                "error": config_error,
                "suggestions": [
                    "Run 'fioctl login' to configure FoundriesFactory credentials",
                ],
            }

        # Get fioctl path
        fioctl_path = _get_fioctl_path()
        if not fioctl_path:
            return {
                "success": False,
                "error": "fioctl not found",
                "suggestions": [
                    "Install fioctl CLI tool: https://github.com/foundriesio/fioctl",
                ],
            }

        # Build fioctl command with all useful columns
        # Available columns: name, target, status, apps, up-to-date, is-prod, created-at,
        # created-by, current-update, device-group, is-wave, last-seen, ostree-hash,
        # owner, tag, updated-at, updated-by, uuid
        cmd = [
            fioctl_path,
            "devices",
            "list",
            "--columns",
            "name,target,status,apps,up-to-date,is-prod,created-at,last-seen,device-group,tag,owner,updated-at,ostree-hash,uuid",
        ]
        if factory:
            cmd.extend(["--factory", factory])

        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return {
                "success": False,
                "error": f"Failed to list Foundries devices: {error_msg}",
                "suggestions": [
                    "Check fioctl is configured correctly: 'fioctl factories list'",
                    "Ensure you have access to the factory",
                ],
            }

        # Parse fioctl output (table format)
        # fioctl devices list outputs a table with columns: NAME, TARGET, STATUS, APPS, UP-TO-DATE, IS-PROD, CREATED-AT, etc.
        # Columns are space-aligned, so we need to handle multi-word values carefully
        lines = result.stdout.strip().split("\n")
        devices = []

        # Skip header and separator lines
        for line in lines:
            line = line.rstrip()  # Keep leading spaces for column detection
            # Skip empty lines, header row, and separator row (lines starting with ----)
            if (
                not line.strip()
                or line.strip().startswith("NAME")
                or line.strip().startswith("----")
            ):
                continue

            # Split by multiple spaces to handle column alignment
            # Format: NAME (50 chars) TARGET (30 chars) STATUS (10 chars) APPS (variable) UP-TO-DATE IS-PROD
            parts = [p for p in line.split("  ") if p.strip()]  # Split by double spaces

            if len(parts) >= 3:
                device_name = parts[0].strip()

                # Handle multi-word TARGET (e.g., "Initial Target")
                # If STATUS is "Target", then TARGET is actually two words
                target_parts = parts[1].strip().split()
                if len(target_parts) >= 2 and len(parts) > 2 and parts[2].strip() == "Target":
                    # "Initial Target" case - combine first two parts
                    target = " ".join(target_parts[:2])
                    status = parts[2].strip() if len(parts) > 2 else "unknown"
                    apps_start_idx = 3
                else:
                    target = target_parts[0] if target_parts else "Unknown"
                    status = parts[2].strip() if len(parts) > 2 else "unknown"
                    apps_start_idx = 3

                # Extract fields from columns:
                # Column order: name, target, status, apps, up-to-date, is-prod, created-at,
                # last-seen, device-group, tag, owner, updated-at, ostree-hash, uuid
                # Note: Empty fields (device-group, updated-at) are skipped when splitting
                apps = ""
                up_to_date = "unknown"
                is_prod = "unknown"
                created_at = None
                last_seen = None
                device_group = None
                tag = None
                owner = None
                updated_at = None
                ostree_hash = None
                uuid = None

                # Parse based on known positions
                # Fixed positions: name[0], target[1], status[2], apps[3], up-to-date[4], is-prod[5]
                # created-at[6], last-seen[7], then variable: device-group[8] (may be empty), tag[8 or 9],
                # owner[9 or 10], updated-at[10 or 11] (may be empty), ostree-hash[10 or 11], uuid[11 or 12]
                
                if len(parts) >= 6:
                    # At minimum: name, target, status, apps, up-to-date, is-prod
                    up_to_date = parts[4].strip() if len(parts) > 4 else "unknown"
                    is_prod = parts[5].strip() if len(parts) > 5 else "unknown"
                    apps = parts[3].strip() if len(parts) > 3 else ""
                
                if len(parts) >= 8:
                    # Has: name, target, status, apps, up-to-date, is-prod, created-at, last-seen
                    created_at = parts[6].strip() if len(parts) > 6 else None
                    last_seen = parts[7].strip() if len(parts) > 7 else None
                
                # For remaining fields, parse from the end (most reliable)
                # UUID is always last (if present), ostree-hash is second-to-last, etc.
                if len(parts) >= 12:
                    # Has all fields (device-group and updated-at may be empty, so we have 12 parts)
                    # parts: [name, target, status, apps, up-to-date, is-prod, created-at, last-seen, tag, owner, ostree-hash, uuid]
                    uuid = parts[11].strip() if len(parts) > 11 else None
                    ostree_hash = parts[10].strip() if len(parts) > 10 else None
                    owner = parts[9].strip() if len(parts) > 9 else None
                    tag = parts[8].strip() if len(parts) > 8 else None
                    # device-group and updated-at are empty in this case
                elif len(parts) >= 10:
                    # Has: name, target, status, apps, up-to-date, is-prod, created-at, last-seen, tag, owner
                    tag = parts[8].strip() if len(parts) > 8 else None
                    owner = parts[9].strip() if len(parts) > 9 else None
                    if len(parts) > 10:
                        ostree_hash = parts[10].strip()
                    if len(parts) > 11:
                        uuid = parts[11].strip()
                elif len(parts) >= 8:
                    # Has: name, target, status, apps, up-to-date, is-prod, created-at, last-seen
                    # Try to get remaining fields if present
                    if len(parts) > 8:
                        tag = parts[8].strip()
                    if len(parts) > 9:
                        owner = parts[9].strip()
                    if len(parts) > 10:
                        ostree_hash = parts[10].strip()
                    if len(parts) > 11:
                        uuid = parts[11].strip()

                # Try to get VPN IP from cache first (optional - VPN IP is not required)
                vpn_ip = get_vpn_ip(device_name)

                # If not in cache, try to get from fioctl device config
                if not vpn_ip:
                    try:
                        fioctl_path = _get_fioctl_path()
                        if fioctl_path:
                            config_cmd = [
                                fioctl_path,
                                "devices",
                                "config",
                                device_name,
                                "wireguard",
                            ]
                            if factory:
                                config_cmd.extend(["--factory", factory])

                            config_result = subprocess.run(
                                config_cmd,
                                check=False,
                                capture_output=True,
                                text=True,
                                timeout=5,
                            )

                            if config_result.returncode == 0:
                                # Parse output for address= line
                                for line in config_result.stdout.split("\n"):
                                    line = line.strip()
                                    if line.startswith("address="):
                                        ip_addr = line.split("=", 1)[1].strip()
                                        if ip_addr and ip_addr != "(none)":
                                            vpn_ip = ip_addr
                                            # Cache it for future use
                                            cache_vpn_ip(device_name, vpn_ip, source="fioctl")
                                            break
                    except Exception as e:
                        logger.debug(f"Failed to get VPN IP from fioctl for {device_name}: {e}")

                device_info = {
                    "name": device_name,
                    "target": target,
                    "status": status,
                    "apps": apps,
                    "up_to_date": up_to_date,
                    "is_prod": is_prod,
                    "factory": factory or "default",
                }

                if vpn_ip:
                    device_info["vpn_ip"] = vpn_ip

                if created_at:
                    device_info["created_at"] = created_at

                if last_seen:
                    device_info["last_seen"] = last_seen

                if device_group:
                    device_info["device_group"] = device_group

                if tag:
                    device_info["tag"] = tag

                if owner:
                    device_info["owner"] = owner

                if updated_at:
                    device_info["updated_at"] = updated_at

                if ostree_hash:
                    device_info["ostree_hash"] = ostree_hash

                if uuid:
                    device_info["uuid"] = uuid

                devices.append(device_info)

        return {
            "success": True,
            "devices": devices,
            "count": len(devices),
            "factory": factory or "default",
            "message": f"Found {len(devices)} Foundries device(s)",
        }

    except Exception as e:
        logger.error(f"Failed to list Foundries devices: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to list Foundries devices: {e!s}",
            "suggestions": [
                "Check if fioctl is installed: https://github.com/foundriesio/fioctl",
                "Check if fioctl is configured: Run 'fioctl login'",
                "Verify you have access to the factory",
            ],
        }

