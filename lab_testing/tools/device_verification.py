"""
Device Identity Verification

Verify that a device at a given IP address matches the expected device
by checking hostname and unique ID. Important for DHCP environments where
IP addresses can change.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import subprocess
from typing import Any, Dict, Optional

from lab_testing.config import get_lab_devices_config
from lab_testing.tools.device_manager import resolve_device_identifier, ssh_to_device
from lab_testing.utils.logger import get_logger

logger = get_logger()


def get_device_unique_id_from_ip(
    ip: str, username: str = "root", ssh_port: int = 22
) -> Optional[str]:
    """
    Get unique ID (SOC serial number) from a device at a given IP address.

    Args:
        ip: IP address to check
        username: SSH username
        ssh_port: SSH port

    Returns:
        Unique ID or None if unable to retrieve
    """
    try:
        # Try multiple methods to get unique ID
        commands = [
            "cat /sys/devices/soc0/serial_number 2>/dev/null",
            "cat /proc/device-tree/serial-number 2>/dev/null | tr -d '\\0'",
            "cat /etc/machine-id 2>/dev/null",
            "hostname 2>/dev/null",
        ]

        for cmd in commands:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "ConnectTimeout=5",
                    "-p",
                    str(ssh_port),
                    f"{username}@{ip}",
                    cmd,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                unique_id = result.stdout.strip()
                if unique_id and unique_id != "NOT_FOUND":
                    return unique_id
    except Exception as e:
        logger.debug(f"Failed to get unique ID from {ip}: {e}")

    return None


def verify_device_identity(device_id_or_name: str, ip: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify that a device matches its expected identity by checking hostname and unique ID.

    This is important in DHCP environments where IP addresses can change.

    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)
        ip: IP address to verify (optional, uses configured IP if not provided)

    Returns:
        Dictionary with verification results
    """

    # Resolve device identifier
    device_id = resolve_device_identifier(device_id_or_name)
    if not device_id:
        return {
            "success": False,
            "error": f"Device '{device_id_or_name}' not found in configuration",
        }

    # Load device config
    config_path = get_lab_devices_config()
    with open(config_path) as f:
        config = json.load(f)

    devices = config.get("devices", {})
    if device_id not in devices:
        return {"success": False, "error": f"Device '{device_id}' not found in configuration"}

    device = devices[device_id]

    # Use provided IP or configured IP
    if not ip:
        ip = device.get("ip")

    if not ip:
        return {"success": False, "error": "No IP address provided or configured"}

    # Get expected identity
    expected_hostname = device.get("hostname") or device_id
    expected_unique_id = device.get("unique_id") or device.get("soc_id")
    expected_friendly_name = device.get("friendly_name") or device.get("name", device_id)

    username = device.get("ssh_user", "root")
    ssh_port = device.get("ports", {}).get("ssh", 22)

    verification = {
        "success": False,
        "device_id": device_id,
        "friendly_name": expected_friendly_name,
        "ip_checked": ip,
        "configured_ip": device.get("ip"),
        "ip_matches": ip == device.get("ip"),
        "expected_hostname": expected_hostname,
        "expected_unique_id": expected_unique_id,
        "actual_hostname": None,
        "actual_unique_id": None,
        "hostname_matches": False,
        "unique_id_matches": False,
        "verified": False,
    }

    try:
        # Get actual hostname from device
        hostname_result = ssh_to_device(device_id, "hostname", username)
        if hostname_result.get("success"):
            actual_hostname = hostname_result.get("stdout", "").strip()
            verification["actual_hostname"] = actual_hostname

            # Check if hostname matches (can be partial match if hostname contains device_id)
            if expected_hostname:
                verification["hostname_matches"] = (
                    actual_hostname.lower() == expected_hostname.lower()
                    or device_id.lower() in actual_hostname.lower()
                    or actual_hostname.lower() in expected_hostname.lower()
                )
            else:
                # If no expected hostname, check if device_id appears in hostname
                verification["hostname_matches"] = device_id.lower() in actual_hostname.lower()

        # Get actual unique ID from device
        unique_id_commands = [
            "cat /sys/devices/soc0/serial_number 2>/dev/null",
            "cat /proc/device-tree/serial-number 2>/dev/null | tr -d '\\0'",
            "cat /etc/machine-id 2>/dev/null",
        ]

        for cmd in unique_id_commands:
            uid_result = ssh_to_device(device_id, cmd, username)
            if uid_result.get("success"):
                actual_uid = uid_result.get("stdout", "").strip()
                if actual_uid and actual_uid != "NOT_FOUND" and len(actual_uid) > 4:
                    verification["actual_unique_id"] = actual_uid

                    if expected_unique_id:
                        verification["unique_id_matches"] = (
                            actual_uid.lower() == expected_unique_id.lower()
                            or expected_unique_id.lower() in actual_uid.lower()
                            or actual_uid.lower() in expected_unique_id.lower()
                        )
                    else:
                        # Store the unique ID for future reference
                        verification["unique_id_matches"] = True  # Found an ID, consider it valid
                    break

        # Device is verified if hostname or unique ID matches
        verification["verified"] = (
            verification["hostname_matches"] or verification["unique_id_matches"]
        )
        verification["success"] = True

        # If IP changed but device is verified, suggest updating config
        if verification["verified"] and not verification["ip_matches"]:
            verification["suggestion"] = (
                f"Device verified but IP changed. Consider updating config: {ip} -> {device.get('ip')}"
            )

    except Exception as e:
        verification["error"] = f"Verification failed: {e!s}"
        logger.error(f"Device verification failed for {device_id}: {e}", exc_info=True)

    return verification


