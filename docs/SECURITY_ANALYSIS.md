# Security Analysis of Custom Changes

## Overview

This document analyzes the security implications of our three custom changes to the Foundries WireGuard server.

## Change 1: Device-to-Device Communication (`--allow-device-to-device`)

### Default Behavior (Upstream)

**Upstream Security Model:**
```
Device A (10.42.42.2) ──┐
                        ├──► Server (10.42.42.1) ◄── Device B (10.42.42.3)
                        └──► Server (10.42.42.1)
```

- Each device can **only** communicate with the server (`10.42.42.1`)
- Devices **cannot** communicate with each other
- Devices **cannot** communicate with client machines
- **Isolation:** Each device is isolated from all other devices and clients

**AllowedIPs:** `{device.ip}/32` (single IP, e.g., `10.42.42.2/32`)

**Security Posture:** ✅ **Highly Secure** - Maximum isolation

### Our Change (When Flag Enabled)

**Our Security Model (with `--allow-device-to-device`):**
```
Device A (10.42.42.2) ──┐
                        ├──► Server (10.42.42.1) ◄── Device B (10.42.42.3)
                        │                              │
                        └──────────────────────────────┘
                        │
                        └──► Client (10.42.42.10)
```

- All devices can communicate with **each other** (`10.42.42.0/24`)
- All devices can communicate with **client machines**
- All clients can communicate with **all devices**
- **Isolation:** None - full mesh network

**AllowedIPs:** `10.42.42.0/24` (entire subnet)

**Security Posture:** ⚠️ **Less Secure** - No isolation between devices

### Security Impact Analysis

#### ✅ **Default Behavior Preserved**

**Critical:** Our change **preserves upstream default behavior** when flag is NOT set:

```python
if self.allow_device_to_device:
    allowed_ips = "10.42.42.0/24"  # Full subnet (less secure)
else:
    allowed_ips = device.ip  # Single IP (upstream default, secure)
```

**When flag is NOT set:**
- ✅ Same security as upstream
- ✅ Devices isolated from each other
- ✅ Devices isolated from clients
- ✅ Maximum security posture

**When flag IS set:**
- ⚠️ Devices can communicate with each other
- ⚠️ Devices can communicate with clients
- ⚠️ Reduced isolation

#### Security Risks When Flag Enabled

