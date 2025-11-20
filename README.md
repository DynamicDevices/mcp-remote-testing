# Lab Testing MCP Server

[![Tests](https://github.com/DynamicDevices/ai-lab-testing/actions/workflows/tests.yml/badge.svg)](https://github.com/DynamicDevices/ai-lab-testing/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

MCP server exposing remote embedded hardware testing capabilities to AI assistants.

**Version**: 0.4.1

## Mission

**Making remote embedded hardware development easy and accessible for engineers.**

This project is designed to make remote hardware testing and development as seamless as possible. Engineers working remotely should be able to:

- **Discover and connect** to lab devices effortlessly
- **Set up secure access** (SSH keys, passwordless sudo) with minimal friction
- **Run commands and tests** on remote boards without complex setup
- **Build and deploy** applications to remote devices
- **Clean up securely** when finished

The MCP server provides intelligent tooling that guides engineers through best practices, suggests next steps, and handles common workflows automatically. When problems occur, the tools provide actionable suggestions and clear next steps.

**Key Design Principles:**
- **Ease of Use**: Tools should be intuitive and require minimal configuration
- **Helpful Guidance**: Error messages include suggestions and next steps
- **Best Practices**: Tools guide users toward secure, maintainable workflows
- **Remote-First**: Optimized for engineers working remotely via VPN

> **⚠️ ALPHA QUALITY WARNING**: This package is currently in **alpha** development status. It is **not ready for professional or production use**. The API may change, features may be incomplete, and there may be bugs. Use at your own risk. See [PUBLISHING.md](PUBLISHING.md) for more details.

## Installation

**Requirements:**
- **Python 3.10+** (MCP SDK requires Python 3.10+)
- **WireGuard tools** (for VPN features) - See [VPN Setup Guide](docs/VPN_SETUP.md)
- **fioctl CLI tool** (optional, for Foundries VPN features) - See [Foundries VPN Setup](docs/FOUNDRIES_VPN_SETUP.md)

### From PyPI (Recommended)

```bash
# Install from PyPI
python3.10 -m pip install ai-lab-testing

# Or with development dependencies
python3.10 -m pip install "ai-lab-testing[dev]"
```

### From Source

```bash
# Clone the repository
git clone https://github.com/DynamicDevices/ai-lab-testing.git
cd ai-lab-testing

# Install in development mode
python3.10 -m pip install -e ".[dev]"

# Verify installation
python3.10 lab_testing/test_server.py
```

## Configuration

### MCP Server Configuration

Add to Cursor MCP config (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "ai-lab-testing": {
      "command": "python3.10",
      "args": ["/path/to/ai-lab-testing/lab_testing/server.py"],
      "env": {
        "LAB_TESTING_ROOT": "/path/to/ai-lab-testing",
        "VPN_CONFIG_PATH": "/path/to/wg0.conf"
      }
    }
  }
}
```

**Important:** Use `python3.10` (or `python3.11+`) since MCP SDK requires Python 3.10+.

### Target Network Configuration

Configure the target network for lab testing operations:

**Option 1: Environment Variable** (in `~/.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "ai-lab-testing": {
      "command": "python3.10",
      "args": ["/path/to/ai-lab-testing/lab_testing/server.py"],
      "env": {
        "LAB_TESTING_ROOT": "/path/to/ai-lab-testing",
        "TARGET_NETWORK": "192.168.2.0/24"
      }
    }
  }
}
```

**Option 2: Config File** (in `lab_devices.json`):
```json
{
  "lab_infrastructure": {
    "network_access": {
      "target_network": "192.168.2.0/24",
      "lab_networks": ["192.168.2.0/24"]
    }
  }
}
```

**Default**: `192.168.2.0/24` if not configured.

### Tool Timeouts

Some tools like `create_network_map` may take longer than 30 seconds for full network scans. If tool calls timeout:
- Use `quick_mode: true` to skip network scanning (completes in <5s)
- Network scanning has been optimized with faster timeouts and increased parallelism

### VPN Setup

The server auto-detects WireGuard VPN configs. If you don't have one:
- See [docs/VPN_SETUP.md](docs/VPN_SETUP.md) for setup guide
- Use MCP tools: `vpn_setup_instructions`, `create_vpn_config_template`

See [docs/SETUP.md](docs/SETUP.md) for detailed setup instructions or `mcp.json.example` for a template.

## Architecture

```mermaid
graph TB
    subgraph "AI Assistant"
        AI[Claude/Cursor]
    end
    subgraph "MCP Server"
        MCP[server.py]
        TOOLS[Tools]
        RES[Resources]
    end
    subgraph "Lab Framework"
        CFG[Config]
        DEV[Device Manager]
        VPN[VPN Manager]
        PWR[Power Monitor]
    end
    subgraph "Hardware"
        BOARD[iMX Boards]
        DMM[DMM]
        TASMOTA[Tasmota]
    end
    AI -->|MCP| MCP
    MCP --> TOOLS
    TOOLS --> DEV
    TOOLS --> VPN
    TOOLS --> PWR
    DEV --> BOARD
    PWR --> DMM