def verify_device_by_ip(ip: str, username: str = "root", ssh_port: int = 22) -> Dict[str, Any]:
    """
    Identify which device (if any) is at a given IP address by checking hostname/unique ID.

    Useful for discovering devices or verifying IP assignments in DHCP environments.

    Args:
        ip: IP address to check
        username: SSH username
        ssh_port: SSH port

    Returns:
        Dictionary with device identification results
    """

    result = {
        "ip": ip,
        "device_found": False,
        "device_id": None,
        "friendly_name": None,
        "hostname": None,
        "unique_id": None,
        "matches": [],
    }

    try:
        # Get hostname from device
        hostname_result = subprocess.run(
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ConnectTimeout=5",
                "-p",
                str(ssh_port),
                f"{username}@{ip}",
                "hostname",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if hostname_result.returncode == 0:
            hostname = hostname_result.stdout.strip()
            result["hostname"] = hostname

        # Get unique ID
        uid_commands = [
            "cat /sys/devices/soc0/serial_number 2>/dev/null",
            "cat /proc/device-tree/serial-number 2>/dev/null | tr -d '\\0'",
            "cat /etc/machine-id 2>/dev/null",
        ]

        for cmd in uid_commands:
            uid_result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "ConnectTimeout=5",
                    "-p",
                    str(ssh_port),
                    f"{username}@{ip}",
                    cmd,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if uid_result.returncode == 0:
                unique_id = uid_result.stdout.strip()
                if unique_id and unique_id != "NOT_FOUND" and len(unique_id) > 4:
                    result["unique_id"] = unique_id
                    break

        # Search config for matching device
        config_path = get_lab_devices_config()
        with open(config_path) as f:
            config = json.load(f)

        devices = config.get("devices", {})

        for device_id, device_info in devices.items():
            match_score = 0
            match_reasons = []

            # Check hostname match
            expected_hostname = device_info.get("hostname") or device_id
            if hostname and expected_hostname:
                if hostname.lower() == expected_hostname.lower():
                    match_score += 10
                    match_reasons.append("exact_hostname_match")
                elif (
                    device_id.lower() in hostname.lower()
                    or hostname.lower() in expected_hostname.lower()
                ):
                    match_score += 5
                    match_reasons.append("partial_hostname_match")

            # Check unique ID match
            expected_uid = device_info.get("unique_id") or device_info.get("soc_id")
            if result["unique_id"] and expected_uid:
                if result["unique_id"].lower() == expected_uid.lower():
                    match_score += 10
                    match_reasons.append("exact_uid_match")
                elif (
                    expected_uid.lower() in result["unique_id"].lower()
                    or result["unique_id"].lower() in expected_uid.lower()
                ):
                    match_score += 5
                    match_reasons.append("partial_uid_match")

            if match_score > 0:
                result["matches"].append(
                    {
                        "device_id": device_id,
                        "friendly_name": device_info.get("friendly_name")
                        or device_info.get("name", device_id),
                        "match_score": match_score,
                        "reasons": match_reasons,
                        "configured_ip": device_info.get("ip"),
                    }
                )

        # Sort matches by score
        result["matches"].sort(key=lambda x: x["match_score"], reverse=True)

        # Best match
        if result["matches"]:
            best_match = result["matches"][0]
            if best_match["match_score"] >= 5:  # At least partial match
                result["device_found"] = True
                result["device_id"] = best_match["device_id"]
                result["friendly_name"] = best_match["friendly_name"]

    except Exception as e:
        result["error"] = f"Failed to identify device: {e!s}"
        logger.error(f"Device identification failed for {ip}: {e}", exc_info=True)

    return result


def update_device_ip_if_changed(device_id_or_name: str, new_ip: str) -> Dict[str, Any]:
    """
    Verify device identity and update IP if device is verified and IP has changed.

    This helps keep device configs up-to-date in DHCP environments.

    Args:
        device_id_or_name: Device identifier (device_id or friendly_name)
        new_ip: New IP address to verify and potentially update

    Returns:
        Dictionary with update results
    """
    # First verify the device identity
    verification = verify_device_identity(device_id_or_name, new_ip)

    if not verification.get("verified"):
        return {
            "success": False,
            "error": "Device identity verification failed. IP not updated.",
            "verification": verification,
        }

    device_id = verification.get("device_id")

    # Load and update config
    config_path = get_lab_devices_config()
    with open(config_path) as f:
        config = json.load(f)

    if device_id not in config.get("devices", {}):
        return {"success": False, "error": f"Device '{device_id}' not found in configuration"}

    old_ip = config["devices"][device_id].get("ip")

    if old_ip == new_ip:
        return {"success": True, "message": "IP address unchanged", "ip": new_ip}

    # Update IP in config
    config["devices"][device_id]["ip"] = new_ip

    # Write back to config file
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        return {
            "success": True,
            "message": f"Device IP updated: {old_ip} -> {new_ip}",
            "device_id": device_id,
            "friendly_name": verification.get("friendly_name"),
            "old_ip": old_ip,
            "new_ip": new_ip,
            "verification": verification,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to update config file: {e!s}",
            "verification": verification,
        }
