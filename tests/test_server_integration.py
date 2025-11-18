"""
Integration tests for MCP server tool handlers

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
from unittest.mock import patch

from lab_testing.server.tool_definitions import get_all_tools
from lab_testing.server.tool_handlers import handle_tool


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

        # list_devices now returns 1 TextContent item: combined summary + table
        assert len(result) == 1
        assert result[0].type == "text"
        # Verify the combined content includes both summary and table
        assert "**0 devices**" in result[0].text
        mock_list.assert_called_once()

    @patch("lab_testing.server.tool_handlers.power_cycle_device")
    def test_power_cycle_device_handler(self, mock_power_cycle):
        """Test power_cycle_device handler"""
        mock_power_cycle.return_value = {
            "success": True,
            "device_id": "test_device_1",
            "message": "Power cycled successfully",
        }

        result = handle_tool(
            "power_cycle_device", {"device_id": "test_device_1", "off_duration": 5}, "test-123", 0.0
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

    @patch("lab_testing.server.tool_handlers.ssh_to_device")
    def test_ssh_to_device_handler(self, mock_ssh):
        """Test ssh_to_device handler"""
        mock_ssh.return_value = {"success": True, "output": "test output"}

        result = handle_tool(
            "ssh_to_device",
            {"device_id": "test_device_1", "command": "uptime"},
            "test-123",
            0.0,
        )

        assert len(result) == 1
        assert result[0].type == "text"
        mock_ssh.assert_called_once_with("test_device_1", "uptime", None)

    @patch("lab_testing.server.tool_handlers.get_vpn_status")
    def test_vpn_status_handler(self, mock_status):
        """Test vpn_status handler"""
        mock_status.return_value = {"connected": True, "interface": "wg0"}

        result = handle_tool("vpn_status", {}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_status.assert_called_once()

    @patch("lab_testing.server.tool_handlers.connect_vpn")
    def test_connect_vpn_handler(self, mock_connect):
        """Test connect_vpn handler"""
        mock_connect.return_value = {"success": True, "message": "Connected"}

        result = handle_tool("connect_vpn", {}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_connect.assert_called_once()

    @patch("lab_testing.server.tool_handlers.disconnect_vpn")
    def test_disconnect_vpn_handler(self, mock_disconnect):
        """Test disconnect_vpn handler"""
        mock_disconnect.return_value = {"success": True, "message": "Disconnected"}

        result = handle_tool("disconnect_vpn", {}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_disconnect.assert_called_once()

    @patch("lab_testing.server.tool_handlers.check_ota_status")
    def test_check_ota_status_handler(self, mock_ota):
        """Test check_ota_status handler"""
        mock_ota.return_value = {"device_id": "test_device_1", "registered": True}

        result = handle_tool("check_ota_status", {"device_id": "test_device_1"}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_ota.assert_called_once_with("test_device_1")

    @patch("lab_testing.server.tool_handlers.check_ota_status")
    def test_check_ota_status_missing_device_id(self, mock_ota):
        """Test check_ota_status handler with missing device_id"""
        result = handle_tool("check_ota_status", {}, "test-123", 0.0)

        assert len(result) == 1
        result_text = json.loads(result[0].text)
        assert "error" in result_text
        assert "device_id" in result_text["error"].lower()
        mock_ota.assert_not_called()

    @patch("lab_testing.server.tool_handlers.trigger_ota_update")
    def test_trigger_ota_update_handler(self, mock_trigger):
        """Test trigger_ota_update handler"""
        mock_trigger.return_value = {"success": True, "message": "Update triggered"}

        result = handle_tool(
            "trigger_ota_update",
            {"device_id": "test_device_1", "target": "production"},
            "test-123",
            0.0,
        )

        assert len(result) == 1
        assert result[0].type == "text"
        mock_trigger.assert_called_once_with("test_device_1", "production")

    @patch("lab_testing.server.tool_handlers.list_containers")
    def test_list_containers_handler(self, mock_list):
        """Test list_containers handler"""
        mock_list.return_value = {"containers": []}

        result = handle_tool("list_containers", {"device_id": "test_device_1"}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_list.assert_called_once_with("test_device_1")

    @patch("lab_testing.server.tool_handlers.deploy_container")
    def test_deploy_container_handler(self, mock_deploy):
        """Test deploy_container handler"""
        mock_deploy.return_value = {"success": True, "message": "Container deployed"}

        result = handle_tool(
            "deploy_container",
            {"device_id": "test_device_1", "container_name": "app", "image": "app:1.0.0"},
            "test-123",
            0.0,
        )

        assert len(result) == 1
        assert result[0].type == "text"
        mock_deploy.assert_called_once_with("test_device_1", "app", "app:1.0.0")

    @patch("lab_testing.server.tool_handlers.deploy_container")
    def test_deploy_container_missing_params(self, mock_deploy):
        """Test deploy_container handler with missing parameters"""
        result = handle_tool("deploy_container", {"device_id": "test_device_1"}, "test-123", 0.0)

        assert len(result) == 1
        result_text = json.loads(result[0].text)
        assert "error" in result_text
        mock_deploy.assert_not_called()

    @patch("lab_testing.server.tool_handlers.get_system_status")
    def test_get_system_status_handler(self, mock_status):
        """Test get_system_status handler"""
        mock_status.return_value = {"device_id": "test_device_1", "uptime": "2 days"}

        result = handle_tool("get_system_status", {"device_id": "test_device_1"}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_status.assert_called_once_with("test_device_1")

    @patch("lab_testing.server.tool_handlers.get_firmware_version")
    def test_get_firmware_version_handler(self, mock_version):
        """Test get_firmware_version handler"""
        mock_version.return_value = {"version": "1.0.0"}

        result = handle_tool(
            "get_firmware_version", {"device_id": "test_device_1"}, "test-123", 0.0
        )

        assert len(result) == 1
        assert result[0].type == "text"
        mock_version.assert_called_once_with("test_device_1")

    @patch("lab_testing.server.tool_handlers.tasmota_control")
    def test_tasmota_control_handler(self, mock_tasmota):
        """Test tasmota_control handler"""
        mock_tasmota.return_value = {"success": True, "action": "on"}

        result = handle_tool(
            "tasmota_control", {"device_id": "tasmota_switch_1", "action": "on"}, "test-123", 0.0
        )

        assert len(result) == 1
        assert result[0].type == "text"
        mock_tasmota.assert_called_once_with("tasmota_switch_1", "on")

    @patch("lab_testing.server.tool_handlers.tasmota_control")
    def test_tasmota_control_missing_params(self, mock_tasmota):
        """Test tasmota_control handler with missing parameters"""
        result = handle_tool("tasmota_control", {"device_id": "tasmota_switch_1"}, "test-123", 0.0)

        assert len(result) == 1
        result_text = json.loads(result[0].text)
        assert "error" in result_text
        mock_tasmota.assert_not_called()

    @patch("lab_testing.server.tool_handlers.list_tasmota_devices")
    def test_list_tasmota_devices_handler(self, mock_list):
        """Test list_tasmota_devices handler"""
        mock_list.return_value = {"devices": []}

        result = handle_tool("list_tasmota_devices", {}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_list.assert_called_once()

    @patch("lab_testing.server.tool_handlers.get_setup_instructions")
    def test_vpn_setup_instructions_handler(self, mock_instructions):
        """Test vpn_setup_instructions handler"""
        mock_instructions.return_value = {"instructions": {}}

        result = handle_tool("vpn_setup_instructions", {}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_instructions.assert_called_once()

    @patch("lab_testing.server.tool_handlers.check_wireguard_installed")
    def test_check_wireguard_installed_handler(self, mock_check):
        """Test check_wireguard_installed handler"""
        mock_check.return_value = {"installed": True}

        result = handle_tool("check_wireguard_installed", {}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_check.assert_called_once()

    @patch("lab_testing.server.tool_handlers.get_help_content")
    def test_help_handler_all(self, mock_help):
        """Test help handler with all topics"""
        mock_help.return_value = {"tools": {}, "resources": {}}

        result = handle_tool("help", {"topic": "all"}, "test-123", 0.0)

        assert len(result) == 1
        assert result[0].type == "text"
        mock_help.assert_called_once()

    @patch("lab_testing.server.tool_handlers.get_help_content")
    def test_help_handler_specific_topic(self, mock_help):
        """Test help handler with specific topic"""
        mock_help.return_value = {"tools": {}, "resources": {}}

        result = handle_tool("help", {"topic": "tools"}, "test-123", 0.0)

        assert len(result) == 1
        result_text = json.loads(result[0].text)
        assert result_text["success"] is True
        assert "tools" in result_text["content"]

    @patch("lab_testing.server.tool_handlers.get_help_content")
    def test_help_handler_unknown_topic(self, mock_help):
        """Test help handler with unknown topic"""
        mock_help.return_value = {"tools": {}, "resources": {}}

        result = handle_tool("help", {"topic": "unknown"}, "test-123", 0.0)

        assert len(result) == 1
        result_text = json.loads(result[0].text)
        assert result_text["success"] is False
        assert "error" in result_text

    def test_tool_handler_exception(self):
        """Test tool handler exception handling"""
        with patch(
            "lab_testing.server.tool_handlers.list_devices", side_effect=Exception("Test error")
        ):
            result = handle_tool("list_devices", {}, "test-123", 0.0)

            assert len(result) == 1
            assert result[0].type == "text"
            # Error is returned as JSON in TextContent
            import json

            error_data = json.loads(result[0].text)
            assert "error" in error_data
            assert "Test error" in error_data["error"]
