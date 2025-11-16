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
- `start_power_monitoring(device_id?, test_name?, duration?, monitor_type?)` - Start monitoring session
  - Supports both DMM (Digital Multimeter) and Tasmota devices
  - `monitor_type`: "dmm" (default) or "tasmota" (auto-detected from device type)
  - DMM: Direct power measurement via SCPI commands
  - Tasmota: Power monitoring via Tasmota energy monitoring (requires energy monitoring enabled)
- `get_power_logs(test_name?, limit=10)` - Get recent logs
- `tasmota_control(device_id, "energy")` - Get current power consumption from Tasmota device

### Tasmota Control
- `tasmota_control(device_id, action)` - Control device (`on`|`off`|`toggle`|`status`|`energy`)
- `list_tasmota_devices()` - List all Tasmota devices and devices they control
- `power_cycle_device(device_id, off_duration=5)` - Power cycle device via mapped Tasmota switch (turns off, waits, turns on)

### OTA/Container Management
- `check_ota_status(device_id)` - Check Foundries.io OTA update status
- `trigger_ota_update(device_id, target?)` - Trigger OTA update
- `list_containers(device_id)` - List Docker containers
- `deploy_container(device_id, container_name, image)` - Deploy/update container
- `get_system_status(device_id)` - Get system status (uptime, load, memory, disk, kernel)
- `get_firmware_version(device_id)` - Get firmware/OS version from /etc/os-release
- `get_foundries_registration_status(device_id)` - Check Foundries.io registration, connection, update status
- `get_secure_boot_status(device_id)` - Get detailed secure boot status (U-Boot, kernel, EFI, HAB/CAAM)
- `get_device_identity(device_id)` - Get device identity: hostname, SOC unique ID, Foundries registration name

### Batch Operations
- `batch_operation(device_ids[], operation, max_concurrent=5, ...)` - Execute operation on multiple devices in parallel
- `regression_test(device_group?|device_ids[], test_sequence?, max_concurrent=5)` - Run regression test sequence in parallel
- `get_device_groups()` - Get devices organized by groups/tags

### Power Analysis
- `analyze_power_logs(test_name?, device_id?, threshold_mw?)` - Analyze for low power/suspend detection
- `monitor_low_power(device_id, duration?, threshold_mw?, sample_rate?)` - Monitor low power consumption
- `compare_power_profiles(test_names[], device_id?)` - Compare power across test runs

### Process Management
- `kill_stale_processes(device_id, process_pattern, force?)` - Kill stale/duplicate processes that might interfere

### Remote Access
- `create_ssh_tunnel(device_id, local_port?, remote_port=22, tunnel_type=local)` - Create SSH tunnel through VPN
- `list_ssh_tunnels()` - List active SSH tunnels
- `close_ssh_tunnel(local_port?|device_id)` - Close an SSH tunnel
- `access_serial_port(remote_laptop_id, serial_device=/dev/ttyACM0, baud_rate=115200)` - Access serial port on remote laptop
- `list_serial_devices(remote_laptop_id)` - List available serial devices on remote laptop

### Change Tracking
- `get_change_history(device_id, include_reverted?)` - Get change history for security/debugging
- `revert_changes(device_id, change_id?, force?)` - Revert changes made to device

### Network Mapping & Verification
- `create_network_map(networks?, scan_networks?, test_configured_devices?, max_hosts_per_network?)` - Create visual map showing device type, uptime, friendly names, power switches
- `verify_device_identity(device_id, ip?)` - Verify device identity by hostname/unique ID (for DHCP)
- `verify_device_by_ip(ip, username?, ssh_port?)` - Identify device at IP by checking hostname/unique ID
- `update_device_ip(device_id, new_ip)` - Verify and update device IP if changed (DHCP)

### Help
- `help(topic?)` - Get help documentation (topic: `all`|`tools`|`resources`|`workflows`|`troubleshooting`|`examples`)

## Resources

- `device://inventory` - Device inventory JSON
- `network://status` - Network/VPN status
- `config://lab_devices` - Raw config file
- `help://usage` - Complete help documentation
- `health://status` - Server health, metrics, SSH pool status, uptime

