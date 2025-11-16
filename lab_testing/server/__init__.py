"""
Lab Testing MCP Server Package

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

# Re-export main from server.py
# Note: server.py and server/ directory both exist, so we import the module directly
import importlib.util
from pathlib import Path

_server_py_path = Path(__file__).parent.parent / "server.py"
if _server_py_path.exists():
    spec = importlib.util.spec_from_file_location("lab_testing.mcp_server", _server_py_path)
    mcp_server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_server)
    main = mcp_server.main
    __all__ = ["main"]
else:
    __all__ = []
