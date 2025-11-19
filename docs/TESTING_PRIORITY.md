# MCP Tools Testing Priority List

**Purpose:** Remote hardware testing for embedded Linux and hardware development, including power monitoring, VPN access, and device management.

**Core Mission:** Make remote embedded hardware development easy and accessible for engineers. This project prioritizes ease of use, helpful guidance, and best practices to enable seamless remote development workflows.

**Last Updated:** 2025-11-18

## Testing Status Legend

- ✅ **Tested & Working** - Tool has been tested and works correctly
- ⚠️ **Partially Tested** - Tool works but has known limitations or edge cases
- ❌ **Not Tested** - Tool exists but hasn't been tested yet
- 🚧 **Needs Work** - Tool has issues that need to be fixed
- 🔄 **In Progress** - Currently being tested
- 📝 **Documentation Needed** - Tool works but needs better docs
- 🗑️ **Consider Removing** - Tool may not be needed or is redundant

---

## Priority 1: Core Device Discovery & Connectivity (CRITICAL)

**Goal:** Ensure we can discover, identify, and connect to devices on remote networks via VPN.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `list_devices` | ✅ | P1 | Core tool, tested | - List all devices<br>- Filter by type/status<br>- Search functionality<br>- Force refresh<br>- Sorting/limiting |
| `test_device` | ✅ | P1 | Basic connectivity | - Ping test<br>- SSH test<br>- Error handling |
| `ssh_to_device` | ✅ | P1 | Core SSH execution | - Execute commands<br>- Handle errors<br>- Timeout handling |
| `create_network_map` | ✅ | P1 | Visual network overview | - Quick mode<br>- Full scan<br>- PNG rendering<br>- Device relationships |

**Testing Focus:**
- [ ] Test with VPN connected/disconnected
- [ ] Test with DHCP devices (IP changes)
- [ ] Test device discovery on remote network
- [ ] Test error handling (device offline, SSH failures)
- [ ] Test caching behavior (force_refresh)

### File Transfer Tools (CRITICAL for Remote Development)

**Goal:** Enable building and deploying applications to remote devices efficiently.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `copy_file_to_device` | ✅ | P1 | Single file copy | - File transfer<br>- Multiplexed SSH<br>- Compression<br>- Permission preservation |
| `copy_file_from_device` | ✅ | P1 | File download | - File download<br>- Multiplexed SSH<br>- Compression<br>- Content verification |
| `sync_directory_to_device` | ⚠️ | P1 | Directory sync | - Requires rsync on device<br>- Multiple files<br>- Exclude patterns<br>- Delete option |
| `copy_files_to_device_parallel` | ✅ | P1 | Parallel transfers | - Multiple files<br>- Shared SSH connection<br>- Concurrent transfers<br>- Error handling |

**Testing Focus:**
- ✅ Test single file copy (to/from device) - **DONE** (see docs/P1_FILE_TRANSFER_TESTING.md)
- ✅ Test parallel file transfers - **DONE**
- ⚠️ Test directory sync (requires rsync on device) - **PARTIAL** (rsync check added)
- ⚠️ Test with large files (>100MB) - **DONE** (see docs/P1_FILE_TRANSFER_SCALE_TESTING.md) - Timeout issue noted (60s too short for slow links)
- ✅ Test with many files (100+ files) - **DONE** (see docs/P1_FILE_TRANSFER_SCALE_TESTING.md) - Successfully tested 100 and 200 files
- ✅ Test error handling (device offline, disk full, permission denied) - **DONE** (see docs/P1_FILE_TRANSFER_ERROR_HANDLING_TESTING.md)
- ✅ Test compression effectiveness on slow links - **DONE** (see docs/P1_FILE_TRANSFER_SCALE_TESTING.md) - Mixed file types tested successfully
- ✅ Test multiplexed SSH connection reuse - **DONE** (4.33x speedup confirmed, see docs/P1_FILE_TRANSFER_ERROR_HANDLING_TESTING.md)

