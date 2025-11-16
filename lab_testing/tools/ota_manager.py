"""
OTA Update Management Tools for Foundries.io
"""

import json
from typing import Any, Dict, Optional

from lab_testing.config import get_lab_devices_config
from lab_testing.tools.device_manager import ssh_to_device


def get_device_fio_info(device_id: str) -> Dict[str, Any]:
    """Get Foundries.io information for a device"""
    try:
        with open(get_lab_devices_config()) as f:
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
        return {"error": f"Failed to get device info: {e!s}"}


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
        from lab_testing.tools.device_manager import ssh_to_device
        result = ssh_to_device(device_id, "aktualizr-info 2>/dev/null || echo 'aktualizr not available'")

        if result.get("success"):
            return {
                "device_id": device_id,
                "status": "checked",
                "output": result.get("stdout", ""),
                "current_target": device_info.get("fio_current"),
                "target": device_info.get("fio_target")
            }
        return {
            "device_id": device_id,
            "status": "error",
            "error": result.get("stderr", "Unknown error")
        }
    except Exception as e:
        return {"error": f"Failed to check OTA status: {e!s}"}


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
        return {"error": f"Failed to trigger OTA update: {e!s}"}


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
            for line in result.get("stdout", "").strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
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
        return {
            "device_id": device_id,
            "error": result.get("stderr", "Failed to list containers")
        }
    except Exception as e:
        return {"error": f"Failed to list containers: {e!s}"}


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
        return {"error": f"Failed to deploy container: {e!s}"}


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
        return {"error": f"Failed to get system status: {e!s}"}


