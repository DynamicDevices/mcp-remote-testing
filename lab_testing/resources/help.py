"""
Help and Documentation Resource Provider

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

from typing import Any, Dict


def get_help_content() -> Dict[str, Any]:
    """Get comprehensive help documentation"""
    return {
        "overview": "MCP server for remote embedded hardware testing in lab environment",
        "version": "0.4.0",
        "usage": {
            "basic": "Ask AI assistant to use tools (e.g., 'List devices in the lab', 'Connect to VPN')",
            "examples": [
                "List all devices: 'What devices are available?'",
                "Test connectivity: 'Can you test if the iMX93 board is reachable?'",
                "SSH command: 'Run uptime on the Sentai board'",
                "VPN control: 'Connect to the lab VPN'",
                "Power control: 'Turn on the E-ink board power'",
                "Start monitoring: 'Start monitoring power consumption'",
            ],
        },
        "tools": {
            "device_management": {
                "list_devices": "List all devices with status, IPs, types, firmware, SSH status, last seen, and power switches. Returns brief summary (always visible) then full table. Supports filtering by device_type_filter, status_filter, ssh_status_filter, power_state_filter, search_query. Supports sorting (sort_by: ip/friendly_name/status/last_seen, sort_order: asc/desc) and limiting results (limit). Includes summary statistics (counts by type/status/SSH status). Shows Tasmota power state/consumption and test equipment detection. Power Switch column: For Tasmota devices, shows their own power state (🟢 ON/🔴 OFF); for other devices, shows which power switch controls them (if configured). Use force_refresh=true to bypass cache and rescan all devices.",
                "test_device": "Test connectivity to a device (ping and SSH check). Best practice: Use before running operations on devices. In DHCP environments, use verify_device_identity to ensure correct device.",
                "ssh_to_device": "Execute SSH command on a device (requires device_id, command, optional username). Best practice: Test device connectivity first with test_device.",
                "verify_device_identity": "Verify device identity at given IP matches expected device (important for DHCP). Updates IP in config if verified and changed.",
                "verify_device_by_ip": "Identify which device (if any) is at a given IP address by checking hostname/unique ID.",
                "update_device_ip": "Verify device identity and update IP address in config if device is verified and IP has changed (for DHCP environments).",
                "update_device_friendly_name": "Update friendly name for a discovered device in the cache. Allows custom names when referencing devices.",
            },
            "vpn_management": {
                "vpn_status": "Get current WireGuard VPN connection status",
                "connect_vpn": "Connect to WireGuard VPN for lab network access",
                "disconnect_vpn": "Disconnect from VPN",
            },
            "power_monitoring": {
                "start_power_monitoring": "Start power monitoring session - supports DMM (SCPI) or Tasmota (energy monitoring). Optional: device_id, test_name, duration, monitor_type (dmm|tasmota)",
                "get_power_logs": "Get recent power monitoring logs (optional: test_name, limit)",
            },
            "tasmota_control": {
                "tasmota_control": "Control Tasmota power switch (device_id, action: on|off|toggle|status|energy)",
                "list_tasmota_devices": "List all configured Tasmota devices and the devices they control",
                "power_cycle_device": "Power cycle a device by controlling its Tasmota power switch (turns off, waits, then turns on). Optional: off_duration (default: 5 seconds).",
            },
            "test_equipment": {
                "list_test_equipment": "List all test equipment devices (DMM, oscilloscopes, etc.) found on the network. Includes both configured devices and auto-discovered devices.",
                "query_test_equipment": "Send a SCPI command to test equipment (DMM, etc.) and get the response. Common commands: *IDN? (identify), MEAS:VOLT:DC? (measure DC voltage), MEAS:CURR:DC? (measure DC current). Supports device_id from config or IP address.",
            },
            "ota_management": {
                "check_ota_status": "Check Foundries.io OTA update status (device_id)",
                "trigger_ota_update": "Trigger OTA update (device_id, target?)",
                "list_containers": "List Docker containers on device (device_id)",
                "deploy_container": "Deploy/update container (device_id, container_name, image)",
                "get_system_status": "Get system status: uptime, load, memory, disk, kernel (device_id)",
                "get_firmware_version": "Get firmware/OS version from /etc/os-release (device_id)",
                "get_foundries_registration_status": "Check Foundries.io registration, connection, update status (device_id)",
                "get_secure_boot_status": "Get detailed secure boot status: U-Boot, kernel, EFI, HAB/CAAM (device_id)",
                "get_device_identity": "Get device identity: hostname, SOC unique ID, Foundries registration name (device_id)",
            },
            "batch_operations": {
                "batch_operation": "Execute operation on multiple devices in parallel (device_ids[], operation, max_concurrent=5, ...)",
                "regression_test": "Run regression test sequence in parallel (device_group?|device_ids[], test_sequence?, max_concurrent=5)",
                "get_device_groups": "Get devices organized by groups/tags for rack management",
            },
            "power_analysis": {
                "analyze_power_logs": "Analyze power logs for low power/suspend detection (test_name?, device_id?, threshold_mw?)",
                "monitor_low_power": "Monitor device for low power consumption (device_id, duration?, threshold_mw?, sample_rate?)",
                "compare_power_profiles": "Compare power consumption across multiple test runs (test_names[], device_id?). Visualizes differences between test sessions.",
            },
        },
        "resources": {
            "device://inventory": "Complete device inventory JSON with all configured devices",
            "network://status": "Current network and VPN connection status",
            "config://lab_devices": "Raw lab devices configuration file",
            "help://usage": "This help documentation",
            "health://status": "Server health, metrics, SSH pool status, and uptime",
        },
        "configuration": {
            "lab_testing_root": "Path to lab testing framework (default: /data_drive/esl/ai-lab-testing)",
            "device_config": "Device inventory: {lab_testing_root}/config/lab_devices.json",
            "vpn_config": "VPN config: {lab_testing_root}/secrets/wg0.conf",
            "environment": "Override with LAB_TESTING_ROOT environment variable",
        },
        "common_workflows": {
            "check_lab_status": [
                "1. Use 'vpn_status' to check VPN connection",
                "2. Use 'list_devices' to see available devices (shows brief summary first, then full table)",
                "3. Filter devices: 'list_devices(device_type_filter=\"tasmota_device\")' or 'list_devices(status_filter=\"online\")'",
                "4. Filter by SSH status: 'list_devices(ssh_status_filter=\"error\")' to find devices with SSH issues",
                "5. Filter Tasmota by power: 'list_devices(power_state_filter=\"on\")' to find powered-on Tasmota devices",
                "6. Search devices: 'list_devices(search_query=\"192.168.2.18\")'",
                '7. Sort results: \'list_devices(sort_by="ip", sort_order="asc")\' or \'list_devices(sort_by="last_seen", sort_order="desc")\'',
                "8. Limit results: 'list_devices(limit=10)' to show only first 10 devices",
                "9. Force refresh: 'list_devices(force_refresh=true)' to bypass cache and rescan",
                "10. Use 'test_device' to verify connectivity",
            ],
            "device_discovery": [
                "1. Devices are automatically discovered via network scanning",
                "2. Tasmota devices detected via HTTP API (port 80)",
                "3. Test equipment (DMM) detected via SCPI ports (5025, 5024, 3490, 3491)",
                "4. Device information cached to speed up subsequent scans",
                "5. Use 'list_devices' to see all discovered devices with their status",
                "6. Update friendly names: 'update_device_friendly_name(ip, friendly_name)'",
            ],
            "remote_device_access": [
                "1. Ensure VPN connected (use 'connect_vpn' if needed)",
                "2. Use 'ssh_to_device' with device_id and command",
                "3. Example: ssh_to_device('imx93_eink_board_2', 'uptime')",
            ],
            "ota_update_workflow": [
                "1. Check current status: 'check_ota_status(device_id)'",
                "2. Trigger update: 'trigger_ota_update(device_id, target?)'",
                "3. Monitor: 'get_system_status(device_id)' to verify",
                "4. Check containers: 'list_containers(device_id)'",
            ],
            "container_deployment": [
                "1. List current containers: 'list_containers(device_id)'",
                "2. Deploy new container: 'deploy_container(device_id, name, image)'",
                "3. Verify: 'list_containers(device_id)' again",
            ],
            "low_power_analysis": [
                "1. Start monitoring: 'monitor_low_power(device_id, duration, threshold_mw)'",
                "2. Wait for monitoring to complete",
                "3. Analyze: 'analyze_power_logs(test_name, device_id, threshold_mw)'",
                "4. Compare profiles: 'compare_power_profiles([test1, test2])'",
            ],
            "regression_testing": [
                "1. Get device groups: 'get_device_groups()' to see available groups",
                "2. Run regression: 'regression_test(device_group, test_sequence?)'",
                "3. Or test specific devices: 'regression_test(device_ids=[...])'",
                "4. Review results for all devices",
            ],
            "rack_management": [
                "1. Group devices by tag/type in device config",
                "2. Use 'get_device_groups()' to see organization",
                "3. Use 'batch_operation(device_ids, operation)' for parallel ops",
                "4. Use 'regression_test(device_group)' for automated testing",
            ],
        },
        "troubleshooting": {
            "vpn_not_connecting": "Check VPN config exists, may require NetworkManager or sudo",
            "device_not_found": "Verify device_id in device inventory (use list_devices). In DHCP environments, use verify_device_identity to ensure correct device.",
            "ssh_fails": "Check SSH keys configured, device online, VPN connected. SSH authentication prioritizes 'fio' user, then 'root'. Check SSH status in device list.",
            "tools_fail": "Verify lab_testing_root path correct, underlying scripts work",
            "device_list_not_visible": "Device list returns brief summary first (always visible), then full table. If not visible, restart MCP server connection.",
            "cache_errors": "Device cache uses atomic writes and thread-safe locking. If errors occur, cache may be corrupted - clear cache directory and rescan.",
        },
        "best_practices": [
            "Always check VPN status before accessing lab devices",
            "Use test_device before executing SSH commands",
            "Use descriptive test_name for power monitoring sessions",
            "Check device inventory resource for available device_ids",
            "For OTA updates: check status first, then trigger, monitor system_status",
            "For containers: list first, deploy with specific image tags, verify after",
            "For low power: set appropriate threshold_mw, monitor for sufficient duration",
            "For regression: organize devices by tags/groups, use batch operations",
            "Tag devices in config for easy rack management and grouping",
            "Use list_devices filters to quickly find specific devices (type, status, SSH status, power state, search)",
            "Use list_devices sorting (sort_by, sort_order) to organize results by IP, name, status, or last seen",
            "Use list_devices limit parameter to cap results for large networks",
            "Use list_devices force_refresh=true to bypass cache when you need fresh data",
            "Device list shows brief summary first - always visible without expanding",
            "In DHCP environments: verify device identity before operations, use update_device_ip if IP changed",
            "Device discovery is optimized with parallel SSH identification and caching",
            "Tasmota devices show power state (🟢 ON/🔴 OFF) in the Power Switch column and consumption (Watts) in the Type column of the device list",
            "Test equipment (DMM) can be queried with SCPI commands via query_test_equipment",
        ],
        "foundries_io_integration": {
            "device_config": "Add 'fio_factory', 'fio_target', 'fio_current' to device config",
            "ota_updates": "Uses aktualizr/aktualizr-torizon for OTA management",
            "containers": "Docker-based container deployment and management",
            "tags": "Add 'tags' array to devices for grouping (e.g., ['rack1', 'regression'])",
        },
    }
