# [WIP] Add device-to-device communication, client peer management, and AllowedIPs persistence fix

## Status: Work in Progress

This PR is currently being tested and verified. Please do not merge until marked as ready.

## Summary

This PR adds three enhancements to the Foundries WireGuard server:

1. **Device-to-device communication** (`--allow-device-to-device` flag)
2. **Client peer management** (config file support)
3. **AllowedIPs persistence fix** (bug fix)

All changes are **backward compatible** and **preserve default security behavior**.

## Changes

### 1. Device-to-Device Communication (`--allow-device-to-device`)

**Problem:** Upstream only allows devices to communicate with the server (`10.42.42.1`), not with each other or client machines. This is restrictive for development/debugging scenarios.

**Solution:** Add opt-in `--allow-device-to-device` flag that sets `AllowedIPs = 10.42.42.0/24` for all device peers, enabling full subnet communication.

**Code Changes:**
- Add `allow_device_to_device` parameter to `WgServer.__init__()`
- Add `--allow-device-to-device` CLI argument
- Modify `_gen_conf()` to conditionally set subnet `AllowedIPs`

**Default Behavior:** ✅ **Preserved** - When flag is NOT set, behavior is identical to upstream (devices isolated).

### 2. Client Peer Management (`load_client_peers`, `apply_client_peers`)

**Problem:** Upstream has no support for managing client peers (engineers' machines). Client peers must be manually added using `wg set` commands and do not persist across daemon restarts.

**Solution:** Add config file support (`/etc/wireguard/factory-clients.conf`) for persistent client peer management.

**Code Changes:**
- Add `load_client_peers()` method to read from config file
- Add `apply_client_peers()` method to apply client peers to WireGuard interface
- Integrate into `apply_conf()` and daemon startup

**Config File Format:**
```
# /etc/wireguard/factory-clients.conf
# Format: <public_key> <assigned_ip> [comment]
mzHaZPGowqqzAa5tVFQJs0zoWuDVLppt44HwgdcPXkg= 10.42.42.10 ajlennon
7WR3aejgU53i+/MiJcpdboASPgjLihXApnhHj4SRukE= 10.42.42.11 engineer2
```

**Default Behavior:** ✅ **Preserved** - If config file doesn't exist, no client peers are added (same as upstream).

### 3. AllowedIPs Persistence Fix

**Problem:** Upstream has a bug where `AllowedIPs` get cleared when devices reconnect with active endpoints. This causes device-to-device communication to break even when configured.

**Solution:** Remove existing device peers before applying config, wait for disconnection, then explicitly set `AllowedIPs` after interface is up.

**Code Changes:**
- Modify `apply_conf()` to remove device peers before applying config (when `allow_device_to_device` is enabled)
- Wait 10 seconds for peers to fully disconnect
- Explicitly set `AllowedIPs` using `wg set` after interface is up

**Default Behavior:** ✅ **Preserved** - Same behavior, just more reliable (fixes upstream bug).

## Security Analysis

### ✅ Default Behavior Preserved

**Critical:** When `--allow-device-to-device` flag is **NOT set**, our code behaves **identically** to upstream:

- Same `AllowedIPs = {device.ip}/32` (single IP)
- Same device isolation (devices cannot communicate)
- Same security posture

### ⚠️ Security Impact When Flag Enabled

**When `--allow-device-to-device` IS set:**
- Devices can communicate with each other (`10.42.42.0/24`)
- Devices can communicate with client machines
- Reduced isolation (appropriate for development/debugging)

**Recommendation:**
- **Production:** Use default mode (no flag) for maximum security
- **Development:** Use device-to-device mode (with flag) when needed

### Security Impact Summary

| Change | Default Behavior | Security Impact | When Flag Enabled |
|--------|----------------|-----------------|-------------------|
| **Device-to-Device** | ✅ Preserved (isolated) | ⚠️ Reduced isolation | Devices can communicate |
| **Client Peer Mgmt** | ✅ Preserved (no change) | ✅ Neutral (operational) | N/A (always enabled) |
| **AllowedIPs Fix** | ✅ Preserved (same behavior) | ✅ Positive (bug fix) | N/A (always enabled) |

**Full security analysis:** See `docs/SECURITY_ANALYSIS.md`

## Verification

All changes have been verified against upstream code:

1. ✅ **Device-to-device communication:** Upstream does NOT support this (verified)
2. ✅ **Client peer management:** Upstream has NO support (verified)
3. ✅ **AllowedIPs persistence:** Upstream has the bug (verified)

**Verification details:** See `docs/UPSTREAM_CODE_VERIFICATION.md`

## Code Size

- **Upstream:** 668 lines
- **Our Code:** 802 lines
- **Difference:** +134 lines (20% increase)

All additions are minimal and focused on the three enhancements above.

## Testing Status

- ✅ Code compiles
- ✅ Syntax check passed
- ⏳ Runtime testing in progress
- ⏳ Integration testing pending

## Use Cases

### Production Deployment (Default Mode)
```bash
# Maximum security - devices isolated
./factory-wireguard.py --oauthcreds ... --factory ... daemon
```

### Development/Debugging (Device-to-Device Mode)
```bash
# Full subnet communication for development
./factory-wireguard.py --oauthcreds ... --factory ... --allow-device-to-device daemon
```

## Documentation

- `docs/SECURITY_ANALYSIS.md` - Comprehensive security impact analysis
- `docs/UPSTREAM_CODE_VERIFICATION.md` - Verification that all changes are needed
- `docs/FACTORY_WIREGUARD_SERVER_CUSTOM_CODE.md` - Custom code documentation

## Related Issues

- Addresses need for device-to-device communication in development environments
- Fixes upstream bug where AllowedIPs don't persist
- Improves operational efficiency with client peer management

## Checklist

- [x] Code changes implemented
- [x] Security analysis completed
- [x] Upstream verification completed
- [x] Documentation added
- [ ] Runtime testing completed
- [ ] Integration testing completed
- [ ] Ready for review

---

**Note:** This PR is marked as WIP until testing is complete. Please do not merge until marked as ready.

---

## Generated by Cursor.AI

This PR and its changes were generated by Cursor.AI for user ajlennon (Alex J Lennon, ajlennon@dynamicdevices.co.uk).

All changes have been:
- ✅ Verified against upstream code
- ✅ Security analyzed
- ✅ Documented with reasoning
- ⏳ Testing in progress

