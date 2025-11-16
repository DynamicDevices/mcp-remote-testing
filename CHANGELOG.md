# Changelog

[Semantic Versioning](https://semver.org/)

## [0.1.0] - 2025-11-16

### Added
- MCP server for remote lab testing
- **Device Management**: list, test, SSH access
- **VPN Management**: connect, disconnect, status
- **Power Monitoring**: basic monitoring and logging
- **Tasmota Control**: power switch control
- **OTA Management**: Foundries.io OTA status, updates, container deployment
- **System Status**: comprehensive device health monitoring
- **Batch Operations**: async parallel operations on multiple devices (5-10x faster)
- **Regression Testing**: automated parallel test sequences for device groups
- **Power Analysis**: low power detection, suspend/resume analysis, profile comparison
- **Device Grouping**: tag-based organization for rack management
- **Self-Describing Help**: built-in documentation and usage examples
- **Structured Logging**: file and console logging with request IDs
- **Health Check Resource**: server health, metrics, SSH pool status
- **Enhanced Error Types**: custom exception hierarchy with detailed context
- **SSH Connection Pooling**: persistent connections for faster execution
- **Process Management**: track and kill stale/duplicate processes to prevent conflicts
- **Firmware Version Detection**: read /etc/os-release for version information
- **Foundries.io Registration Status**: check device registration, connection, and update status via /var/sota and aktualizr
- **Secure Boot Status**: detailed secure boot information (U-Boot, kernel, EFI, HAB/CAAM for i.MX devices)
- **Device Identity**: hostname, SOC unique ID, and Foundries registration name tracking
- **Change Tracking**: track all changes made to devices for security/debugging, with revert capability
- **SSH Tunnels**: create and manage SSH tunnels through VPN for direct device access
- **Serial Port Access**: access serial ports on remote Linux laptops for low power/bootup debugging
- Resources: device inventory, network status, config, help, health
- Pre-commit/pre-push hooks
- Documentation and architecture diagram
- CI workflow

