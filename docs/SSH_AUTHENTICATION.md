# SSH Authentication Guide

## Current Authentication Methods

The MCP tools support three methods of SSH authentication, in order of preference:

### 1. SSH Public Keys (Preferred) ✅

**How it works:**
- Automatically checks for SSH keys in `~/.ssh/id_rsa.pub` or `~/.ssh/id_ed25519.pub`
- Uses key-based authentication if the key is installed on the target device
- No password needed - most secure method

**Setup:**
1. Generate SSH key (if you don't have one):
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   # Or use RSA:
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   ```

2. Install key on target device:
   ```bash
   # Manual method:
   ssh-copy-id username@device_ip
   
   # Or use the MCP tool (when implemented):
   install_ssh_key device_id username [password]
   ```

**Current Status:**
- ✅ Automatically detected and used if available
- ⚠️ No MCP tool yet to install keys automatically
- 📝 SSH key installation must be done manually or via `install_ssh_key()` function

### 2. Cached Passwords (Fallback) ⚠️

**How it works:**
- Passwords are cached in `~/.cache/ai-lab-testing/credentials.json`
- Uses `sshpass` tool to provide password non-interactively
- Requires `sshpass` package: `sudo apt install sshpass`

**Current Limitations:**
- ❌ **No MCP tool to cache credentials** - passwords must be cached programmatically
- ⚠️ Credentials must be cached before use
- 📝 Cache location: `~/.cache/ai-lab-testing/credentials.json` (permissions: 600)

**Manual Credential Caching:**
```python
from lab_testing.utils.credentials import cache_credential

# Cache SSH password for a device
cache_credential(
    device_id="my-device-id",
    username="root",
    password="my-password",
    credential_type="ssh"
)
```

### 3. Interactive SSH (Fallback) ⚠️

**How it works:**
- Falls back to standard SSH command if keys and cached passwords fail
- Will prompt for password interactively (not suitable for MCP tools)
- **Not recommended** - use SSH keys or cached passwords instead

---

## Current Implementation Details

### Authentication Flow

When `ssh_to_device` is called:

1. **Check SSH Key** (`check_ssh_key_installed()`)
   - Tests if key-based auth works: `ssh -o BatchMode=yes username@ip "echo OK"`
   - If successful → use key-based SSH command

2. **Check Cached Password** (if `use_password=True`)
   - Looks up password in `~/.cache/ai-lab-testing/credentials.json`
   - If found → use `sshpass -p password ssh ...`

3. **Fallback to Standard SSH**
   - Uses standard SSH command (may prompt for password)
   - **This will fail in MCP context** (no interactive input)

### Code Location

- **Credential Management**: `lab_testing/utils/credentials.py`
  - `cache_credential()` - Cache password for device
  - `get_credential()` - Retrieve cached password
  - `check_ssh_key_installed()` - Check if key auth works
  - `install_ssh_key()` - Install SSH key on device
  - `get_ssh_command()` - Build SSH command with auth

- **SSH Execution**: `lab_testing/tools/device_manager.py`
  - `ssh_to_device()` - Execute SSH command (uses `get_ssh_command()`)

---

## Recommended Improvements

### 1. Add MCP Tool: `cache_device_credentials` ⚠️ NEEDED

**Purpose:** Allow users to cache SSH passwords via MCP tool

**Proposed Tool:**
```python
Tool(
    name="cache_device_credentials",
    description="Cache SSH credentials (username/password) for a device. "
                "Credentials are stored securely in ~/.cache/ai-lab-testing/credentials.json. "
                "Prefer SSH keys over passwords when possible.",
    inputSchema={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Device identifier (device_id or friendly_name)"
            },
            "username": {
                "type": "string",
                "description": "SSH username"
            },
            "password": {
                "type": "string",
                "description": "SSH password (optional, prefer SSH keys)"
            },
            "credential_type": {
                "type": "string",
                "enum": ["ssh", "sudo"],
                "default": "ssh",
                "description": "Type of credential to cache"
            }
        },
        "required": ["device_id", "username"]
    }
)
```

### 2. Add MCP Tool: `install_ssh_key` ⚠️ NEEDED

**Purpose:** Automatically install SSH public key on target device

**Proposed Tool:**
```python
Tool(
    name="install_ssh_key",
    description="Install SSH public key on target device for passwordless access. "
                "Uses default SSH key from ~/.ssh/id_rsa.pub or ~/.ssh/id_ed25519.pub. "
                "Requires password for initial access if key not already installed.",
    inputSchema={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Device identifier (device_id or friendly_name)"
            },
            "username": {
                "type": "string",
                "description": "SSH username (optional, uses device default)"
            },
            "password": {
                "type": "string",
                "description": "Password for initial access (if key not installed)"
            }
        },
        "required": ["device_id"]
    }
)
```

### 3. Add MCP Tool: `check_ssh_key_status` ✅ EASY

**Purpose:** Check if SSH key is installed and working

**Proposed Tool:**
```python
Tool(
    name="check_ssh_key_status",
    description="Check if SSH key authentication is working for a device",
    inputSchema={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Device identifier (device_id or friendly_name)"
            },
            "username": {
                "type": "string",
                "description": "SSH username (optional, uses device default)"
            }
        },
        "required": ["device_id"]
    }
)
```

### 4. Update `ssh_to_device` Tool ⚠️ ENHANCEMENT

**Current:** Only accepts `device_id`, `command`, `username`

**Proposed Enhancement:**
- Add optional `use_password` parameter (default: False)
- If `use_password=True`, use cached password if available
- Better error messages when authentication fails

---

## Usage Examples

### Current Workflow (Manual Credential Caching)

```python
# 1. Cache credentials programmatically (not via MCP)
from lab_testing.utils.credentials import cache_credential
cache_credential("my-device-id", "root", "my-password")