def get_firmware_version(device_id: str) -> Dict[str, Any]:
    """
    Get firmware/OS version information from /etc/os-release.
    
    Returns:
        Dictionary with parsed os-release fields
    """
    try:
        from lab_testing.exceptions import DeviceNotFoundError, OTAError
        from lab_testing.tools.device_manager import ssh_to_device
        from lab_testing.utils.logger import get_logger

        logger = get_logger()

        result = ssh_to_device(device_id, "cat /etc/os-release")
        if not result.get("success"):
            raise DeviceNotFoundError(f"Failed to read /etc/os-release: {result.get('error', 'Unknown error')}")

        os_release = {}
        for line in result.get("stdout", "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes from value
                value = value.strip('"\'')
                os_release[key] = value

        return {
            "success": True,
            "device_id": device_id,
            "os_release": os_release,
            "name": os_release.get("NAME", "Unknown"),
            "version": os_release.get("VERSION", "Unknown"),
            "version_id": os_release.get("VERSION_ID", "Unknown"),
            "build_id": os_release.get("BUILD_ID", "Unknown"),
            "pretty_name": os_release.get("PRETTY_NAME", "Unknown"),
            "foundries": {
                "factory": os_release.get("FACTORY", "Unknown"),
                "target": os_release.get("LMP_FACTORY", "Unknown"),
                "machine": os_release.get("MACHINE", "Unknown")
            }
        }
    except Exception as e:
        logger.error(f"Failed to get firmware version for {device_id}: {e}")
        raise OTAError(f"Firmware version check failed: {e!s}")


def get_foundries_registration_status(device_id: str) -> Dict[str, Any]:
    """
    Check Foundries.io registration and connection status.
    
    Checks:
    - /var/sota directory and files
    - fioctl device status
    - aktualizr status
    
    Returns:
        Dictionary with registration status
    """
    try:
        from lab_testing.exceptions import OTAError
        from lab_testing.tools.device_manager import ssh_to_device
        from lab_testing.utils.logger import get_logger

        logger = get_logger()

        status = {
            "success": True,
            "device_id": device_id,
            "registered": False,
            "connected": False,
            "up_to_date": False,
            "details": {}
        }

        # Check /var/sota directory
        sota_check = ssh_to_device(device_id, "test -d /var/sota && ls -la /var/sota/ || echo 'NOT_FOUND'")
        if sota_check.get("success"):
            sota_output = sota_check.get("stdout", "")
            if "NOT_FOUND" not in sota_output:
                status["details"]["sota_directory"] = "exists"
                # Check for key files
                key_files = ["device_name", "device_id", "sota.toml"]
                for key_file in key_files:
                    file_check = ssh_to_device(device_id, f"test -f /var/sota/{key_file} && cat /var/sota/{key_file} || echo 'NOT_FOUND'")
                    if file_check.get("success") and "NOT_FOUND" not in file_check.get("stdout", ""):
                        content = file_check.get("stdout", "").strip()
                        status["details"][key_file] = content
                        if key_file == "device_name":
                            status["registered"] = True
            else:
                status["details"]["sota_directory"] = "not_found"

        # Check aktualizr status
        aktualizr_check = ssh_to_device(device_id, "systemctl is-active aktualizr 2>/dev/null || echo 'INACTIVE'")
        if aktualizr_check.get("success"):
            aktualizr_status = aktualizr_check.get("stdout", "").strip()
            status["details"]["aktualizr_service"] = aktualizr_status
            status["connected"] = aktualizr_status == "active"

        # Try to get device info from aktualizr
        device_info = ssh_to_device(device_id, "aktualizr-info 2>/dev/null || echo 'NOT_AVAILABLE'")
        if device_info.get("success"):
            info_output = device_info.get("stdout", "")
            if "NOT_AVAILABLE" not in info_output:
                status["details"]["aktualizr_info"] = info_output

        # Check if fioctl is available and try to get device status
        fioctl_check = ssh_to_device(device_id, "which fioctl >/dev/null 2>&1 && echo 'AVAILABLE' || echo 'NOT_AVAILABLE'")
        if fioctl_check.get("success") and "AVAILABLE" in fioctl_check.get("stdout", ""):
            # Note: fioctl typically needs to run from a machine with API keys, not on device
            # But we can check if device has fioctl config
            fioctl_config = ssh_to_device(device_id, "test -f ~/.config/fioctl/config.yaml && echo 'CONFIGURED' || echo 'NOT_CONFIGURED'")
            if fioctl_config.get("success"):
                status["details"]["fioctl_configured"] = "CONFIGURED" in fioctl_config.get("stdout", "")

        # Check for pending updates
        update_check = ssh_to_device(device_id, "test -f /var/sota/sota.toml && grep -q 'pending' /var/sota/*.json 2>/dev/null && echo 'PENDING' || echo 'NONE'")
        if update_check.get("success"):
            has_pending = "PENDING" in update_check.get("stdout", "")
            status["up_to_date"] = not has_pending
            status["details"]["pending_updates"] = has_pending

        return status

    except Exception as e:
        logger.error(f"Failed to get Foundries registration status for {device_id}: {e}")
        raise OTAError(f"Registration status check failed: {e!s}")


def get_secure_boot_status(device_id: str) -> Dict[str, Any]:
    """
    Get detailed secure boot status information.
    
    Checks:
    - U-Boot secure boot status
    - Kernel secure boot status (via /proc/config.gz or kernel cmdline)
    - EFI secure boot status (if available)
    - HAB/CAAM status (for i.MX devices)
    
    Returns:
        Dictionary with secure boot status details
    """
    try:
        from lab_testing.exceptions import OTAError
        from lab_testing.tools.device_manager import ssh_to_device
        from lab_testing.utils.logger import get_logger

        logger = get_logger()

        status = {
            "success": True,
            "device_id": device_id,
            "secure_boot_enabled": False,
            "details": {}
        }

        # Check U-Boot secure boot status
        uboot_check = ssh_to_device(device_id, "fw_printenv secure_boot 2>/dev/null || echo 'NOT_FOUND'")
        if uboot_check.get("success"):
            uboot_output = uboot_check.get("stdout", "").strip()
            if "NOT_FOUND" not in uboot_output:
                status["details"]["uboot_secure_boot"] = uboot_output
                if "secure_boot=yes" in uboot_output.lower() or "secure_boot=1" in uboot_output:
                    status["secure_boot_enabled"] = True

        # Check kernel command line for secure boot indicators
        kernel_cmdline = ssh_to_device(device_id, "cat /proc/cmdline 2>/dev/null || echo 'NOT_FOUND'")
        if kernel_cmdline.get("success"):
            cmdline = kernel_cmdline.get("stdout", "").strip()
            if "NOT_FOUND" not in cmdline:
                status["details"]["kernel_cmdline"] = cmdline
                # Check for secure boot indicators
                secure_indicators = ["lockdown", "ima", "apparmor", "selinux"]
                found_indicators = [ind for ind in secure_indicators if ind in cmdline.lower()]
                if found_indicators:
                    status["details"]["security_indicators"] = found_indicators
                    status["secure_boot_enabled"] = True

        # Check EFI secure boot (if EFI is available)
        efi_check = ssh_to_device(device_id, "test -d /sys/firmware/efi && cat /sys/firmware/efi/efivars/SecureBoot-* 2>/dev/null | od -An -tu1 | head -1 || echo 'NOT_EFI'")
        if efi_check.get("success"):
            efi_output = efi_check.get("stdout", "").strip()
            if "NOT_EFI" not in efi_output and efi_output:
                try:
                    # EFI SecureBoot variable: 1 = enabled, 0 = disabled
                    secure_boot_value = int(efi_output.strip())
                    status["details"]["efi_secure_boot"] = secure_boot_value == 1
                    if secure_boot_value == 1:
                        status["secure_boot_enabled"] = True
                except ValueError:
                    pass

        # Check HAB status (High Assurance Boot for i.MX devices)
        hab_check = ssh_to_device(device_id, "dmesg | grep -i 'hab' | tail -5 || echo 'NO_HAB'")
        if hab_check.get("success"):
            hab_output = hab_check.get("stdout", "").strip()
            if "NO_HAB" not in hab_output and hab_output:
                status["details"]["hab_status"] = hab_output
                if "enabled" in hab_output.lower() or "closed" in hab_output.lower():
                    status["secure_boot_enabled"] = True

        # Check CAAM (Cryptographic Accelerator and Assurance Module) status
        caam_check = ssh_to_device(device_id, "dmesg | grep -i 'caam' | head -3 || echo 'NO_CAAM'")
        if caam_check.get("success"):
            caam_output = caam_check.get("stdout", "").strip()
            if "NO_CAAM" not in caam_output and caam_output:
                status["details"]["caam_status"] = caam_output

        # Check if kernel is locked down
        lockdown_check = ssh_to_device(device_id, "cat /sys/kernel/security/lockdown 2>/dev/null || echo 'NOT_AVAILABLE'")
        if lockdown_check.get("success"):
            lockdown_output = lockdown_check.get("stdout", "").strip()
            if "NOT_AVAILABLE" not in lockdown_output:
                status["details"]["kernel_lockdown"] = lockdown_output
                if "none" not in lockdown_output.lower():
                    status["secure_boot_enabled"] = True

        # Check IMA (Integrity Measurement Architecture) status
        ima_check = ssh_to_device(device_id, "cat /sys/kernel/security/ima/policy 2>/dev/null | head -1 || echo 'NO_IMA'")
        if ima_check.get("success"):
            ima_output = ima_check.get("stdout", "").strip()
            if "NO_IMA" not in ima_output and ima_output:
                status["details"]["ima_enabled"] = True

        return status

    except Exception as e:
        logger.error(f"Failed to get secure boot status for {device_id}: {e}")
        raise OTAError(f"Secure boot status check failed: {e!s}")


def get_device_identity(device_id: str) -> Dict[str, Any]:
    """
    Get device identity information including hostname and SOC unique ID.
    
    The hostname is typically created from a unique SOC ID that's used
    for registration with Foundries.io portal.
    
    Returns:
        Dictionary with hostname, SOC ID, and registration information
    """
    try:
        from lab_testing.exceptions import OTAError
        from lab_testing.tools.device_manager import ssh_to_device
        from lab_testing.utils.logger import get_logger

        logger = get_logger()

        identity = {
            "success": True,
            "device_id": device_id,
            "hostname": None,
            "soc_unique_id": None,
            "foundries_device_name": None,
            "details": {}
        }

        # Get hostname
        hostname_check = ssh_to_device(device_id, "hostname")
        if hostname_check.get("success"):
            identity["hostname"] = hostname_check.get("stdout", "").strip()

        # Get full hostname (FQDN)
        fqdn_check = ssh_to_device(device_id, "hostname -f 2>/dev/null || hostname")
        if fqdn_check.get("success"):
            identity["details"]["fqdn"] = fqdn_check.get("stdout", "").strip()

        # Try to get SOC unique ID from various sources
        # i.MX devices: /sys/devices/soc0/serial_number or /proc/device-tree/serial-number
        # Generic: /etc/machine-id or systemd machine-id

        # Check for i.MX serial number
        imx_serial = ssh_to_device(device_id, "cat /sys/devices/soc0/serial_number 2>/dev/null || echo 'NOT_FOUND'")
        if imx_serial.get("success"):
            serial = imx_serial.get("stdout", "").strip()
            if "NOT_FOUND" not in serial and serial:
                identity["soc_unique_id"] = serial
                identity["details"]["soc_id_source"] = "/sys/devices/soc0/serial_number"

        # Check device tree serial number
        if not identity["soc_unique_id"]:
            dt_serial = ssh_to_device(device_id, "cat /proc/device-tree/serial-number 2>/dev/null | tr -d '\\0' || echo 'NOT_FOUND'")
            if dt_serial.get("success"):
                serial = dt_serial.get("stdout", "").strip()
                if "NOT_FOUND" not in serial and serial:
                    identity["soc_unique_id"] = serial
                    identity["details"]["soc_id_source"] = "/proc/device-tree/serial-number"

        # Check machine-id (systemd)
        if not identity["soc_unique_id"]:
            machine_id = ssh_to_device(device_id, "cat /etc/machine-id 2>/dev/null || cat /var/lib/dbus/machine-id 2>/dev/null || echo 'NOT_FOUND'")
            if machine_id.get("success"):
                mid = machine_id.get("stdout", "").strip()
                if "NOT_FOUND" not in mid and mid:
                    identity["soc_unique_id"] = mid
                    identity["details"]["soc_id_source"] = "machine-id"

        # Check for Foundries device name in /var/sota
        sota_device_name = ssh_to_device(device_id, "cat /var/sota/device_name 2>/dev/null || echo 'NOT_FOUND'")
        if sota_device_name.get("success"):
            device_name = sota_device_name.get("stdout", "").strip()
            if "NOT_FOUND" not in device_name and device_name:
                identity["foundries_device_name"] = device_name
                identity["details"]["foundries_registration_name"] = device_name

        # Check aktualizr device ID
        aktualizr_id = ssh_to_device(device_id, "aktualizr-info 2>/dev/null | grep -i 'deviceid\\|device id' | head -1 || echo 'NOT_FOUND'")
        if aktualizr_id.get("success"):
            aid = aktualizr_id.get("stdout", "").strip()
            if "NOT_FOUND" not in aid and aid:
                identity["details"]["aktualizr_device_id"] = aid

        # Check if hostname matches SOC ID pattern
        if identity["hostname"] and identity["soc_unique_id"]:
            # Hostname might be derived from SOC ID (last few characters)
            soc_short = identity["soc_unique_id"][-8:] if len(identity["soc_unique_id"]) > 8 else identity["soc_unique_id"]
            if soc_short.lower() in identity["hostname"].lower():
                identity["details"]["hostname_derived_from_soc"] = True
            else:
                identity["details"]["hostname_derived_from_soc"] = False

        # Get additional system identifiers
        product_uuid = ssh_to_device(device_id, "cat /sys/class/dmi/id/product_uuid 2>/dev/null || echo 'NOT_FOUND'")
        if product_uuid.get("success"):
            puuid = product_uuid.get("stdout", "").strip()
            if "NOT_FOUND" not in puuid and puuid:
                identity["details"]["product_uuid"] = puuid

        return identity

    except Exception as e:
        logger.error(f"Failed to get device identity for {device_id}: {e}")
        raise OTAError(f"Device identity check failed: {e!s}")

