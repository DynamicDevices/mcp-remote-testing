# Test Suite

Comprehensive test suite for MCP Remote Testing Server.

## Running Tests

```bash
# Install test dependencies
python3.10 -m pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=lab_testing --cov-report=html

# Run specific test file
pytest tests/test_tools_device.py

# Run with verbose output
pytest -v
```

## Test Structure

- `conftest.py` - Shared fixtures and configuration
- `test_tools_*.py` - Unit tests for tool modules
- `test_server_integration.py` - Integration tests for server handlers

## Test Categories

### Unit Tests
- Device management (`test_tools_device.py`)
- Tasmota control (`test_tools_tasmota.py`)
- Network mapping (`test_tools_network.py`)
- VPN management
- OTA management
- Power monitoring

### Integration Tests
- Tool handler execution
- Error handling
- Parameter validation
- Response formatting

## Mocking Strategy

Tests use mocks for:
- SSH connections (no real devices required)
- VPN status (no real VPN required)
- Subprocess execution (no real commands)
- File system operations (temporary configs)

## Adding Tests

1. Create test file: `tests/test_tools_<module>.py`
2. Import fixtures from `conftest.py`
3. Mock external dependencies (SSH, subprocess, etc.)
4. Test both success and error cases
5. Verify response structure and content

