"""
Enhanced Power Analysis Tools for Low Power Monitoring
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp_remote_testing.config import get_lab_devices_config, get_logs_dir


def analyze_power_logs(
    test_name: Optional[str] = None,
    device_id: Optional[str] = None,
    threshold_mw: Optional[float] = None
) -> Dict[str, Any]:
    """
    Analyze power logs for low power characteristics.
    
    Args:
        test_name: Filter by test name
        device_id: Filter by device
        threshold_mw: Power threshold in mW for low power detection
        
    Returns:
        Power analysis results
    """
    logs_dir = get_logs_dir() / "power_logs"
    
    if not logs_dir.exists():
        return {"error": f"Logs directory not found: {logs_dir}"}
    
    # Find relevant log files
    log_files = []
    for log_file in sorted(logs_dir.glob("*.csv"), reverse=True):
        if test_name and test_name not in log_file.name:
            continue
        if device_id and device_id not in log_file.name:
            continue
        log_files.append(log_file)
        if len(log_files) >= 5:  # Analyze last 5 matching logs
            break
    
    if not log_files:
        return {"error": "No matching log files found"}
    
    analyses = []
    for log_file in log_files:
        try:
            import csv
            power_values = []
            timestamps = []
            
            with open(log_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        power = float(row.get("power_w", 0)) * 1000  # Convert to mW
                        power_values.append(power)
                        timestamps.append(row.get("timestamp", ""))
                    except (ValueError, KeyError):
                        continue
            
            if not power_values:
                continue
            
            analysis = {
                "log_file": log_file.name,
                "samples": len(power_values),
                "min_power_mw": min(power_values),
                "max_power_mw": max(power_values),
                "avg_power_mw": sum(power_values) / len(power_values),
                "duration_seconds": len(power_values)  # Assuming 1Hz sampling
            }
            
            # Low power analysis
            if threshold_mw:
                low_power_samples = [p for p in power_values if p < threshold_mw]
                analysis["low_power"] = {
                    "threshold_mw": threshold_mw,
                    "samples_below": len(low_power_samples),
                    "percentage": (len(low_power_samples) / len(power_values)) * 100,
                    "min_low_power_mw": min(low_power_samples) if low_power_samples else None
                }
            
            # Suspend/resume detection (power drops significantly)
            if len(power_values) > 10:
                baseline = sum(power_values[:10]) / 10
                suspend_threshold = baseline * 0.3  # 70% drop indicates suspend
                suspend_events = sum(1 for p in power_values if p < suspend_threshold)
                analysis["suspend_detection"] = {
                    "baseline_mw": baseline,
                    "suspend_threshold_mw": suspend_threshold,
                    "potential_suspend_events": suspend_events
                }
            
            analyses.append(analysis)
            
        except Exception as e:
            analyses.append({
                "log_file": log_file.name,
                "error": str(e)
            })
    
    return {
        "analyses": analyses,
        "count": len(analyses)
    }


def monitor_low_power(
    device_id: str,
    duration: int = 300,
    threshold_mw: float = 100.0,
    sample_rate: float = 1.0
) -> Dict[str, Any]:
    """
    Monitor device for low power consumption.
    
    Args:
        device_id: Device identifier
        duration: Monitoring duration in seconds
        threshold_mw: Low power threshold in mW
        sample_rate: Sampling rate in Hz
        
    Returns:
        Low power monitoring results
    """
    try:
        from mcp_remote_testing.tools.power_monitor import start_power_monitoring
        
        # Start monitoring
        result = start_power_monitoring(
            device_id=device_id,
            test_name=f"low_power_{device_id}",
            duration=duration
        )
        
        if not result.get("success"):
            return result
        
        return {
            "success": True,
            "device_id": device_id,
            "monitoring_started": True,
            "duration_seconds": duration,
            "threshold_mw": threshold_mw,
            "sample_rate": sample_rate,
            "process_id": result.get("process_id"),
            "message": f"Monitoring started. Check logs after {duration}s for analysis."
        }
        
    except Exception as e:
        return {"error": f"Failed to start low power monitoring: {str(e)}"}


def compare_power_profiles(
    test_names: List[str],
    device_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compare power consumption across multiple test runs.
    
    Args:
        test_names: List of test names to compare
        device_id: Optional device filter
        
    Returns:
        Comparison analysis
    """
    comparisons = []
    
    for test_name in test_names:
        analysis = analyze_power_logs(test_name=test_name, device_id=device_id)
        if "error" not in analysis and analysis.get("analyses"):
            # Get average from most recent analysis
            latest = analysis["analyses"][0]
            comparisons.append({
                "test_name": test_name,
                "avg_power_mw": latest.get("avg_power_mw"),
                "min_power_mw": latest.get("min_power_mw"),
                "max_power_mw": latest.get("max_power_mw"),
                "samples": latest.get("samples")
            })
    
    if not comparisons:
        return {"error": "No valid power profiles found for comparison"}
    
    # Calculate differences
    if len(comparisons) > 1:
        baseline = comparisons[0]
        for comp in comparisons[1:]:
            comp["vs_baseline"] = {
                "avg_diff_mw": comp["avg_power_mw"] - baseline["avg_power_mw"],
                "avg_diff_percent": ((comp["avg_power_mw"] - baseline["avg_power_mw"]) / baseline["avg_power_mw"]) * 100
            }
    
    return {
        "comparisons": comparisons,
        "count": len(comparisons)
    }

