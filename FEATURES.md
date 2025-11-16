# Feature Overview

## Core Capabilities

### Foundries.io Integration
- **OTA Updates**: Check status, trigger updates, monitor progress
- **Container Management**: List, deploy, update Docker containers
- **System Status**: Comprehensive health monitoring (uptime, load, memory, disk, kernel)

### Low Power Analysis
- **Power Log Analysis**: Detect suspend/resume events, low power periods
- **Low Power Monitoring**: Targeted monitoring with configurable thresholds
- **Profile Comparison**: Compare power consumption across test runs

### Batch Operations & Regression Testing
- **Parallel Operations**: Execute operations on multiple devices simultaneously
- **Device Grouping**: Tag-based organization for rack management
- **Regression Testing**: Automated test sequences across device groups
- **Rack Support**: Foundation for managing racks of boards

## Use Cases

### OTA Update Workflow
1. Check current OTA status
2. Trigger update to target
3. Monitor system status
4. Verify containers after update

### Container Deployment
1. List current containers
2. Deploy new container image
3. Verify deployment

### Low Power Testing
1. Start low power monitoring
2. Analyze logs for suspend/resume
3. Compare power profiles

### Regression Testing
1. Organize devices by tags/groups
2. Run test sequence on group
3. Review results across all devices

## Device Configuration

Add to device config for Foundries.io support:
```json
{
  "fio_factory": "factory-name",
  "fio_target": "target-name",
  "fio_current": "current-version",
  "tags": ["rack1", "regression", "imx93"]
}
```

