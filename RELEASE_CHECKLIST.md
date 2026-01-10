# Pre-Release Validation Checklist

## Automated Checks ✅ (Completed)

- ✅ **Python Syntax**: All `.py` files compile without syntax errors
- ✅ **JSON Validation**: All JSON files are valid
  - manifest.json
  - strings.json
  - translations/en.json
  - hacs.json
- ✅ **Imports**: All constants used are defined
  - All `CONF_*` constants exist
  - All `SUFFIX_*` constants exist
  - All `STATE_*` constants exist
- ✅ **Method Calls**: All called methods are defined
  - Async methods match their calls
  - No typos in method names
- ✅ **Entity Access**: All entity retrievals have None checks
- ✅ **No Obvious Errors**: Code review complete

## Known Fixed Issues (v1.1.0 - v1.1.6)

- ✅ Python 3.13 `from __future__ import annotations` compatibility
- ✅ Form validation ranges for sump pump preset
- ✅ Learning start time initialization race condition
- ✅ Daily reset callback method name typo
- ✅ Health state sensor missing ENUM device class
- ✅ Options flow config_entry property conflict

## Manual Testing Required

### Initial Setup
- [ ] Integration appears in "Add Integration" search
- [ ] Config flow step 1 loads (appliance name, sensor, type)
- [ ] Power sensor dropdown shows available sensors
- [ ] Appliance type selector shows all types (including sump_pump)
- [ ] Config flow step 2 loads (thresholds)
- [ ] Sump pump preset applies correct defaults (5 cycles, 168h learning, 168h max idle)
- [ ] Form accepts sump pump preset values without validation errors
- [ ] Integration creates successfully

### Entity Creation
- [ ] All 10 entities created
  - 7 sensors
  - 3 binary sensors
- [ ] Entity names use appliance type labels
  - Refrigerator: "Door Open", "Compressor On Power"
  - Sump Pump: "Power Spike", "Pump On Power"
- [ ] Health state sensor has ENUM device class
- [ ] All entities show initial values

### Learning Phase
- [ ] Learning progress increases from 0%
- [ ] No errors in logs during learning
- [ ] Coordinator starts without crashes
- [ ] Power sensor changes are processed

### Options Flow
- [ ] Can click "Configure" on existing integration
- [ ] Options form loads with current values
- [ ] Can modify settings
- [ ] Can save changes
- [ ] Integration reloads successfully

## Critical Tests Before Release

1. **Fresh Install Test**
   - Delete integration
   - Restart HA
   - Add integration from scratch
   - Verify no errors in logs

2. **Restart Survival Test**
   - Integration running
   - Restart HA
   - Verify integration resumes

3. **Options Flow Test**
   - Configure existing integration
   - Change a threshold
   - Save
   - Verify no crashes

## Release Process

1. Run automated checks (see above) ✅
2. Perform manual tests
3. Update version in `manifest.json`
4. Commit with clear message
5. Push to GitHub
6. Create release with changelog
7. Test HACS installation from release

## Version History

- v1.1.0 - Context-aware labels, sump pump support
- v1.1.1 - Validation range fixes
- v1.1.2 - Learning start time fix
- v1.1.3 - Daily reset callback fix
- v1.1.4 - ENUM device class fix
- v1.1.5 - Options flow attempted fix (incomplete)
- v1.1.6 - Options flow complete fix
