"""
Tests for power analysis tools

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import csv
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from lab_testing.tools.power_analysis import (
    analyze_power_logs,
    compare_power_profiles,
    monitor_low_power,
)


class TestAnalyzePowerLogs:
    """Tests for analyze_power_logs"""

    @patch("lab_testing.tools.power_analysis.get_logs_dir")
    def test_analyze_power_logs_no_directory(self, mock_logs_dir, tmp_path):
        """Test analyzing power logs when directory doesn't exist"""
        mock_logs_dir.return_value = tmp_path / "nonexistent"

        result = analyze_power_logs()

        assert "error" in result
        assert "not found" in result["error"].lower()

    @patch("lab_testing.tools.power_analysis.get_logs_dir")
    def test_analyze_power_logs_no_files(self, mock_logs_dir, tmp_path):
        """Test analyzing power logs when no log files exist"""
        logs_dir = tmp_path / "power_logs"
        logs_dir.mkdir(parents=True)
        mock_logs_dir.return_value = tmp_path

        result = analyze_power_logs()

        assert "error" in result
        assert "no matching" in result["error"].lower()

    @patch("lab_testing.tools.power_analysis.get_logs_dir")
    def test_analyze_power_logs_success(self, mock_logs_dir, tmp_path):
        """Test analyzing power logs successfully"""
        logs_dir = tmp_path / "power_logs"
        logs_dir.mkdir(parents=True)
        mock_logs_dir.return_value = tmp_path

        # Create a test log file
        log_file = logs_dir / "test_device_20250101_120000.csv"
        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "power_w"])
            writer.writeheader()
            writer.writerow({"timestamp": "2025-01-01 12:00:00", "power_w": "0.1"})
            writer.writerow({"timestamp": "2025-01-01 12:00:01", "power_w": "0.15"})
            writer.writerow({"timestamp": "2025-01-01 12:00:02", "power_w": "0.12"})

        result = analyze_power_logs()

        assert "analyses" in result
        assert len(result["analyses"]) > 0
        analysis = result["analyses"][0]
        assert "min_power_mw" in analysis
        assert "max_power_mw" in analysis
        assert "avg_power_mw" in analysis

    @patch("lab_testing.tools.power_analysis.get_logs_dir")
    def test_analyze_power_logs_with_threshold(self, mock_logs_dir, tmp_path):
        """Test analyzing power logs with low power threshold"""
        logs_dir = tmp_path / "power_logs"
        logs_dir.mkdir(parents=True)
        mock_logs_dir.return_value = tmp_path

        log_file = logs_dir / "test_device_20250101_120000.csv"
        with open(log_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "power_w"])
            writer.writeheader()
            writer.writerow({"timestamp": "2025-01-01 12:00:00", "power_w": "0.05"})  # 50mW
            writer.writerow({"timestamp": "2025-01-01 12:00:01", "power_w": "0.15"})  # 150mW

        result = analyze_power_logs(threshold_mw=100.0)

        assert "analyses" in result
        analysis = result["analyses"][0]
        assert "low_power" in analysis
        assert analysis["low_power"]["threshold_mw"] == 100.0
        assert analysis["low_power"]["samples_below"] == 1

    @patch("lab_testing.tools.power_analysis.get_logs_dir")
    def test_analyze_power_logs_filter_by_test_name(self, mock_logs_dir, tmp_path):
        """Test analyzing power logs filtered by test name"""
        logs_dir = tmp_path / "power_logs"
        logs_dir.mkdir(parents=True)
        mock_logs_dir.return_value = tmp_path

        # Create two log files
        log1 = logs_dir / "test1_device_20250101.csv"
        log2 = logs_dir / "test2_device_20250101.csv"
        log1.write_text("timestamp,power_w\n2025-01-01,0.1\n")
        log2.write_text("timestamp,power_w\n2025-01-01,0.2\n")

        result = analyze_power_logs(test_name="test1")

        assert "analyses" in result
        assert len(result["analyses"]) == 1
        assert "test1" in result["analyses"][0]["log_file"]


class TestComparePowerProfiles:
    """Tests for compare_power_profiles"""

    @patch("lab_testing.tools.power_analysis.get_logs_dir")
    def test_compare_power_profiles_success(self, mock_logs_dir, tmp_path):
        """Test comparing power profiles successfully"""
        logs_dir = tmp_path / "power_logs"
        logs_dir.mkdir(parents=True)
        mock_logs_dir.return_value = tmp_path

        # Create test log files with matching test names
        log1 = logs_dir / "test1_device_20250101_120000.csv"
        log2 = logs_dir / "test2_device_20250101_120000.csv"
        with open(log1, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "power_w"])
            writer.writeheader()
            writer.writerow({"timestamp": "2025-01-01", "power_w": "0.1"})
        with open(log2, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "power_w"])
            writer.writeheader()
            writer.writerow({"timestamp": "2025-01-01", "power_w": "0.2"})

        result = compare_power_profiles(["test1", "test2"])

        assert "comparisons" in result
        assert len(result["comparisons"]) == 2


class TestMonitorLowPower:
    """Tests for monitor_low_power"""

    @patch("lab_testing.tools.power_monitor.start_power_monitoring")
    def test_monitor_low_power_success(self, mock_start):
        """Test monitoring low power successfully"""
        mock_start.return_value = {
            "success": True,
            "session_id": "test_session",
            "process_id": 12345,
        }

        result = monitor_low_power("test_device", duration=10, threshold_mw=100.0)

        assert result["success"] is True
        assert "monitoring_started" in result
        assert result["monitoring_started"] is True

    @patch("lab_testing.tools.power_monitor.start_power_monitoring")
    def test_monitor_low_power_failure(self, mock_start):
        """Test monitoring low power with failure"""
        mock_start.return_value = {"success": False, "error": "Monitoring failed"}

        result = monitor_low_power("test_device", duration=10)

        assert result["success"] is False or "error" in result

