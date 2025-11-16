"""
Error Helper Utilities

Provides actionable error messages, suggestions, and fixes to help LLMs
guide users through problems and ensure best practices.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

from typing import Any, Dict, List, Optional

from lab_testing.exceptions import MCPError


def format_error_response(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format an error into a comprehensive response with suggestions and fixes.
    
    Args:
        error: The exception that occurred
        context: Additional context about the operation
    
    Returns:
        Dictionary with error details, suggestions, fixes, and related tools
    """
    if isinstance(error, MCPError):
        response = error.to_dict()
    else:
        response = {
            "error": str(error),
            "error_type": type(error).__name__,
            "details": {}
        }
    
    # Add context if provided
    if context:
        response["context"] = context
    
    # Add general troubleshooting if no specific suggestions
    if "suggestions" not in response or not response["suggestions"]:
        response["suggestions"] = get_general_suggestions(error, context)
    
    # Add related tools if not specified
    if "related_tools" not in response or not response["related_tools"]:
        response["related_tools"] = get_related_tools(error, context)
    
    return response


def get_general_suggestions(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Get general troubleshooting suggestions based on error type"""
    suggestions = []
    
    error_type = type(error).__name__
    error_msg = str(error).lower()
    
    # Network/connection errors
    if "connection" in error_msg or "network" in error_msg or "timeout" in error_msg:
        suggestions.extend([
            "Check VPN connection status using 'vpn_status' tool",
            "Verify device is online using 'test_device' tool",
            "Check network connectivity: 'ping' command or 'test_device'",
            "Ensure VPN is connected: 'connect_vpn' if needed"
        ])
    
    # Device not found errors
    if "not found" in error_msg or "device" in error_msg:
        suggestions.extend([
            "List available devices using 'list_devices' tool",
            "Verify device_id spelling (case-sensitive)",
            "Check if device has a friendly_name you can use instead",
            "Use 'list_devices' to see all configured devices with their IDs and friendly names"
        ])
    
    # Authentication errors
    if "auth" in error_msg or "permission" in error_msg or "denied" in error_msg:
        suggestions.extend([
            "Check SSH key configuration in device config",
            "Verify SSH credentials are cached (system handles this automatically)",
            "Check if passwordless sudo is enabled on target device",
            "Review device configuration for SSH user and port settings"
        ])
    
    # Configuration errors
    if "config" in error_msg or "missing" in error_msg:
        suggestions.extend([
            "Check device configuration file exists and is valid JSON",
            "Verify required fields are present in device config",
            "Use 'list_devices' to see current configuration",
            "Check VPN config exists: 'vpn_setup_instructions' for setup help"
        ])
    
    # OTA/Container errors
    if "ota" in error_msg or "container" in error_msg or "foundries" in error_msg:
        suggestions.extend([
            "Check device registration status: 'get_foundries_registration_status'",
            "Verify device is connected to Foundries.io: 'check_ota_status'",
            "Check system status: 'get_system_status'",
            "Review device identity: 'get_device_identity'"
        ])
    
    return suggestions if suggestions else [
        "Check the help documentation: 'help' tool with topic 'troubleshooting'",
        "Verify device configuration and network connectivity",
        "Check server logs for detailed error information"
    ]


def get_related_tools(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Get list of related tools that might help resolve the issue"""
    tools = []
    
    error_msg = str(error).lower()
    
    # Always include basic diagnostic tools
    tools.extend(["list_devices", "vpn_status", "help"])
    
    # Add context-specific tools
    if context:
        tool_name = context.get("tool_name", "")
        
        if "device" in tool_name or "device" in error_msg:
            tools.extend(["test_device", "get_device_info", "verify_device_identity"])
        
        if "vpn" in tool_name or "vpn" in error_msg:
            tools.extend(["connect_vpn", "vpn_statistics", "vpn_setup_instructions"])
        
        if "ota" in tool_name or "container" in tool_name:
            tools.extend(["check_ota_status", "get_system_status", "get_device_identity"])
    
    return list(set(tools))  # Remove duplicates


def validate_device_identifier(
    identifier: str,
    available_devices: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate a device identifier and provide helpful suggestions if invalid.
    
    Args:
        identifier: Device identifier to validate
        available_devices: Dictionary of available devices (optional)
    
    Returns:
        Validation result with suggestions
    """
    result = {
        "valid": False,
        "identifier": identifier,
        "suggestions": [],
        "alternatives": []
    }
    
    if not identifier:
        result["suggestions"] = [
            "Device identifier is required",
            "Use 'list_devices' to see available devices",
            "You can use either device_id or friendly_name"
        ]
        return result
    
    if not available_devices:
        result["valid"] = True  # Can't validate without device list
        return result
    
    # Check exact match
    if identifier in available_devices:
        result["valid"] = True
        return result
    
    # Check friendly names
    alternatives = []
    identifier_lower = identifier.lower()
    
    for device_id, device_info in available_devices.items():
        friendly_name = device_info.get("friendly_name") or device_info.get("name", "")
        if friendly_name and identifier_lower in friendly_name.lower():
            alternatives.append({
                "device_id": device_id,
                "friendly_name": friendly_name,
                "match_type": "friendly_name_contains"
            })
        elif identifier_lower in device_id.lower():
            alternatives.append({
                "device_id": device_id,
                "friendly_name": friendly_name,
                "match_type": "device_id_contains"
            })
    
    if alternatives:
        result["alternatives"] = alternatives
        result["suggestions"] = [
            f"Device '{identifier}' not found exactly, but found {len(alternatives)} similar device(s)",
            "Did you mean one of these?",
            "Use 'list_devices' to see all available devices"
        ]
    else:
        result["suggestions"] = [
            f"Device '{identifier}' not found",
            "Use 'list_devices' to see all configured devices",
            "Device identifiers are case-sensitive",
            "You can use either the device_id (unique ID) or friendly_name"
        ]
    
    return result


def get_best_practices(tool_name: str) -> List[str]:
    """
    Get best practice recommendations for a specific tool.
    
    Args:
        tool_name: Name of the tool
    
    Returns:
        List of best practice recommendations
    """
    practices = {
        "ssh_to_device": [
            "Always verify device connectivity first with 'test_device'",
            "Use friendly_name for better readability in scripts",
            "Check device identity if IP might have changed (DHCP): 'verify_device_identity'",
            "Review change history: 'get_change_history' to see what was executed"
        ],
        "test_device": [
            "Test devices before running critical operations",
            "Use 'verify_device_identity' in DHCP environments to ensure correct device",
            "Check VPN connection first if devices are unreachable"
        ],
        "connect_vpn": [
            "Check VPN status first: 'vpn_status'",
            "Use NetworkManager method when available (no root required)",
            "Verify VPN config exists: 'list_vpn_configs' or 'vpn_setup_instructions'"
        ],
        "batch_operation": [
            "Start with small batches to test operations",
            "Use appropriate max_concurrent based on network capacity",
            "Monitor results for individual device failures",
            "Consider using 'regression_test' for standard test sequences"
        ],
        "deploy_container": [
            "List existing containers first: 'list_containers'",
            "Verify device is online and accessible",
            "Check system resources: 'get_system_status'",
            "Monitor deployment: 'get_system_status' after deployment"
        ],
        "trigger_ota_update": [
            "Check current OTA status first: 'check_ota_status'",
            "Verify device registration: 'get_foundries_registration_status'",
            "Monitor update progress: 'get_system_status'",
            "Check firmware version after update: 'get_firmware_version'"
        ],
        "create_network_map": [
            "Start with configured devices only (scan_networks=false) for faster results",
            "Use smaller network ranges or limit max_hosts_per_network for large networks",
            "Verify device identities for discovered hosts: 'verify_device_by_ip'"
        ],
        "verify_device_identity": [
            "Always verify device identity in DHCP environments before operations",
            "Use this after network scans to identify unknown hosts",
            "Update device IP if verified and changed: 'update_device_ip'"
        ]
    }
    
    return practices.get(tool_name, [
        "Check device connectivity before operations",
        "Verify VPN connection for remote devices",
        "Review help documentation: 'help' tool"
    ])


def format_tool_response(
    result: Dict[str, Any],
    tool_name: str,
    include_best_practices: bool = True
) -> Dict[str, Any]:
    """
    Format a tool response with helpful context and best practices.
    
    Args:
        result: Tool execution result
        tool_name: Name of the tool executed
        include_best_practices: Whether to include best practice recommendations
    
    Returns:
        Enhanced response with context
    """
    enhanced = result.copy()
    
    # Add best practices if successful
    if result.get("success") and include_best_practices:
        enhanced["best_practices"] = get_best_practices(tool_name)
    
    # Add helpful context for common operations
    if tool_name == "list_devices" and "devices_by_type" in result:
        enhanced["usage_tip"] = (
            "You can use either device_id or friendly_name when referencing devices. "
            "Friendly names are easier to remember and use in conversations."
        )
    
    if tool_name == "test_device" and not result.get("success"):
        enhanced["next_steps"] = [
            "Check VPN connection: 'vpn_status'",
            "Verify device IP hasn't changed: 'verify_device_identity'",
            "Check network connectivity: 'create_network_map'"
        ]
    
    return enhanced

