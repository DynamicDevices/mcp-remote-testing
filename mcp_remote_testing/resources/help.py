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
        "version": "0.1.0",
        "usage": {
            "basic": "Ask AI assistant to use tools (e.g., 'List devices in the lab', 'Connect to VPN')",
            "examples": [
                "List all devices: 'What devices are available?'",
                "Test connectivity: 'Can you test if the iMX93 board is reachable?'",
                "SSH command: 'Run uptime on the Sentai board'",
                "VPN control: 'Connect to the lab VPN'",
                "Power control: 'Turn on the E-ink board power'",
                "Start monitoring: 'Start monitoring power consumption'"
            ]
        },
        "tools": {
            "device_management": {
                "list_devices": "List all configured lab devices with status, IPs, and types",
                "test_device": "Test connectivity to a device (ping and SSH check)",
                "ssh_to_device": "Execute SSH command on a device (requires device_id, command, optional username)"
            },
            "vpn_management": {
                "vpn_status": "Get current WireGuard VPN connection status",
                "connect_vpn": "Connect to WireGuard VPN for lab network access",
                "disconnect_vpn": "Disconnect from VPN"
            },
            "power_monitoring": {
                "start_power_monitoring": "Start power monitoring session (optional: device_id, test_name, duration)",
                "get_power_logs": "Get recent power monitoring logs (optional: test_name, limit)"
            },
            "tasmota_control": {
            "tasmota_control": "Control Tasmota power switch (device_id, action: on|off|toggle|status|energy)",
            "list_tasmota_devices": "List all configured Tasmota devices"
        },
        "ota_management": {
            "check_ota_status": "Check Foundries.io OTA update status (device_id)",
            "trigger_ota_update": "Trigger OTA update (device_id, target?)",
            "list_containers": "List Docker containers on device (device_id)",
            "deploy_container": "Deploy/update container (device_id, container_name, image)",
            "get_system_status": "Get system status: uptime, load, memory, disk, kernel (device_id)"
        },
        "batch_operations": {
            "batch_operation": "Execute operation on multiple devices (device_ids[], operation, ...)",
            "regression_test": "Run regression test sequence (device_group?|device_ids[], test_sequence?)",
            "get_device_groups": "Get devices organized by groups/tags for rack management"
        },
        "power_analysis": {
            "analyze_power_logs": "Analyze power logs for low power/suspend detection (test_name?, device_id?, threshold_mw?)",
            "monitor_low_power": "Monitor device for low power consumption (device_id, duration?, threshold_mw?, sample_rate?)",
            "compare_power_profiles": "Compare power consumption across test runs (test_names[], device_id?)"
        }
    },
        "resources": {
            "device://inventory": "Complete device inventory JSON with all configured devices",
            "network://status": "Current network and VPN connection status",
            "config://lab_devices": "Raw lab devices configuration file",
            "help://usage": "This help documentation"
        },
        "configuration": {
            "lab_testing_root": "Path to lab testing framework (default: /data_drive/esl/lab-testing)",
            "device_config": "Device inventory: {lab_testing_root}/config/lab_devices.json",
            "vpn_config": "VPN config: {lab_testing_root}/secrets/wg0.conf",
            "environment": "Override with LAB_TESTING_ROOT environment variable"
        },
        "common_workflows": {
            "check_lab_status": [
                "1. Use 'vpn_status' to check VPN connection",
                "2. Use 'list_devices' to see available devices",
                "3. Use 'test_device' to verify connectivity"
            ],
            "remote_device_access": [
                "1. Ensure VPN connected (use 'connect_vpn' if needed)",
                "2. Use 'ssh_to_device' with device_id and command",
                "3. Example: ssh_to_device('imx93_eink_board_2', 'uptime')"
            ],
            "ota_update_workflow": [
                "1. Check current status: 'check_ota_status(device_id)'",
                "2. Trigger update: 'trigger_ota_update(device_id, target?)'",
                "3. Monitor: 'get_system_status(device_id)' to verify",
                "4. Check containers: 'list_containers(device_id)'"
            ],
            "container_deployment": [
                "1. List current containers: 'list_containers(device_id)'",
                "2. Deploy new container: 'deploy_container(device_id, name, image)'",
                "3. Verify: 'list_containers(device_id)' again"
            ],
            "low_power_analysis": [
                "1. Start monitoring: 'monitor_low_power(device_id, duration, threshold_mw)'",
                "2. Wait for monitoring to complete",
                "3. Analyze: 'analyze_power_logs(test_name, device_id, threshold_mw)'",
                "4. Compare profiles: 'compare_power_profiles([test1, test2])'"
            ],
            "regression_testing": [
                "1. Get device groups: 'get_device_groups()' to see available groups",
                "2. Run regression: 'regression_test(device_group, test_sequence?)'",
                "3. Or test specific devices: 'regression_test(device_ids=[...])'",
                "4. Review results for all devices"
            ],
            "rack_management": [
                "1. Group devices by tag/type in device config",
                "2. Use 'get_device_groups()' to see organization",
                "3. Use 'batch_operation(device_ids, operation)' for parallel ops",
                "4. Use 'regression_test(device_group)' for automated testing"
            ]
        },
        "troubleshooting": {
            "vpn_not_connecting": "Check VPN config exists, may require NetworkManager or sudo",
            "device_not_found": "Verify device_id in device inventory (use list_devices)",
            "ssh_fails": "Check SSH keys configured, device online, VPN connected",
            "tools_fail": "Verify lab_testing_root path correct, underlying scripts work"
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
            "Tag devices in config for easy rack management and grouping"
        ],
        "foundries_io_integration": {
            "device_config": "Add 'fio_factory', 'fio_target', 'fio_current' to device config",
            "ota_updates": "Uses aktualizr/aktualizr-torizon for OTA management",
            "containers": "Docker-based container deployment and management",
            "tags": "Add 'tags' array to devices for grouping (e.g., ['rack1', 'regression'])"
        }
    }

