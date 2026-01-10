# Validation Checklist

Use this checklist to verify the integration is working correctly after deployment.

## ✅ Pre-Deployment Checks

- [ ] All files present in `custom_components/appliance_health_monitor/`:
  - [ ] `__init__.py`
  - [ ] `manifest.json`
  - [ ] `config_flow.py`
  - [ ] `const.py`
  - [ ] `sensor.py`
  - [ ] `binary_sensor.py`
  - [ ] `strings.json`
  - [ ] `hacs.json`
  - [ ] `README.md`
  - [ ] `translations/en.json`

- [ ] Power sensor exists and is updating:
  - [ ] Check `sensor.refrigerator_power` (or your sensor name) in Developer Tools → States
  - [ ] Verify it has device_class: `power`
  - [ ] Verify unit is `W` (watts)
  - [ ] Verify "Last Changed" updates regularly (every 1-5 minutes)

## ✅ Deployment Checks

- [ ] Files copied to HA config directory
- [ ] Location: `/config/custom_components/appliance_health_monitor/`
- [ ] File permissions are readable
- [ ] Home Assistant restarted successfully
- [ ] No errors in HA logs related to `appliance_health_monitor`

## ✅ Integration Setup Checks

- [ ] Integration appears in "Add Integration" search
- [ ] Config flow form loads without errors
- [ ] Power sensor appears in dropdown selector
- [ ] Form accepts appliance name
- [ ] Thresholds form appears after first submit
- [ ] Integration creates successfully (no errors)

## ✅ Entity Creation Checks

After adding integration, verify these 10 entities exist:

### Sensors (7)
- [ ] `sensor.<appliance>_health_state`
  - Initial value: `initializing`
- [ ] `sensor.<appliance>_baseline_average_power`
  - Initial value: `0` W
- [ ] `sensor.<appliance>_baseline_standard_deviation`
  - Initial value: `0` W
- [ ] `sensor.<appliance>_compressor_on_power`
  - Initial value: `0` W
- [ ] `sensor.<appliance>_compressor_off_power`
  - Initial value: `0` W
- [ ] `sensor.<appliance>_compressor_cycles_daily`
  - Initial value: `0`
- [ ] `sensor.<appliance>_learning_progress`
  - Initial value: `0` %

### Binary Sensors (3)
- [ ] `binary_sensor.<appliance>_door_open`
  - Initial value: `off`
- [ ] `binary_sensor.<appliance>_needs_attention`
  - Initial value: `off`
- [ ] `binary_sensor.<appliance>_compressor_running`
  - Initial value: `off` or `on` (depends on current power)

## ✅ Learning Phase Checks (First Hour)

- [ ] `sensor.<appliance>_learning_progress` increases over time
- [ ] Check after 30 minutes: Should be > 0%
- [ ] Check after 1 hour: Should be ~2% (for 48h learning period)
- [ ] `sensor.<appliance>_health_state` remains `initializing`
- [ ] No errors in HA logs

## ✅ Learning Phase Checks (After Completion)

Default: 48 hours. Check these after learning period:

- [ ] `sensor.<appliance>_learning_progress` = `100%`
- [ ] `sensor.<appliance>_health_state` changed from `initializing` to `normal`
- [ ] `sensor.<appliance>_baseline_average_power` has realistic value (not 0)
  - Typical refrigerator: 30-80W
  - Typical freezer: 40-100W
- [ ] `sensor.<appliance>_baseline_standard_deviation` has value > 0
- [ ] `sensor.<appliance>_compressor_on_power` has value > baseline
- [ ] `sensor.<appliance>_compressor_off_power` has value < baseline
- [ ] `binary_sensor.<appliance>_compressor_running` changes state (on/off)

## ✅ Monitoring Phase Checks

After learning is complete, test anomaly detection:

### Test 1: Door Open Detection

- [ ] Open appliance door for 5+ minutes
- [ ] Wait for grace period (default 3 minutes)
- [ ] `binary_sensor.<appliance>_door_open` turns `on`
- [ ] `sensor.<appliance>_health_state` changes to `door_open`
- [ ] `binary_sensor.<appliance>_needs_attention` turns `on`
- [ ] Close door
- [ ] Sensors return to normal state

### Test 2: Compressor Cycle Tracking

