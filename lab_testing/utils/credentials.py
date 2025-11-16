"""
Credential Management for Remote Access

Handles secure credential caching and SSH key management.
Prefer public key authentication, fallback to sshpass for passwords.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

# Credential cache location (user-specific, not in repo)
CREDENTIAL_CACHE_DIR = Path.home() / ".cache" / "ai-lab-testing"
CREDENTIAL_CACHE_FILE = CREDENTIAL_CACHE_DIR / "credentials.json"


def ensure_cache_dir():
    """Ensure credential cache directory exists"""
    CREDENTIAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Set restrictive permissions
    os.chmod(CREDENTIAL_CACHE_DIR, 0o700)


def load_credentials() -> Dict[str, Dict[str, str]]:
    """Load cached credentials from user's home directory"""
    ensure_cache_dir()

    if not CREDENTIAL_CACHE_FILE.exists():
        return {}

    try:
        with open(CREDENTIAL_CACHE_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_credentials(credentials: Dict[str, Dict[str, str]]):
    """Save credentials to cache (user's home directory, not in repo)"""
    ensure_cache_dir()

    # Set restrictive permissions before writing
    CREDENTIAL_CACHE_FILE.touch(mode=0o600)

    with open(CREDENTIAL_CACHE_FILE, "w") as f:
        json.dump(credentials, f, indent=2)

    # Ensure file permissions are restrictive
    os.chmod(CREDENTIAL_CACHE_FILE, 0o600)


def get_credential(device_id: str, credential_type: str = "ssh") -> Optional[Dict[str, str]]:
    """
    Get cached credential for a device.

    Args:
        device_id: Device identifier
        credential_type: Type of credential (ssh, sudo, etc.)

    Returns:
        Credential dict with username/password or None
    """
    credentials = load_credentials()
    key = f"{device_id}:{credential_type}"
    return credentials.get(key)


def cache_credential(
    device_id: str, username: str, password: Optional[str] = None, credential_type: str = "ssh"
):
    """
    Cache credential for a device (stored in user's home, not in repo).

    Args:
        device_id: Device identifier
        username: Username
        password: Password (optional, prefer SSH keys)
        credential_type: Type of credential (ssh, sudo, etc.)
    """
    credentials = load_credentials()
    key = f"{device_id}:{credential_type}"
    credentials[key] = {
        "username": username,
        "password": password,  # Only if needed, prefer SSH keys
    }
    save_credentials(credentials)


def check_ssh_key_installed(device_ip: str, username: str) -> bool:
    """
    Check if SSH key is already installed on target device.

    Args:
        device_ip: Device IP address
        username: SSH username

    Returns:
        True if key-based auth works
    """
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "StrictHostKeyChecking=no",
                f"{username}@{device_ip}",
                "echo OK",
            ],
            check=False,
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def install_ssh_key(device_ip: str, username: str, password: Optional[str] = None) -> bool:
    """
    Install SSH public key on target device.
    Prefer this over password authentication.

    Args:
        device_ip: Device IP address
        username: SSH username
        password: Password for initial access (if key not installed)

    Returns:
        True if key was installed successfully
    """
    # Check if key already works
    if check_ssh_key_installed(device_ip, username):
        return True

    # Get default SSH public key
    ssh_key_path = Path.home() / ".ssh" / "id_rsa.pub"
    if not ssh_key_path.exists():
        ssh_key_path = Path.home() / ".ssh" / "id_ed25519.pub"

    if not ssh_key_path.exists():
        return False

    # Read public key
    try:
        with open(ssh_key_path) as f:
            public_key = f.read().strip()
    except OSError:
        return False

    # Install key using sshpass if password provided, otherwise prompt
    if password:
        cmd = [
            "sshpass",
            "-p",
            password,
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            f"{username}@{device_ip}",
            f"mkdir -p ~/.ssh && echo '{public_key}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys",
        ]
    else:
        # Try without password (key might already be partially installed)
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            f"{username}@{device_ip}",
            f"mkdir -p ~/.ssh && echo '{public_key}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys",
        ]

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, timeout=30)
        if result.returncode == 0:
            # Verify it works
            return check_ssh_key_installed(device_ip, username)
    except Exception:
        pass

    return False


def enable_passwordless_sudo(device_ip: str, username: str, password: Optional[str] = None) -> bool:
    """
    Enable passwordless sudo on target device for debugging.

    Args:
        device_ip: Device IP address
        username: SSH username
        password: Sudo password (if needed for initial setup)

    Returns:
        True if passwordless sudo was enabled
    """
    sudo_config = f"{username} ALL=(ALL) NOPASSWD: ALL"

    # Check if already configured
    check_cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        f"{username}@{device_ip}",
        f"sudo grep -q '{sudo_config}' /etc/sudoers.d/{username} 2>/dev/null && echo OK",
    ]

    try:
        result = subprocess.run(check_cmd, check=False, capture_output=True, timeout=10)
        if result.returncode == 0 and b"OK" in result.stdout:
            return True
    except Exception:
        pass

    # Install passwordless sudo config using sshpass if password provided
    if password:
        # Check if sshpass is available
        try:
            subprocess.run(["which", "sshpass"], capture_output=True, check=True)
            cmd = [
                "sshpass",
                "-p",
                password,
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                f"{username}@{device_ip}",
                f"echo '{sudo_config}' | sudo tee /etc/sudoers.d/{username} && sudo chmod 440 /etc/sudoers.d/{username}",
            ]
        except (subprocess.CalledProcessError, FileNotFoundError):
            # sshpass not available, try interactive
            cmd = [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                f"{username}@{device_ip}",
                f"echo '{sudo_config}' | sudo tee /etc/sudoers.d/{username} && sudo chmod 440 /etc/sudoers.d/{username}",
            ]
    else:
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            f"{username}@{device_ip}",
            f"echo '{sudo_config}' | sudo tee /etc/sudoers.d/{username} && sudo chmod 440 /etc/sudoers.d/{username}",
        ]

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, timeout=30)
        return result.returncode == 0
    except Exception:
        return False


def get_ssh_command(
    device_ip: str,
    username: str,
    command: str,
    device_id: Optional[str] = None,
    use_password: bool = False,
) -> list:
    """
    Build SSH command with appropriate authentication method.
    Prefers SSH keys, falls back to sshpass if needed.

    Args:
        device_ip: Device IP address
        username: SSH username
        command: Command to execute
        device_id: Device ID for credential lookup
        use_password: Force password authentication (if key fails)

    Returns:
        Command list for subprocess
    """
    # Try key-based auth first
    if not use_password and check_ssh_key_installed(device_ip, username):
        return [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=no",
            f"{username}@{device_ip}",
            command,
        ]

    # Fall back to password if needed
    if use_password and device_id:
        cred = get_credential(device_id, "ssh")
        if cred and cred.get("password"):
            return [
                "sshpass",
                "-p",
                cred["password"],
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ConnectTimeout=10",
                f"{username}@{device_ip}",
                command,
            ]

    # Default: try key-based (may prompt for password)
    return [
        "ssh",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=no",
        f"{username}@{device_ip}",
        command,
    ]