**Known Limitations:**
- `sync_directory_to_device` requires rsync installed on remote device
- Many embedded Linux devices don't have rsync by default
- Workaround: Use `copy_files_to_device_parallel` for multiple files
- Large file transfers (>50MB) may timeout on slow VPN links (60s timeout)
- Workaround: Split large files or increase timeout (future enhancement: dynamic timeout)

---

## Priority 2: VPN Management (CRITICAL)

**Goal:** Ensure reliable VPN connectivity to remote test networks. Support both standard WireGuard and Foundries.io WireGuard.

### Standard WireGuard VPN

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `vpn_status` | ✅ | P2 | Check connection | - Connected state<br>- Disconnected state<br>- Error states |
| `connect_vpn` | ✅ | P2 | Connect to VPN | - Auto-detect config<br>- Manual config<br>- Error handling |
| `disconnect_vpn` | ✅ | P2 | Disconnect VPN | - Graceful disconnect<br>- Error handling |
| `vpn_setup_instructions` | ✅ | P2 | Setup help | - New developer onboarding<br>- Config template generation |
| `check_wireguard_installed` | ✅ | P2 | Check prerequisites | - Installation check<br>- Missing tools detection |
| `list_vpn_configs` | ✅ | P2 | List available configs | - Multiple configs<br>- Config selection |
| `create_vpn_config_template` | ✅ | P2 | Template generation | - Template creation<br>- Config validation |
| `setup_networkmanager_vpn` | ⚠️ | P2 | NetworkManager integration | - Import config<br>- Non-root access |
| `vpn_statistics` | ❌ | P2 | VPN stats | - Transfer data<br>- Latency<br>- Handshakes |

**Testing Focus:**
- [ ] Test VPN connection/disconnection workflow
- [ ] Test with multiple VPN configs
- [ ] Test NetworkManager integration (non-root)
- [ ] Test VPN statistics collection
- [ ] Test error handling (config not found, connection failed)
- [ ] **Documentation:** Create comprehensive VPN setup guide for new developers

### Foundries.io WireGuard VPN (✅ IMPLEMENTED & TESTED)

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `foundries_vpn_status` | ✅ | P2 | Check Foundries VPN | - Connection status<br>- Server connectivity<br>- NetworkManager detection |
| `get_foundries_vpn_server_config` | ✅ | P2 | Get server config via API | - Server endpoint<br>- Public key<br>- Address range |
| `check_foundries_vpn_client_config` | ✅ | P2 | Validate client config | - Config file validation<br>- Required fields check |
| `generate_foundries_vpn_client_config_template` | ✅ | P2 | Generate config template | - Template with server details<br>- Auto-fill server info |
| `setup_foundries_vpn` | ✅ | P2 | Automated setup | - End-to-end automation<br>- Prerequisite checking<br>- Step tracking |
| `verify_foundries_vpn_connection` | ✅ | P2 | Verify connectivity | - Server ping test<br>- Routing check |
| `connect_foundries_vpn` | ✅ | P2 | Connect via Foundries | - Server-based VPN<br>- Device access<br>- Auto-config detection |
| `list_foundries_devices` | ✅ | P2 | List Foundries devices | - Remote device discovery<br>- Device registration<br>- WireGuard status |
| `enable_foundries_vpn_device` | ✅ | P2 | Enable VPN on device | - Device VPN enable<br>- OTA update trigger |
| `disable_foundries_vpn_device` | ✅ | P2 | Disable VPN on device | - Device VPN disable<br>- OTA update trigger |

**Implementation Status:**
- [x] Research Foundries.io WireGuard VPN mechanism ✅
- [x] Understand difference from standard WireGuard ✅
- [x] Implement Foundries VPN connection tools ✅
- [x] Test with Foundries.io remote devices ✅ (see test_mcp_foundries_vpn_automation.py)
- [x] Document Foundries VPN setup process ✅ (see docs/FOUNDRIES_VPN_SETUP.md, docs/FOUNDRIES_VPN_CLIENT_SETUP.md)

