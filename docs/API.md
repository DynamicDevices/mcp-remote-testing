# API Reference

## Tools

### Device Management
- `list_devices()` - List all devices with status/IPs/types
- `test_device(device_id)` - Test connectivity (ping/SSH)
- `ssh_to_device(device_id, command, username?)` - Execute SSH command

### VPN Management
- `vpn_status()` - Get WireGuard connection status
- `connect_vpn()` - Connect to VPN
- `disconnect_vpn()` - Disconnect from VPN

### Power Monitoring
- `start_power_monitoring(device_id?, test_name?, duration?)` - Start monitoring session
- `get_power_logs(test_name?, limit=10)` - Get recent logs

### Tasmota Control
- `tasmota_control(device_id, action)` - Control device (`on`|`off`|`toggle`|`status`|`energy`)
- `list_tasmota_devices()` - List all Tasmota devices

### OTA/Container Management
- `check_ota_status(device_id)` - Check Foundries.io OTA update status
- `trigger_ota_update(device_id, target?)` - Trigger OTA update
- `list_containers(device_id)` - List Docker containers
- `deploy_container(device_id, container_name, image)` - Deploy/update container
- `get_system_status(device_id)` - Get system status (uptime, load, memory, disk, kernel)

### Batch Operations
- `batch_operation(device_ids[], operation, ...)` - Execute operation on multiple devices
- `regression_test(device_group?|device_ids[], test_sequence?)` - Run regression test sequence
- `get_device_groups()` - Get devices organized by groups/tags

### Power Analysis
- `analyze_power_logs(test_name?, device_id?, threshold_mw?)` - Analyze for low power/suspend detection
- `monitor_low_power(device_id, duration?, threshold_mw?, sample_rate?)` - Monitor low power consumption
- `compare_power_profiles(test_names[], device_id?)` - Compare power across test runs

### Help
- `help(topic?)` - Get help documentation (topic: `all`|`tools`|`resources`|`workflows`|`troubleshooting`|`examples`)

## Resources

- `device://inventory` - Device inventory JSON
- `network://status` - Network/VPN status
- `config://lab_devices` - Raw config file
- `help://usage` - Complete help documentation

