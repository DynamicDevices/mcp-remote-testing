"""
Tests for async batch operations

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from lab_testing.tools.batch_operations_async import (
    batch_operation_async,
    get_device_groups,
    regression_test_async,
)


class TestGetDeviceGroups:
    """Tests for get_device_groups"""

    @patch("lab_testing.tools.batch_operations_async.get_lab_devices_config")
    @patch("builtins.open")
    def test_get_device_groups_by_type(self, mock_open, mock_config, sample_device_config):
        """Test getting device groups by device type"""
        mock_config.return_value = sample_device_config
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            {
                "devices": {
                    "device1": {"device_type": "board", "tags": ["rack1"]},
                    "device2": {"device_type": "board", "tags": ["rack1", "regression"]},
                    "device3": {"device_type": "laptop", "tags": ["rack2"]},
                }
            }
        )

        result = get_device_groups()

        assert "error" not in result
        assert "board" in result
        assert "laptop" in result
        assert len(result["board"]) == 2
        assert len(result["laptop"]) == 1

    @patch("lab_testing.tools.batch_operations_async.get_lab_devices_config")
    @patch("builtins.open")
    def test_get_device_groups_by_tags(self, mock_open, mock_config, sample_device_config):
        """Test getting device groups by tags"""
        mock_config.return_value = sample_device_config
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            {
                "devices": {
                    "device1": {"device_type": "board", "tags": ["rack1", "regression"]},
                    "device2": {"device_type": "board", "tags": ["rack1"]},
                    "device3": {"device_type": "laptop", "tags": ["rack2", "regression"]},
                }
            }
        )

        result = get_device_groups()

        assert "error" not in result
        assert "rack1" in result
        assert "rack2" in result
        assert "regression" in result
        assert len(result["regression"]) == 2

    @patch("lab_testing.tools.batch_operations_async.get_lab_devices_config")
    @patch("builtins.open")
    def test_get_device_groups_error(self, mock_open, mock_config):
        """Test error handling in get_device_groups"""
        mock_config.return_value = Mock()
        mock_open.side_effect = IOError("File not found")

        result = get_device_groups()

        assert "error" in result


class TestBatchOperationAsync:
    """Tests for batch_operation_async"""

    @pytest.mark.asyncio
    @patch("lab_testing.tools.device_manager.test_device")
    async def test_batch_operation_async_success(self, mock_test):
        """Test successful async batch operation"""
        mock_test.return_value = {"success": True, "device_id": "device1"}

        result = await batch_operation_async(
            device_ids=["device1", "device2"], operation="test", max_concurrent=2
        )

        assert "results" in result
        assert len(result["results"]) == 2
        assert result["total_devices"] == 2

    @pytest.mark.asyncio
    @patch("lab_testing.tools.device_manager.ssh_to_device")
    async def test_batch_operation_async_with_kwargs(self, mock_ssh):
        """Test async batch operation with kwargs"""
        mock_ssh.return_value = {"success": True, "output": "test"}

        result = await batch_operation_async(
            device_ids=["device1"],
            operation="ssh",
            command="uptime",
            max_concurrent=1,
        )

        assert "results" in result
        mock_ssh.assert_called()

    @pytest.mark.asyncio
    async def test_batch_operation_async_empty_list(self):
        """Test async batch operation with empty device list"""
        result = await batch_operation_async(device_ids=[], operation="test")

        assert "error" in result

    @pytest.mark.asyncio
    @patch("lab_testing.tools.device_manager.test_device")
    async def test_batch_operation_async_concurrency_limit(self, mock_test):
        """Test that concurrency limit is respected"""
        mock_test.return_value = {"success": True}

        result = await batch_operation_async(
            device_ids=["device1", "device2", "device3", "device4", "device5"],
            operation="test",
            max_concurrent=2,
        )

        assert "results" in result
        assert len(result["results"]) == 5
        assert result["max_concurrent"] == 2


class TestRegressionTestAsync:
    """Tests for regression_test_async"""

    @pytest.mark.asyncio
    @patch("lab_testing.tools.device_manager.test_device")
    @patch("lab_testing.tools.ota_manager.get_system_status")
    async def test_regression_test_async_success(self, mock_status, mock_test):
        """Test successful regression test"""
        mock_test.return_value = {"success": True}
        mock_status.return_value = {"success": True}

        result = await regression_test_async(
            device_ids=["device1", "device2"],
            test_sequence=["test", "system_status"],
            max_concurrent=2,
        )

        assert "results" in result
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    @patch("lab_testing.tools.device_manager.test_device")
    @patch("lab_testing.tools.ota_manager.get_system_status")
    @patch("lab_testing.tools.ota_manager.check_ota_status")
    async def test_regression_test_async_default_sequence(self, mock_ota, mock_status, mock_test):
        """Test regression test with default sequence"""
        mock_test.return_value = {"success": True}
        mock_status.return_value = {"success": True}
        mock_ota.return_value = {"success": True}

        result = await regression_test_async(device_ids=["device1"], max_concurrent=1)

        assert "results" in result
        assert "test_sequence" in result

    @pytest.mark.asyncio
    @patch("lab_testing.tools.batch_operations_async.get_device_groups")
    @patch("lab_testing.tools.batch_operations_async.batch_operation_async")
    async def test_regression_test_async_by_group(self, mock_batch, mock_groups):
        """Test regression test by device group"""
        mock_groups.return_value = {"rack1": ["device1", "device2"]}
        mock_batch.return_value = {"results": {}, "successful": 2, "total_devices": 2}

        result = await regression_test_async(device_group="rack1", max_concurrent=2)

        assert "results" in result
        mock_groups.assert_called_once()

    @pytest.mark.asyncio
    @patch("lab_testing.tools.batch_operations_async.get_device_groups")
    async def test_regression_test_async_empty_group(self, mock_groups):
        """Test regression test with empty device group"""
        mock_groups.return_value = {"rack1": []}

        result = await regression_test_async(device_group="rack1", max_concurrent=1)

        assert "error" in result
