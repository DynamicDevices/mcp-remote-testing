# Factory WireGuard Server: Custom Code Status

## Current Status

**The Proxmox server is running CUSTOM CODE**, not the upstream Foundries code.

## Why Custom Code?

We've made **three critical modifications** that are not in the upstream `foundriesio/factory-wireguard-server` repository:

### 1. Device-to-Device Communication (`--allow-device-to-device`)

**Problem:** By default, Foundries devices can only communicate with the VPN server (`10.42.42.1`), not with each other or client machines.

**Solution:** Added `--allow-device-to-device` flag that:
- Sets `AllowedIPs = 10.42.42.0/24` for all device peers (instead of `/32`)
- Enables full subnet communication for development/debugging

**Code Changes:**
- Added `allow_device_to_device` parameter to `WgServer.__init__()`
- Modified `_gen_conf()` to use subnet `AllowedIPs` when flag is set
- Modified `apply_conf()` to remove peers before applying config (ensures `AllowedIPs` persist)

**Status:** ✅ Implemented locally, needs to be deployed to server

### 2. Client Peer Management (`load_client_peers`, `apply_client_peers`)

**Problem:** Client peers (engineers' machines) are NOT automatically managed by the daemon. They must be manually added using `wg set` commands, and they don't persist across daemon restarts.

**Solution:** Added config file-based client peer management:
- Reads client peers from `/etc/wireguard/factory-clients.conf`
- Applies client peers on daemon startup and after config changes
- Client peers persist across restarts

**Code Changes:**
- Added `load_client_peers()` method
- Added `apply_client_peers()` method
- Integrated into `apply_conf()` and `daemon()` startup

**Config File Format:**
```
# /etc/wireguard/factory-clients.conf
# Format: <public_key> <assigned_ip> [comment]
mzHaZPGowqqzAa5tVFQJs0zoWuDVLppt44HwgdcPXkg= 10.42.42.10 ajlennon
7WR3aejgU53i+/MiJcpdboASPgjLihXApnhHj4SRukE= 10.42.42.11 engineer2
```

**Status:** ✅ Implemented locally, needs to be deployed to server

### 3. AllowedIPs Persistence Fix

**Problem:** WireGuard clears `AllowedIPs` when peers reconnect with active endpoints, causing device-to-device communication to break.

**Solution:** Modified `apply_conf()` to:
- Remove existing device peers before applying config
- Wait 10 seconds for peers to fully disconnect
- Apply config (which adds peers without endpoints initially)
- Explicitly set `AllowedIPs` using `wg set` after interface is up

**Status:** ✅ Implemented locally, needs to be deployed to server

## Repository Structure

The `factory-wireguard-server` directory is a **git submodule** with three remotes:

```
dynamicdevices  -> git@github.com:DynamicDevices/factory-wireguard-server.git (fork)
origin          -> git@github.com:ajlennon/factory-wireguard-server.git (personal fork)
upstream        -> git@github.com:foundriesio/factory-wireguard-server.git (upstream)
```

**Current State:**
- Local code has custom modifications
- DynamicDevices fork may or may not have these changes
- Upstream does NOT have these changes

## What's Running on Proxmox Server?

**Unknown** - Need to check what version is actually running on the server.

To check:
```bash
# SSH to server via Foundries VPN
ssh root@10.42.42.1 -p 5025

# Check daemon code
cat /root/factory-wireguard-server/factory-wireguard.py | grep -E "allow_device_to_device|load_client_peers|apply_client_peers"

# Check daemon command line
systemctl cat factory-vpn-dynamic-devices.service | grep ExecStart
```

## Deployment Status

**Local Code:** ✅ All custom modifications implemented  
**Server Code:** ❓ Unknown - needs verification and deployment

## Should We Contribute Back to Upstream?

### Option 1: Contribute to Upstream (Recommended)

**Pros:**
- Benefits entire Foundries community
- Easier maintenance (upstream updates)
- Standardized solution

**Cons:**
- Requires PR review/approval
- May take time to merge
- May need to justify use cases

**Changes to Contribute:**
1. ✅ `--allow-device-to-device` flag (useful for development)
2. ✅ Client peer management (useful for all factories)
3. ✅ AllowedIPs persistence fix (bug fix)

### Option 2: Maintain Custom Fork

**Pros:**
- Full control
- No upstream dependencies
- Can customize freely

**Cons:**
- Must maintain fork
- Must manually merge upstream updates
- Duplicate effort

**Recommendation:** **Contribute to upstream** - These are useful features that benefit everyone.

## Next Steps

1. **Verify Server Code:**
   - Check what's actually running on Proxmox server
   - Compare with local custom code

2. **Deploy Custom Code:**
   - Copy updated `factory-wireguard.py` to server
   - Restart daemon
   - Test functionality

3. **Decide on Upstream Contribution:**
   - Create PR for `--allow-device-to-device` flag
   - Create PR for client peer management
   - Create PR for AllowedIPs persistence fix

4. **Document Custom Changes:**
   - Keep this document updated
   - Document any additional customizations

## Summary

**Why Custom Code?**
- Upstream doesn't support device-to-device communication
- Upstream doesn't manage client peers
- Upstream has AllowedIPs persistence issues

**What We've Added:**
- Device-to-device communication flag
- Client peer config file management
- AllowedIPs persistence fixes

**Status:**
- ✅ Code implemented locally
- ❓ Server status unknown (needs check)
- ⏳ Deployment pending
- ⏳ Upstream contribution pending

