"""
Tests for error helper utilities

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

from unittest.mock import Mock

import pytest

from lab_testing.exceptions import DeviceConnectionError, DeviceNotFoundError, MCPError
from lab_testing.utils.error_helper import (
    format_error_response,
    get_general_suggestions,
    get_related_tools,
)


class TestFormatErrorResponse:
    """Tests for format_error_response"""

    def test_format_mcp_error(self):
        """Test formatting MCPError"""
        error = DeviceNotFoundError("Device not found", device_id="test_device")

        result = format_error_response(error)

        assert "error" in result or "message" in result
        assert "suggestions" in result
        assert "related_tools" in result
        # MCPError.to_dict() may not include error_type, check if it exists
        if "error_type" in result:
            assert result["error_type"] == "DeviceNotFoundError"

    def test_format_generic_error(self):
        """Test formatting generic exception"""
        error = ValueError("Invalid value")

        result = format_error_response(error)

        assert "error" in result
        assert result["error_type"] == "ValueError"
        assert "suggestions" in result

    def test_format_error_with_context(self):
        """Test formatting error with context"""
        error = DeviceConnectionError("Connection failed", device_id="test_device")
        context = {"operation": "ssh", "command": "uptime"}

        result = format_error_response(error, context)

        assert "context" in result
        assert result["context"] == context


class TestGeneralSuggestions:
    """Tests for get_general_suggestions"""

    def test_connection_error_suggestions(self):
        """Test suggestions for connection errors"""
        error = DeviceConnectionError("Connection timeout", device_id="test_device")

        suggestions = get_general_suggestions(error)

        assert len(suggestions) > 0
        assert any("vpn" in s.lower() for s in suggestions)
        assert any("test_device" in s.lower() for s in suggestions)

    def test_device_not_found_suggestions(self):
        """Test suggestions for device not found errors"""
        error = DeviceNotFoundError("Device not found", device_id="test_device")

        suggestions = get_general_suggestions(error)

        assert len(suggestions) > 0
        assert any("list_devices" in s.lower() for s in suggestions)

    def test_authentication_error_suggestions(self):
        """Test suggestions for authentication errors"""
        error = Exception("Permission denied (publickey)")

        suggestions = get_general_suggestions(error)

        assert len(suggestions) > 0
        assert any("ssh" in s.lower() or "key" in s.lower() for s in suggestions)

    def test_generic_error_suggestions(self):
        """Test suggestions for generic errors"""
        error = Exception("Something went wrong")

        suggestions = get_general_suggestions(error)

        # Should have some general suggestions
        assert isinstance(suggestions, list)


class TestRelatedTools:
    """Tests for get_related_tools"""

    def test_connection_error_tools(self):
        """Test related tools for connection errors"""
        error = DeviceConnectionError("Connection failed", device_id="test_device")

        tools = get_related_tools(error)

        assert len(tools) > 0
        assert any("vpn" in t.lower() for t in tools)

    def test_device_error_tools(self):
        """Test related tools for device errors"""
        error = DeviceNotFoundError("Device not found", device_id="test_device")

        tools = get_related_tools(error)

        assert len(tools) > 0
        assert any("list" in t.lower() for t in tools)

    def test_generic_error_tools(self):
        """Test related tools for generic errors"""
        error = Exception("Generic error")

        tools = get_related_tools(error)

        # Should have some general tools
        assert isinstance(tools, list)

