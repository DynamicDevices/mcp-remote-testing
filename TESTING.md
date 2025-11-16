# Testing Guide

## Overview

Comprehensive test suite for MCP Remote Testing Server to ensure all tools work correctly and prevent regressions.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and configuration
├── test_tools_device.py     # Device management tests
├── test_tools_tasmota.py    # Tasmota control tests
├── test_tools_network.py    # Network mapping tests
├── test_tools_power.py      # Power monitoring tests (DMM & Tasmota)
└── test_server_integration.py  # Server integration tests
```

## Running Tests

```bash
# Install test dependencies
python3.10 -m pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=lab_testing --cov-report=html

# Run specific test file
pytest tests/test_tools_device.py -v

# Run specific test class
pytest tests/test_tools_power.py::TestStartPowerMonitoring -v
```

## Test Categories

### Unit Tests
- **Device Management** (`test_tools_device.py`)
  - Device listing
  - Device connectivity testing
  - SSH command execution
  - Device identifier resolution (device_id/friendly_name)

- **Tasmota Control** (`test_tools_tasmota.py`)
  - Tasmota device control (on/off/toggle/status/energy)
  - Power switch mapping
  - Power cycling

- **Network Mapping** (`test_tools_network.py`)
  - Network map creation
  - Device verification
  - IP address updates

- **Power Monitoring** (`test_tools_power.py`)
  - DMM power monitoring
  - Tasmota power monitoring
  - Power log retrieval

### Integration Tests
- **Server Integration** (`test_server_integration.py`)
  - Tool handler execution
  - Error handling
  - Parameter validation
  - Response formatting

## Mocking Strategy

Tests use mocks to avoid requiring real hardware:

- **SSH Connections**: Mocked subprocess calls
- **VPN Status**: Mocked WireGuard status
- **Device Config**: Temporary JSON config files
- **Tasmota Devices**: Mocked HTTP responses
- **DMM**: Mocked SCPI command responses

## Adding New Tests

1. **Create test file**: `tests/test_tools_<module>.py`
2. **Import fixtures**: Use fixtures from `conftest.py`
3. **Mock dependencies**: Mock SSH, subprocess, file I/O
4. **Test both paths**: Success and error cases
5. **Verify structure**: Check response format and content

### Example Test Template

```python
import pytest
from unittest.mock import patch, MagicMock
from lab_testing.tools.my_module import my_function

class TestMyFunction:
    """Tests for my_function"""
    
    @patch("lab_testing.tools.my_module.external_dependency")
    def test_success(self, mock_dep):
        """Test successful execution"""
        mock_dep.return_value = {"success": True}
        result = my_function("arg1")
        assert result["success"] is True
    
    def test_error_case(self):
        """Test error handling"""
        result = my_function(None)
        assert result["success"] is False
        assert "error" in result
```

## Test Coverage Goals

- **Unit Tests**: >80% coverage for tool modules
- **Integration Tests**: All tool handlers tested
- **Error Cases**: All error paths covered
- **Edge Cases**: Boundary conditions tested

## Continuous Integration

Tests should run automatically on:
- Pull requests
- Commits to main branch
- Pre-commit hooks (optional)

## Power Monitoring Tests

Special attention to dual monitoring support:

- **DMM Monitoring**: Tests DMM script execution
- **Tasmota Monitoring**: Tests Tasmota energy API
- **Auto-detection**: Tests monitor type detection
- **Error Handling**: Tests missing scripts/devices

## Best Practices

1. **Isolation**: Each test should be independent
2. **Fast**: Tests should complete quickly (<1s each)
3. **Deterministic**: No random behavior
4. **Clear Names**: Test names describe what they test
5. **Documentation**: Docstrings explain test purpose