**Testing Status:**
- ✅ Automated setup workflow tested
- ✅ Config template generation tested
- ✅ Server config retrieval tested
- ✅ Client config validation tested
- ✅ Real device testing complete (see docs/P1_FOUNDRIES_VPN_DEVICE_TESTING.md)
  - ✅ VPN status check
  - ✅ Server config retrieval
  - ✅ Device listing (4 devices found)
  - ✅ VPN connection verification
  - ✅ Enable/disable VPN functions verified
  - ⚠️ SSH access via VPN IP pending (requires device IP addresses)

---

## Priority 3: Power Monitoring (CRITICAL for Hardware Development)

**Goal:** Accurate power measurement and analysis for embedded Linux power optimization.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `start_power_monitoring` | ⚠️ | P3 | DMM/Tasmota support | - DMM monitoring<br>- Tasmota monitoring<br>- Duration/timeout<br>- Test naming |
| `get_power_logs` | ⚠️ | P3 | Retrieve logs | - Log listing<br>- Filter by test name<br>- Log format |
| `analyze_power_logs` | ❌ | P3 | Power analysis | - Low power detection<br>- Suspend/resume detection<br>- Power profiling |
| `monitor_low_power` | ❌ | P3 | Low power monitoring | - Threshold detection<br>- Duration monitoring<br>- Alert generation |
| `compare_power_profiles` | ❌ | P3 | Profile comparison | - Multiple test runs<br>- Power consumption trends<br>- Regression detection |
| `tasmota_control` (energy) | ✅ | P3 | Tasmota power query | - Energy consumption<br>- Power state |

**Testing Focus:**
- [ ] Test DMM power monitoring (SCPI commands)
- [ ] Test Tasmota power monitoring (energy monitoring)
- [ ] Test power log collection and storage
- [ ] Test power analysis algorithms
- [ ] Test low power detection (suspend/resume)
- [ ] Test power profile comparison
- [ ] Validate power measurement accuracy
- [ ] Test with multiple devices simultaneously

**Hardware Requirements:**
- [ ] DMM with SCPI support (e.g., Keysight DMM)
- [ ] Tasmota devices with energy monitoring enabled
- [ ] Test devices (embedded Linux boards)

---

## Priority 4: Device Control & Power Management

**Goal:** Control devices remotely, including power cycling and Tasmota control.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `tasmota_control` | ✅ | P4 | Power switch control | - ON/OFF/Toggle<br>- Status check<br>- Energy query |
| `list_tasmota_devices` | ✅ | P4 | List power switches | - Device listing<br>- Power relationships |
| `power_cycle_device` | ⚠️ | P4 | Power cycle via Tasmota | - Power off/on cycle<br>- Timing control<br>- Error handling |
| `list_test_equipment` | ✅ | P4 | List test equipment | - DMM discovery<br>- Oscilloscope discovery |
| `query_test_equipment` | ⚠️ | P4 | SCPI commands | - Device identification<br>- Measurement commands<br>- Error handling |

**Testing Focus:**
- [ ] Test Tasmota power control (ON/OFF/Toggle)
- [ ] Test power cycling workflow
- [ ] Test SCPI command execution
- [ ] Test error handling (device offline, command failed)
- [ ] Test power relationships (which device is powered by which switch)

---

## Priority 5: Device Verification & Identity (Important for DHCP)

**Goal:** Handle DHCP environments where device IPs may change.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `verify_device_identity` | ⚠️ | P5 | Verify device at IP | - Hostname check<br>- Unique ID check<br>- IP update |
| `verify_device_by_ip` | ⚠️ | P5 | Identify device by IP | - Unknown IP discovery<br>- Device identification |
| `update_device_ip` | ⚠️ | P5 | Update IP in config | - IP change detection<br>- Config update |
| `update_device_friendly_name` | ❌ | P5 | Update friendly name | - Name caching<br>- Name persistence |

**Testing Focus:**
- [ ] Test device identity verification
- [ ] Test IP address updates (DHCP)
- [ ] Test device discovery by IP
- [ ] Test friendly name updates
- [ ] Test with devices that change IPs frequently

