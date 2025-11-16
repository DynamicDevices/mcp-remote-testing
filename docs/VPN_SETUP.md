# WireGuard VPN Setup Guide

This guide helps you set up WireGuard VPN for use with the MCP Remote Testing server.

## Quick Start

The MCP server can automatically detect WireGuard configurations in common locations. If you already have a WireGuard config, you may not need to do anything!

### Automatic Detection

The server searches for VPN configs in this order:

1. **Environment variable**: `VPN_CONFIG_PATH` (if set)
2. **Secrets directory**: `{LAB_TESTING_ROOT}/secrets/wg0.conf` (or `wireguard.conf`, `vpn.conf`)
3. **User config**: `~/.config/wireguard/*.conf`
4. **System config**: `/etc/wireguard/*.conf`

### Using Environment Variable

If your config is in a non-standard location:

```bash
export VPN_CONFIG_PATH=/path/to/your/wg0.conf
```

Or in Cursor MCP config:

```json
{
  "mcpServers": {
    "ai-lab-testing": {
      "command": "python3.10",
      "args": ["/path/to/lab_testing/server.py"],
      "env": {
        "LAB_TESTING_ROOT": "/path/to/ai-lab-testing",
        "VPN_CONFIG_PATH": "/path/to/your/wg0.conf"
      }
    }
  }
}
```

## Installation

### Install WireGuard Tools

**Debian/Ubuntu:**
```bash
sudo apt update
sudo apt install wireguard-tools
```

**RHEL/CentOS:**
```bash
sudo yum install wireguard-tools
```

**Arch Linux:**
```bash
sudo pacman -S wireguard-tools
```

**macOS:**
```bash
brew install wireguard-tools
```

### Optional: NetworkManager Support

For connecting without root privileges:

**Debian/Ubuntu:**
```bash
sudo apt install network-manager network-manager-wireguard
```

## Setup Methods

### Method 1: Using MCP Tools (Recommended)

The MCP server provides tools to help you set up WireGuard:

1. **Check if WireGuard is installed:**
   - Use tool: `check_wireguard_installed`

2. **Get setup instructions:**
   - Use tool: `vpn_setup_instructions`

3. **Create a config template:**
   - Use tool: `create_vpn_config_template`
   - This creates a template at `{LAB_TESTING_ROOT}/secrets/wg0.conf`

4. **Edit the template** with your VPN server details:
   - Private key (generate with: `wg genkey`)
   - Server public key
   - Server endpoint
   - Allowed IPs (lab network subnets)

5. **Import into NetworkManager (optional):**
   - Use tool: `setup_networkmanager_vpn`
   - This allows connecting without root

### Method 2: Manual Setup

#### Step 1: Generate Key Pair

```bash
# Generate private key
wg genkey | tee privatekey | wg pubkey > publickey

# View your public key (share with VPN server admin)
cat publickey
```

#### Step 2: Create Configuration File

Create `{LAB_TESTING_ROOT}/secrets/wg0.conf`:

```ini
[Interface]
# Your private key (from Step 1)
PrivateKey = YOUR_PRIVATE_KEY_HERE

# Your local IP address on the VPN network
Address = 10.0.0.X/24

# Optional: DNS servers
# DNS = 8.8.8.8

[Peer]
# Server's public key (from your VPN administrator)
PublicKey = SERVER_PUBLIC_KEY_HERE

# Server endpoint
Endpoint = vpn.example.com:51820

# Allowed IPs (routes to send through VPN)
# Use specific subnets for lab network only:
AllowedIPs = 192.168.0.0/16, 10.0.0.0/8

# Keep connection alive
PersistentKeepalive = 25
```

**Important:** Replace:
- `YOUR_PRIVATE_KEY_HERE` with your private key
- `SERVER_PUBLIC_KEY_HERE` with the server's public key
- `vpn.example.com:51820` with your VPN server address
- `10.0.0.X/24` with your assigned VPN IP
- `AllowedIPs` with the lab network subnets you need access to

#### Step 3: Set Secure Permissions

```bash
chmod 600 {LAB_TESTING_ROOT}/secrets/wg0.conf
```

#### Step 4: Test Connection

**Using wg-quick (requires root):**
```bash
sudo wg-quick up {LAB_TESTING_ROOT}/secrets/wg0.conf
```

**Using NetworkManager (no root needed):**
```bash
nmcli connection import type wireguard file {LAB_TESTING_ROOT}/secrets/wg0.conf
nmcli connection up wg0
```

## NetworkManager Integration (Recommended)

NetworkManager allows connecting to WireGuard VPN without root privileges, which is safer and more convenient.

### Import Config

```bash
nmcli connection import type wireguard file /path/to/wg0.conf
```

### Connect/Disconnect

```bash
# Connect
nmcli connection up wg0

# Disconnect
nmcli connection down wg0

# Check status
nmcli connection show --active
```

The MCP server will automatically detect and use NetworkManager connections if available.

## Configuration Examples

### Lab Network Only (Recommended)

Only route lab network traffic through VPN:

```ini
AllowedIPs = 192.168.0.0/16, 10.0.0.0/8
```

### All Traffic

Route all internet traffic through VPN:

```ini
AllowedIPs = 0.0.0.0/0
```

### Multiple Peers

If you have multiple VPN servers:

```ini
[Interface]
PrivateKey = YOUR_PRIVATE_KEY
Address = 10.0.0.2/24

[Peer]
PublicKey = SERVER1_PUBLIC_KEY
Endpoint = server1.example.com:51820
AllowedIPs = 192.168.1.0/24

[Peer]
PublicKey = SERVER2_PUBLIC_KEY
Endpoint = server2.example.com:51820
AllowedIPs = 192.168.2.0/24
```

## Troubleshooting

### VPN Config Not Found

1. Check if config exists: Use `list_vpn_configs` tool
2. Set `VPN_CONFIG_PATH` environment variable
3. Ensure config file has `.conf` extension
4. Check file permissions (should be 600)

### Connection Fails

1. **Check WireGuard installation:**
   ```bash
   wg --version
   ```

2. **Test manually:**
   ```bash
   sudo wg-quick up /path/to/wg0.conf
   ```

3. **Check logs:**
   ```bash
   sudo journalctl -u wg-quick@wg0
   ```

4. **Verify server details:**
   - Public key matches server
   - Endpoint is reachable
   - Port is not blocked by firewall

### NetworkManager Issues

1. **Check if NetworkManager supports WireGuard:**
   ```bash
   nmcli --version
   ```

2. **Re-import config:**
   ```bash
   nmcli connection delete wg0  # Remove old connection
   nmcli connection import type wireguard file /path/to/wg0.conf
   ```

### Permission Issues

- Config file should be readable by your user: `chmod 600 wg0.conf`
- For wg-quick, you need sudo access
- NetworkManager doesn't require root for user connections

## Security Best Practices

1. **Keep private keys secure:**
   - Never share your private key
   - Use `chmod 600` on config files
   - Don't commit configs to git

2. **Use NetworkManager when possible:**
   - Avoids need for root/sudo
   - Better integration with system

3. **Limit AllowedIPs:**
   - Only route necessary subnets through VPN
   - Reduces attack surface

4. **Regular key rotation:**
   - Periodically regenerate keys
   - Update server configuration

## Getting Help

- Use MCP tool: `vpn_setup_instructions` for detailed help
- Check WireGuard documentation: https://www.wireguard.com/
- Check server logs: `~/.cache/ai-lab-testing/logs/`