```

Data flow: AI → MCP Server → Tools → Lab Framework → Hardware

## Tools

- **Device**: `list_devices` (with filtering, sorting, limiting, summary stats, power state) - Shows device inventory with Power Switch column: Tasmota devices display their own power state (🟢 ON/🔴 OFF), other devices show which power switch controls them. Supports filtering by type, status, SSH status, power state, and search. Supports sorting by IP, friendly_name, status, or last_seen. Supports limiting results. Use force_refresh to bypass cache. `test_device`, `ssh_to_device`, `verify_device_identity`, `verify_device_by_ip`, `update_device_ip`, `update_device_friendly_name`
- **VPN**: `vpn_status`, `connect_vpn`, `disconnect_vpn`
- **Power**: `start_power_monitoring` (DMM or Tasmota), `get_power_logs`, `analyze_power_logs`, `monitor_low_power`, `compare_power_profiles` - Power monitoring via DMM (SCPI) or Tasmota energy monitoring
- **Tasmota**: `tasmota_control`, `list_tasmota_devices`, `power_cycle_device` - Power cycle devices via Tasmota switches. Tasmota devices show power state (🟢 ON/🔴 OFF) in the Power Switch column and consumption (Watts) in the Type column of the device list
- **Test Equipment**: `list_test_equipment`, `query_test_equipment` - Auto-detect and query test equipment (DMM, oscilloscopes) via SCPI protocol
- **OTA/Containers**: `check_ota_status`, `trigger_ota_update`, `list_containers`, `deploy_container`, `get_system_status`, `get_firmware_version`, `get_foundries_registration_status`, `get_secure_boot_status`, `get_device_identity`
- **Process Management**: `kill_stale_processes` - Kill duplicate processes that might interfere
- **Remote Access**: `create_ssh_tunnel`, `list_ssh_tunnels`, `close_ssh_tunnel`, `access_serial_port`, `list_serial_devices` - SSH tunnels and serial port access
- **Change Tracking**: `get_change_history`, `revert_changes` - Track and revert changes for security/debugging
- **Batch/Regression**: `batch_operation`, `regression_test`, `get_device_groups`
- **Network Mapping**: `create_network_map` - Visual map of network with device type, uptime, friendly names, power switches
- **Device Verification**: `verify_device_identity`, `verify_device_by_ip`, `update_device_ip` - Verify device identity in DHCP environments. Device list shows SSH status, last seen timestamps, and power switch information (Tasmota devices show their own state, other devices show controlling switch)
- **Help**: `help` - Get usage documentation and examples

## Resources

- `device://inventory` - Device inventory
- `network://status` - Network/VPN status
- `config://lab_devices` - Raw config
- `help://usage` - Help documentation and usage examples
- `health://status` - Server health, metrics, and SSH pool status

## Development

```bash
# Use Python 3.10+ for development
python3.10 -m pip install -e ".[dev]"
pre-commit install
black . && ruff check . --fix
```

**Adding tools**: Create function in `lab_testing/tools/`, register in `lab_testing/server/tool_definitions.py` and `lab_testing/server/tool_handlers.py`.

**Versioning**: Semantic versioning (MAJOR.MINOR.PATCH). Update `version.py`, see [CHANGELOG.md](CHANGELOG.md).

## Documentation

- [API Reference](docs/API.md) - Tool and resource API
- [Setup Guide](docs/SETUP.md) - Installation and configuration
- [Architecture Diagram](docs/architecture.mmd) - Full system diagram

## License

GPL-3.0-or-later - Copyright (C) 2025 Dynamic Devices Ltd

See [LICENSE](LICENSE) for full license text.

## Maintainer

Alex J Lennon <ajlennon@dynamicdevices.co.uk>
