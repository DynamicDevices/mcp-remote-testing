"""
Custom Exceptions for MCP Remote Testing

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

from typing import Optional


class MCPError(Exception):
    """Base exception for all MCP errors"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict] = None,
        suggestions: Optional[list] = None,
        fixes: Optional[list] = None,
        related_tools: Optional[list] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestions = suggestions or []
        self.fixes = fixes or []
        self.related_tools = related_tools or []

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON serialization with helpful context"""
        result = {
            "error": self.message,
            "error_code": self.error_code,
            "details": self.details
        }
        
        if self.suggestions:
            result["suggestions"] = self.suggestions
        if self.fixes:
            result["fixes"] = self.fixes
        if self.related_tools:
            result["related_tools"] = self.related_tools
        
        return result


class ConfigurationError(MCPError):
    """Configuration-related errors"""


class DeviceError(MCPError):
    """Device-related errors"""

    def __init__(self, message: str, device_id: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.device_id = device_id
        if device_id:
            self.details["device_id"] = device_id


class DeviceNotFoundError(DeviceError):
    """Device not found in configuration"""
    
    def __init__(self, message: str, device_id: Optional[str] = None, **kwargs):
        suggestions = [
            f"Device '{device_id}' not found in configuration",
            "Use 'list_devices' tool to see all available devices",
            "Device identifiers are case-sensitive",
            "You can use either device_id (unique ID) or friendly_name"
        ]
        fixes = [
            "Check spelling of device_id",
            "List devices: 'list_devices' to see available options",
            "Try using the friendly_name if configured"
        ]
        related_tools = ["list_devices", "get_device_info"]
        super().__init__(
            message,
            device_id=device_id,
            suggestions=suggestions,
            fixes=fixes,
            related_tools=related_tools,
            **kwargs
        )


class DeviceConnectionError(DeviceError):
    """Failed to connect to device"""
    
    def __init__(self, message: str, device_id: Optional[str] = None, **kwargs):
        suggestions = [
            "Check VPN connection status: 'vpn_status'",
            "Verify device is online: 'test_device'",
            "Device IP may have changed (DHCP): 'verify_device_identity'",
            "Check network connectivity"
        ]
        fixes = [
            "Connect to VPN: 'connect_vpn' if not connected",
            "Verify device identity: 'verify_device_identity'",
            "Update device IP if changed: 'update_device_ip'",
            "Check device power and network cables"
        ]
        related_tools = ["vpn_status", "test_device", "verify_device_identity", "connect_vpn"]
        super().__init__(
            message,
            device_id=device_id,
            suggestions=suggestions,
            fixes=fixes,
            related_tools=related_tools,
            **kwargs
        )


class DeviceTimeoutError(DeviceError):
    """Device operation timed out"""


class NetworkError(MCPError):
    """Network-related errors"""


class VPNError(NetworkError):
    """VPN connection errors"""


class SSHError(MCPError):
    """SSH-related errors"""

    def __init__(self, message: str, device_id: Optional[str] = None, command: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.device_id = device_id
        self.command = command
        if device_id:
            self.details["device_id"] = device_id
        if command:
            self.details["command"] = command
        
        # Add helpful suggestions
        suggestions = [
            "Verify device connectivity: 'test_device'",
            "Check SSH credentials and key configuration",
            "Verify device is online and accessible"
        ]
        fixes = [
            "Test device connectivity first: 'test_device'",
            "Check SSH user and port in device configuration",
            "Verify VPN connection if device is remote"
        ]
        related_tools = ["test_device", "vpn_status", "get_device_info"]
        
        self.suggestions = suggestions
        self.fixes = fixes
        self.related_tools = related_tools


class AuthenticationError(SSHError):
    """SSH authentication errors"""


class PowerMonitoringError(MCPError):
    """Power monitoring errors"""


class OTAError(MCPError):
    """OTA update errors"""

    def __init__(self, message: str, device_id: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.device_id = device_id
        if device_id:
            self.details["device_id"] = device_id


class ContainerError(MCPError):
    """Container deployment errors"""

    def __init__(self, message: str, device_id: Optional[str] = None, container_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.device_id = device_id
        self.container_name = container_name
        if device_id:
            self.details["device_id"] = device_id
        if container_name:
            self.details["container_name"] = container_name

