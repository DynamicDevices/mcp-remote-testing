# Setup

## Installation

**Requirements: Python 3.10+** (MCP SDK requires Python 3.10+)

```bash
# Install the MCP SDK (requires Python 3.10+)
python3.10 -m pip install git+https://github.com/modelcontextprotocol/python-sdk.git

# Install this package
python3.10 -m pip install -e ".[dev]"  # Optional: dev dependencies

# Optional: git hooks
pre-commit install
```

**Note:** If your default `python3` is 3.8 or 3.9, use `python3.10` explicitly for MCP SDK installation.

## Configuration

Uses existing lab testing framework:
- Device config: `{LAB_TESTING_ROOT}/config/lab_devices.json`
- VPN config: Auto-detected (see [VPN Setup Guide](VPN_SETUP.md))

### Environment Variables

- `LAB_TESTING_ROOT`: Path to lab testing framework (default: `/data_drive/esl/lab-testing`)
- `VPN_CONFIG_PATH`: Path to WireGuard config file (optional, auto-detected if not set)

### VPN Configuration

The server automatically searches for WireGuard configs in:
1. `VPN_CONFIG_PATH` environment variable (if set)
2. `{LAB_TESTING_ROOT}/secrets/wg0.conf` (or `wireguard.conf`, `vpn.conf`)
3. `~/.config/wireguard/*.conf`
4. `/etc/wireguard/*.conf`

**No VPN?** See [VPN Setup Guide](VPN_SETUP.md) for setup instructions, or use the MCP tools:
- `vpn_setup_instructions` - Get setup help
- `create_vpn_config_template` - Create a config template
- `check_wireguard_installed` - Check if WireGuard is installed

## Cursor Integration

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "lab-testing": {
      "command": "python3.10",
      "args": ["/absolute/path/to/lab_testing/server.py"],
      "env": {"LAB_TESTING_ROOT": "/data_drive/esl/lab-testing"}
    }
  }
}
```

**Important:** Use `python3.10` (or `python3.11+`) since MCP SDK requires Python 3.10+.

Or use installed package: `"command": "python3.10", "args": ["-m", "lab_testing.server"]`

Restart Cursor.

## Verification

```bash
python3 test_server.py
```