- [ ] Monitor `binary_sensor.<appliance>_compressor_running` over several hours
- [ ] Should toggle `on`/`off` multiple times per day
- [ ] `sensor.<appliance>_compressor_cycles_daily` increments with each ON cycle
- [ ] Check HA logs for "Compressor ON" and "Compressor OFF" debug messages

### Test 3: Daily Counter Reset

- [ ] Note `sensor.<appliance>_compressor_cycles_daily` value before midnight
- [ ] Check value after midnight (00:00)
- [ ] Should reset to `0`
- [ ] Check HA logs for "Daily reset" message

## ✅ Options Flow Checks

Test reconfiguration:

- [ ] Go to Settings → Devices & Services
- [ ] Find "Appliance Health Monitor"
- [ ] Click **Configure**
- [ ] Options form loads with current values
- [ ] Change a threshold (e.g., door sensitivity from 2.5 to 3.0)
- [ ] Save successfully
- [ ] Integration reloads
- [ ] All entities still present
- [ ] New threshold is active

## ✅ Edge Case Checks

### Power Sensor Unavailable

- [ ] Disable/stop power sensor (simulate sensor failure)
- [ ] `sensor.<appliance>_health_state` changes to `offline`
- [ ] Re-enable sensor
- [ ] State returns to previous value (`initializing` or `normal`)

### Home Assistant Restart During Learning

- [ ] Note `sensor.<appliance>_learning_progress` value
- [ ] Restart Home Assistant
- [ ] After restart, learning continues
- [ ] **Note:** Learning progress will reset to 0 (expected limitation)
- [ ] Will need to re-learn after restart

### Multiple Appliances

- [ ] Add integration second time with different name/sensor
- [ ] Both integrations operate independently
- [ ] No conflicts between entities
- [ ] Each has separate baseline learning

## ✅ Performance Checks

- [ ] HA performance not degraded (check CPU/memory in System)
- [ ] Integration responds to power changes within seconds
- [ ] No excessive logging (check HA logs)
- [ ] No memory leaks over 24+ hours

## ✅ Logs Check

Check HA logs (Settings → System → Logs) for:

**Expected messages (INFO level):**
- `Monitoring started for <appliance>`
- `Learning complete for <appliance>: baseline=X.XW±X.XW`
- `Daily reset: X cycles yesterday`

**Debug messages (if debug enabled):**
- `Compressor ON (power: X.XW)`
- `Compressor OFF (power: X.XW)`

**Warning messages (when anomalies detected):**
- `Door may be open: X.XW > X.XW (threshold)`
- `Compressor may be failing: X.XW is very low`
- `No compressor cycles for X.X hours`
- `Cycle anomaly: X cycles (expected X±X%)`

**Should NOT see:**
- Errors or exceptions
- Tracebacks
- "Invalid power value" (unless sensor actually reports invalid data)

## ✅ Documentation Checks

- [ ] README.md is clear and complete
- [ ] QUICKSTART.md has accurate deployment instructions
- [ ] All entity names match reality
- [ ] Example automations are correct
- [ ] Troubleshooting section covers common issues

## 🎯 Success Criteria

All checks above should pass for a successful deployment. Priority checks:

1. **Critical:** All 10 entities created
2. **Critical:** Learning progress increases over time
3. **Critical:** Health state changes to "normal" after learning
4. **Critical:** Door open detection works
5. **Important:** Compressor cycling detected
6. **Important:** No errors in logs
7. **Nice to have:** Options flow works
8. **Nice to have:** Multiple appliances work

## 📊 Testing Summary

| Test Area | Status | Notes |
|-----------|--------|-------|
| Pre-Deployment | ⬜ | |
| Deployment | ⬜ | |
| Integration Setup | ⬜ | |
| Entity Creation | ⬜ | |
| Learning Phase | ⬜ | |
| Monitoring Phase | ⬜ | |
| Options Flow | ⬜ | |
| Edge Cases | ⬜ | |
| Performance | ⬜ | |
| Logs | ⬜ | |

## 🐛 Issues Found

Document any issues discovered during validation:

```
Issue:
Expected:
Actual:
Workaround:
```

---

**Last Updated:** 2026-01-09
**Integration Version:** 1.0.0