# 2. Use ssh_to_device (will use cached password)
# Via MCP: ssh_to_device(device_id="my-device-id", command="uptime")
```

### Recommended Workflow (SSH Keys)

```bash
# 1. Generate SSH key (if needed)
ssh-keygen -t ed25519

# 2. Install key on device manually
ssh-copy-id root@192.168.2.18

# 3. Use ssh_to_device (will automatically use key)
# Via MCP: ssh_to_device(device_id="my-device-id", command="uptime")
```

### Future Workflow (With New Tools)

```python
# 1. Check if SSH key works
check_ssh_key_status(device_id="my-device-id")

# 2a. If key not installed, install it
install_ssh_key(device_id="my-device-id", password="initial-password")

# 2b. Or cache password as fallback
cache_device_credentials(device_id="my-device-id", username="root", password="my-password")

# 3. Use ssh_to_device
ssh_to_device(device_id="my-device-id", command="uptime")
```

---

## Security Considerations

### Credential Storage

- **Location**: `~/.cache/ai-lab-testing/credentials.json`
- **Permissions**: 600 (read/write owner only)
- **Format**: JSON with `device_id:credential_type` keys
- **Never committed**: Credentials are in user's home directory, not in repo

### Best Practices

1. **Prefer SSH Keys**: Most secure, no password storage needed
2. **Use Strong Passwords**: If passwords must be used, use strong passwords
3. **Rotate Credentials**: Regularly rotate passwords if used
4. **Review Cache**: Periodically review `~/.cache/ai-lab-testing/credentials.json`
5. **Limit Access**: Ensure credential cache has restrictive permissions (600)

### Credential Cache Format

```json
{
  "device_id:ssh": {
    "username": "root",
    "password": "encrypted-or-plaintext-password"
  },
  "device_id:sudo": {
    "username": "root",
    "password": "sudo-password"
  }
}
```

**Note:** Currently passwords are stored in plaintext. Consider encryption in future.

---

## Troubleshooting

### SSH Key Not Working

1. **Check if key exists:**
   ```bash
   ls -la ~/.ssh/id_*.pub
   ```

2. **Check if key is installed on device:**
   ```bash
   ssh -o BatchMode=yes root@device_ip "echo OK"
   ```

3. **Install key manually:**
   ```bash
   ssh-copy-id root@device_ip
   ```

### Password Authentication Failing

1. **Check if password is cached:**
   ```bash
   cat ~/.cache/ai-lab-testing/credentials.json
   ```

2. **Check if sshpass is installed:**
   ```bash
   which sshpass
   # Install if missing: sudo apt install sshpass
   ```

3. **Cache password manually:**
   ```python
   from lab_testing.utils.credentials import cache_credential
   cache_credential("device-id", "root", "password")
   ```

### Authentication Errors

- **"Permission denied (publickey,password)"**: No SSH key installed and no password cached
- **"sshpass: command not found"**: Install sshpass: `sudo apt install sshpass`
- **"Connection refused"**: Device may be offline or SSH not running
- **"Connection timed out"**: VPN may be disconnected or network unreachable

---

## Next Steps

1. ✅ **Document current authentication flow** - DONE
2. ⏳ **Add `cache_device_credentials` MCP tool** - NEEDED
3. ⏳ **Add `install_ssh_key` MCP tool** - NEEDED
4. ⏳ **Add `check_ssh_key_status` MCP tool** - RECOMMENDED
5. ⏳ **Update `ssh_to_device` with `use_password` parameter** - ENHANCEMENT
6. ⏳ **Add credential encryption** - FUTURE ENHANCEMENT

---

## Related Documentation

- [Security Guide](SECURITY.md) - General security practices
- [VPN Setup Guide](VPN_SETUP.md) - VPN configuration for remote access
- [Device Management](docs/API.md) - Device management tools