---

## Priority 6: System Information & Status

**Goal:** Get device status, firmware, and system information.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `get_system_status` | ⚠️ | P6 | System info | - Uptime<br>- Load<br>- Memory<br>- Disk<br>- Kernel version |
| `get_firmware_version` | ⚠️ | P6 | Firmware info | - OS release info<br>- Version parsing |
| `list_containers` | ❌ | P6 | Docker containers | - Container listing<br>- Status check |
| `deploy_container` | ❌ | P6 | Container deployment | - Container update<br>- Image pull<br>- Error handling |

**Testing Focus:**
- [ ] Test system status collection
- [ ] Test firmware version parsing
- [ ] Test Docker container management
- [ ] Test error handling (device offline, SSH failures)

---

## Priority 7: OTA Updates & Foundries.io Integration

**Goal:** Manage OTA updates for Foundries.io devices.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `check_ota_status` | ❌ | P7 | OTA status check | - Update status<br>- Target version<br>- Update history |
| `trigger_ota_update` | ❌ | P7 | Trigger OTA update | - Update trigger<br>- Target selection<br>- Status monitoring |

**Testing Focus:**
- [ ] Test OTA status checking
- [ ] Test OTA update triggering
- [ ] Test with Foundries.io devices
- [ ] Test update status monitoring
- [ ] **Integration:** Test with Foundries VPN (when implemented)

---

## Priority 8: Batch Operations & Regression Testing

**Goal:** Test multiple devices in parallel for regression testing.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `batch_operation` | ❌ | P8 | Parallel operations | - Multiple devices<br>- Operation types<br>- Error handling |
| `regression_test` | ❌ | P8 | Regression suite | - Test sequence<br>- Device groups<br>- Results aggregation |
| `get_device_groups` | ❌ | P8 | Device grouping | - Group by location<br>- Group by function<br>- Group by power circuit |

**Testing Focus:**
- [ ] Test parallel operations
- [ ] Test regression test sequences
- [ ] Test device grouping
- [ ] Test error handling (some devices fail)
- [ ] Test results aggregation

---

## Priority 9: Help & Documentation

**Goal:** Ensure users can get help and understand tool usage.

| Tool | Status | Priority | Notes | Test Scenarios |
|------|--------|----------|-------|----------------|
| `help` | ✅ | P9 | Help documentation | - Tool descriptions<br>- Usage examples<br>- Workflows |

**Testing Focus:**
- [ ] Test help content accuracy
- [ ] Test help content completeness
- [ ] Update help with new tools/features

---

## Testing Workflow Recommendations

### 1. **New Developer Onboarding Test**
1. ✅ VPN setup (`vpn_setup_instructions`, `create_vpn_config_template`)
2. ✅ VPN connection (`connect_vpn`, `vpn_status`)
3. ✅ Device discovery (`list_devices`)
4. ✅ Device connectivity (`test_device`, `ssh_to_device`)

### 2. **Power Monitoring Test**
1. ✅ List test equipment (`list_test_equipment`)
2. ⚠️ Start power monitoring (`start_power_monitoring`)
3. ⚠️ Get power logs (`get_power_logs`)
4. ❌ Analyze power logs (`analyze_power_logs`)
5. ❌ Monitor low power (`monitor_low_power`)

### 3. **Device Control Test**
1. ✅ List Tasmota devices (`list_tasmota_devices`)
2. ✅ Control Tasmota (`tasmota_control`)
3. ⚠️ Power cycle device (`power_cycle_device`)
4. ⚠️ Query test equipment (`query_test_equipment`)

### 4. **DHCP Environment Test**
1. ⚠️ Verify device identity (`verify_device_identity`)
2. ⚠️ Update device IP (`update_device_ip`)
3. ❌ Update friendly name (`update_device_friendly_name`)

### 5. **Foundries.io Integration Test** (When Implemented)
1. ❌ Connect Foundries VPN (`connect_foundries_vpn`)
2. ❌ List Foundries devices (`list_foundries_devices`)
3. ❌ Check OTA status (`check_ota_status`)
4. ❌ Trigger OTA update (`trigger_ota_update`)

