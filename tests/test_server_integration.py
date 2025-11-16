"""
Integration tests for MCP server tool handlers

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from lab_testing.server.tool_handlers import handle_tool
from lab_testing.server.tool_definitions import get_all_tools


class TestToolDefinitions:
    """Tests for tool definitions"""

    def test_all_tools_defined(self):
        """Test that all tools have definitions"""
        tools = get_all_tools()
        tool_names = {tool.name for tool in tools}
        
        # Check for key tools
        assert "list_devices" in tool_names
        assert "test_device" in tool_names
        assert "power_cycle_device" in tool_names
        assert "create_network_map" in tool_names
        assert "list_tasmota_devices" in tool_names

    def test_tool_schemas_valid(self):
        """Test that tool schemas are valid"""
        tools = get_all_tools()
        
        for tool in tools:
            assert tool.name
            assert tool.description
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"


class TestToolHandlers:
    """Tests for tool handlers"""

    @patch("lab_testing.server.tool_handlers.list_devices")
    def test_list_devices_handler(self, mock_list):
        """Test list_devices handler"""
        mock_list.return_value = {"total_devices": 0, "devices_by_type": {}}
        
        result = handle_tool("list_devices", {}, "test-123", 0.0)
        
        assert len(result) == 1
        assert result[0].type == "text"
        mock_list.assert_called_once()

    @patch("lab_testing.server.tool_handlers.power_cycle_device")
    def test_power_cycle_device_handler(self, mock_power_cycle):
        """Test power_cycle_device handler"""
        mock_power_cycle.return_value = {
            "success": True,
            "device_id": "test_device_1",
            "message": "Power cycled successfully"
        }
        
        result = handle_tool(
            "power_cycle_device",
            {"device_id": "test_device_1", "off_duration": 5},
            "test-123",
            0.0
        )
        
        assert len(result) == 1
        assert result[0].type == "text"
        mock_power_cycle.assert_called_once_with("test_device_1", 5)

    def test_unknown_tool(self):
        """Test handling of unknown tool"""
        result = handle_tool("unknown_tool", {}, "test-123", 0.0)
        
        assert len(result) == 1
        assert result[0].type == "text"
        result_text = json.loads(result[0].text)
        assert "error" in result_text
        assert "Unknown tool" in result_text["error"]

    def test_missing_required_parameter(self):
        """Test handling of missing required parameters"""
        result = handle_tool("test_device", {}, "test-123", 0.0)
        
        assert len(result) == 1
        result_text = json.loads(result[0].text)
        assert "error" in result_text or "suggestions" in result_text

