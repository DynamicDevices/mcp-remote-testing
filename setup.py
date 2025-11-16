"""
Setup script for Lab Testing MCP Server
"""

from setuptools import setup, find_packages

# Read version from version module
try:
    from mcp_remote_testing.version import __version__
except ImportError:
    __version__ = "0.1.0"

setup(
    name="mcp-remote-testing",
    version=__version__,
    description="MCP server for remote embedded hardware testing",
    author="Alex J Lennon",
    author_email="ajlennon@dynamicdevices.co.uk",
    maintainer="Alex J Lennon",
    maintainer_email="ajlennon@dynamicdevices.co.uk",
    license="GPL-3.0-or-later",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "mcp>=1.0.0",
        "pydantic>=2.0.0",
        "requests>=2.28.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "mcp-lab-testing=mcp_remote_testing.server:main",
        ],
    },
)