---

## Tools to Consider Removing

| Tool | Reason | Alternative |
|------|--------|-------------|
| (None identified yet) | - | - |

**Note:** Review tools after testing to identify redundant or unused functionality.

---

## Tools to Add

### High Priority
1. **Foundries.io VPN Tools** (P2)
   - `connect_foundries_vpn` - Connect via Foundries.io WireGuard server
   - `list_foundries_devices` - List devices accessible via Foundries VPN
   - `foundries_vpn_setup` - Setup Foundries VPN configuration

2. **Enhanced Power Analysis** (P3)
   - `export_power_report` - Export power analysis as PDF/CSV
   - `power_alerts` - Configure power consumption alerts
   - `power_baseline` - Establish power consumption baselines

### Medium Priority
3. **Device Configuration Management**
   - `update_device_config` - Update device configuration remotely
   - `backup_device_config` - Backup device configuration
   - `restore_device_config` - Restore device configuration

4. **Network Diagnostics**
   - `network_ping_test` - Comprehensive ping test
   - `network_traceroute` - Network path tracing
   - `network_bandwidth_test` - Bandwidth measurement

### Low Priority
5. **Log Management**
   - `collect_device_logs` - Collect logs from devices
   - `analyze_device_logs` - Analyze device logs
   - `export_logs` - Export logs for analysis

---

## Testing Environment Requirements

### Hardware
- [ ] Embedded Linux devices (iMX8MM, iMX93, etc.)
- [ ] Tasmota power switches with energy monitoring
- [ ] DMM with SCPI support (Keysight, etc.)
- [ ] Test network infrastructure

### Software
- [ ] WireGuard VPN configured
- [ ] Foundries.io account and VPN setup (when implemented)
- [ ] SSH access to devices
- [ ] SCPI-capable test equipment

### Network
- [ ] Remote test network accessible via VPN
- [ ] DHCP support for dynamic IP testing
- [ ] Network isolation for testing

---

## Documentation Priorities

1. **VPN Setup Guide** (P2)
   - Standard WireGuard setup
   - Foundries.io WireGuard setup (when implemented)
   - NetworkManager integration
   - Troubleshooting

2. **Power Monitoring Guide** (P3)
   - DMM setup and configuration
   - Tasmota energy monitoring setup
   - Power analysis workflows
   - Low power testing procedures

3. **Device Management Guide** (P1)
   - Device discovery and identification
   - DHCP environment handling
   - Device configuration management

4. **Testing Workflows** (All Priorities)
   - Common testing scenarios
   - Regression testing procedures
   - Power optimization workflows

---

## Next Steps

1. **Immediate (This Week)**
   - [ ] Complete Priority 1 testing (Core Device Discovery)
   - [ ] Complete Priority 2 testing (VPN Management - Standard WireGuard)
   - [ ] Document VPN setup process for new developers

2. **Short Term (This Month)**
   - [ ] Complete Priority 3 testing (Power Monitoring)
   - [ ] Implement Foundries.io VPN tools (Priority 2)
   - [ ] Complete Priority 4 testing (Device Control)

3. **Medium Term (Next Quarter)**
   - [ ] Complete Priority 5-7 testing
   - [ ] Implement enhanced power analysis tools
   - [ ] Complete documentation

4. **Long Term (Ongoing)**
   - [ ] Continuous testing and improvement
   - [ ] Add new tools as needed
   - [ ] Remove unused/redundant tools

---

## Notes

- **VPN Testing:** Ensure both standard WireGuard and Foundries.io WireGuard are tested separately
- **Power Monitoring:** Critical for embedded Linux power optimization - ensure accuracy and reliability
- **DHCP Environments:** Many remote test networks use DHCP - ensure tools handle IP changes gracefully
- **Documentation:** Focus on new developer onboarding - make it easy to get started
- **Foundries.io Integration:** This is a distinct VPN mechanism - needs separate implementation and testing