1. **Device-to-Device Communication**
   - **Risk:** Compromised device can attack other devices
   - **Mitigation:** Devices should be trusted (they're in your factory)
   - **Use Case:** Development/debugging requires device-to-device communication

2. **Client-to-Device Communication**
   - **Risk:** Compromised client can attack devices
   - **Mitigation:** Client authentication (WireGuard keys), access control
   - **Use Case:** Engineers need to access devices for development

3. **Lateral Movement**
   - **Risk:** Attacker on one device can move to other devices
   - **Mitigation:** Device security hardening, monitoring
   - **Use Case:** Development environment, not production

#### When to Use Each Mode

**Use Default (Isolated) Mode When:**
- ✅ Production deployments
- ✅ Security-critical environments
- ✅ Devices should not communicate with each other
- ✅ Maximum isolation required

**Use Device-to-Device Mode When:**
- ✅ Development/debugging environments
- ✅ Device-to-device communication required
- ✅ Testing scenarios
- ✅ Trusted device network

---

## Change 2: Client Peer Management (`load_client_peers`, `apply_client_peers`)

### Security Impact: ✅ **NEUTRAL** (Operational Change)

**What Changed:**
- Client peers now managed via config file instead of manual `wg set` commands
- Client peers persist across daemon restarts

**Security Implications:**
- ✅ **No change** to security model
- ✅ **Same authentication** (WireGuard public keys)
- ✅ **Same access control** (AllowedIPs still apply)
- ✅ **More secure** (config file can be version-controlled, audited)

**Default Behavior:**
- ✅ **Preserved** - If config file doesn't exist, no client peers are added
- ✅ **Backward compatible** - Manual `wg set` commands still work

**Security Benefits:**
- ✅ Config file can be version-controlled
- ✅ Config file can be audited
- ✅ Easier to manage access (add/remove clients)
- ✅ Persistence prevents accidental loss of access

**Security Considerations:**
- ⚠️ Config file must be protected (`chmod 600`)
- ⚠️ Config file should be backed up
- ⚠️ Access to config file = ability to add clients

**Verdict:** ✅ **No security degradation** - Operational improvement only

---

## Change 3: AllowedIPs Persistence Fix

### Security Impact: ✅ **POSITIVE** (Bug Fix)

**What Changed:**
- Fixed bug where `AllowedIPs` get cleared on device reconnection
- Ensures `AllowedIPs` persist as configured

**Security Implications:**
- ✅ **Improves security** - Ensures configured `AllowedIPs` are actually applied
- ✅ **Prevents accidental exposure** - Without fix, devices might have broader access than intended
- ✅ **Maintains intended security posture** - Config matches runtime behavior

**Default Behavior:**
- ✅ **Preserved** - Same behavior, just more reliable
- ✅ **Fixes upstream bug** - Upstream had security issue (AllowedIPs not persisting)

**Security Benefits:**
- ✅ Config file `AllowedIPs` actually enforced
- ✅ No accidental broader access due to bug
- ✅ Predictable security posture

**Verdict:** ✅ **Security improvement** - Fixes upstream bug

---

## Summary Table

| Change | Default Behavior | Security Impact | When Flag Enabled |
|--------|----------------|-----------------|-------------------|
| **Device-to-Device** | ✅ Preserved (isolated) | ⚠️ Reduced isolation | Devices can communicate |
| **Client Peer Mgmt** | ✅ Preserved (no change) | ✅ Neutral (operational) | N/A (always enabled) |
| **AllowedIPs Fix** | ✅ Preserved (same behavior) | ✅ Positive (bug fix) | N/A (always enabled) |

---

## Security Recommendations

### 1. Use Default Mode for Production

**Recommendation:** Use default (isolated) mode for production deployments:

```bash
# Production: NO flag (default, secure)
./factory-wireguard.py --oauthcreds ... --factory ... daemon

# Development: WITH flag (less secure, but needed)
./factory-wireguard.py --oauthcreds ... --factory ... --allow-device-to-device daemon
```

### 2. Protect Client Peer Config File

**Recommendation:** Secure the client peer config file:

```bash
# Set restrictive permissions
chmod 600 /etc/wireguard/factory-clients.conf
chown root:root /etc/wireguard/factory-clients.conf

# Version control (read-only access)
# Audit regularly
```

### 3. Monitor Device-to-Device Traffic

**Recommendation:** When using `--allow-device-to-device`:
- Monitor network traffic
- Log device-to-device communications
- Use firewall rules if needed
- Consider device security hardening

### 4. Document Security Posture

**Recommendation:** Document which mode is used:
- Production deployments: Default (isolated)
- Development deployments: Device-to-device enabled
- Document rationale for each environment

---

## Comparison: Upstream vs Our Code

### Default Behavior (Flag NOT Set)

| Aspect | Upstream | Our Code | Match? |
|--------|----------|----------|--------|
| Device AllowedIPs | `{device.ip}/32` | `{device.ip}/32` | ✅ Yes |
| Device isolation | Full isolation | Full isolation | ✅ Yes |
| Client peer mgmt | Manual only | Config file + manual | ✅ Compatible |
| AllowedIPs persistence | Buggy | Fixed | ✅ Improved |

### With Flag Enabled

| Aspect | Upstream | Our Code | Match? |
|--------|----------|----------|--------|
| Device AllowedIPs | N/A (not supported) | `10.42.42.0/24` | N/A |
| Device isolation | N/A | No isolation | N/A |
| Use case | N/A | Development | N/A |

---

## Conclusion

### ✅ **Default Behavior Preserved**

**Critical Finding:** Our changes **preserve upstream default security behavior** when the flag is NOT set:

- ✅ Same `AllowedIPs` (`{device.ip}/32`)
- ✅ Same device isolation
- ✅ Same security posture
- ✅ Backward compatible

### ⚠️ **Security Trade-off When Flag Enabled**

**When `--allow-device-to-device` is enabled:**
- ⚠️ Reduced isolation (devices can communicate)
- ⚠️ Appropriate for development/debugging
- ⚠️ **NOT recommended for production**

### ✅ **Operational Improvements**

- ✅ Client peer management: No security impact, operational improvement
- ✅ AllowedIPs persistence fix: Security improvement (fixes bug)

### 🎯 **Recommendation**

**Use default mode (no flag) for:**
- Production deployments
- Security-critical environments
- Maximum isolation required

**Use device-to-device mode (with flag) for:**
- Development/debugging
- Testing scenarios
- When device-to-device communication is required

**Our changes are secure and preserve default behavior.**

