# Setup

## Installation

```bash
pip3 install -r requirements.txt
pip3 install git+https://github.com/modelcontextprotocol/python-sdk.git
pip3 install -e ".[dev]"  # Optional: dev dependencies
pre-commit install  # Optional: git hooks
```

## Configuration

Uses existing lab testing framework:
- Device config: `/data_drive/esl/lab-testing/config/lab_devices.json`
- VPN config: `/data_drive/esl/lab-testing/secrets/wg0.conf`

Override: `export LAB_TESTING_ROOT=/path/to/lab-testing`

## Cursor Integration

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "lab-testing": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_remote_testing/server.py"],
      "env": {"LAB_TESTING_ROOT": "/data_drive/esl/lab-testing"}
    }
  }
}
```

Or use installed package: `"command": "mcp-lab-testing"`

Restart Cursor.

## Verification

```bash
python3 test_server.py
```

