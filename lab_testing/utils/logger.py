"""
Structured Logging for MCP Remote Testing

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Global logger instance
_logger: Optional[logging.Logger] = None


def setup_logger(
    name: str = "lab_testing",
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    Set up structured logger for MCP server.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_to_file: Enable file logging
        log_to_console: Enable console logging

    Returns:
        Configured logger instance
    """
    global _logger

    if _logger is not None:
        return _logger

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()  # Remove any existing handlers

    # Prevent duplicate logs from propagating to root logger
    logger.propagate = False

    # Formatter with timestamp, level, name, and message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler (always enabled for debugging)
    if log_to_file:
        log_dir = Path.home() / ".cache" / "ai-lab-testing" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Main log file
        file_handler = logging.FileHandler(log_dir / "server.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Error log file (errors only)
        error_handler = logging.FileHandler(log_dir / "errors.log")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

    # Console handler (INFO and above)
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _logger = logger
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get logger instance. Creates one if it doesn't exist.

    Args:
        name: Optional logger name (uses default if not provided)

    Returns:
        Logger instance
    """
    if _logger is None:
        return setup_logger()

    if name:
        return logging.getLogger(name)

    return _logger


def set_log_level(level: int):
    """
    Set logging level for all handlers.

    Args:
        level: Logging level (logging.DEBUG, logging.INFO, etc.)
    """
    logger = get_logger()
    logger.setLevel(level)
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
            # Console handler - keep at INFO or above
            handler.setLevel(max(level, logging.INFO))
        else:
            handler.setLevel(level)


def log_tool_call(tool_name: str, arguments: dict, request_id: Optional[str] = None):
    """
    Log tool call with request ID for tracing.

    Args:
        tool_name: Name of the tool being called
        arguments: Tool arguments
        request_id: Optional request ID for tracing
    """
    logger = get_logger()
    msg = f"Tool call: {tool_name}"
    if request_id:
        msg += f" [request_id={request_id}]"
    logger.info(msg)
    logger.debug(f"Arguments: {arguments}")


def log_tool_result(
    tool_name: str, success: bool, request_id: Optional[str] = None, error: Optional[str] = None
):
    """
    Log tool execution result.

    Args:
        tool_name: Name of the tool
        success: Whether execution succeeded
        request_id: Optional request ID
        error: Error message if failed
    """
    logger = get_logger()
    msg = f"Tool result: {tool_name} - {'SUCCESS' if success else 'FAILED'}"
    if request_id:
        msg += f" [request_id={request_id}]"

    if success:
        logger.info(msg)
    else:
        logger.warning(msg)
        if error:
            logger.error(f"Error: {error}")
