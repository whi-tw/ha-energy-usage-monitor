# Quick Start Guide - Local Testing

## Prerequisites

- Home Assistant instance running (OS/Container/Core)
- Shelly PM2 Mini already configured in HA with power sensor
- SSH or file access to HA config directory

---

## Method 1: Automatic Deployment (Recommended)

### If HA is on the same machine:

```bash
cd /home/mike/github/personal/ha-energy-usage-monitor
./deploy.sh /path/to/homeassistant/config
```

### If HA is remote:

```bash
# Copy the integration
scp -r custom_components/appliance_health_monitor user@ha-server:/config/custom_components/

# SSH and restart
ssh user@ha-server
ha core restart
```

### If using Home Assistant OS:

**Via Samba/File Share:**
1. Open file explorer
2. Connect to `\\your-ha-ip\config`
3. Navigate to `custom_components/`
4. Copy the entire `appliance_health_monitor` folder here
5. Restart HA via UI

**Via SSH (if enabled):**
```bash
# From your computer
scp -r custom_components/appliance_health_monitor root@ha-ip:/config/custom_components/

# SSH to HA and restart
ssh root@ha-ip
ha core restart
```

---

## Method 2: Manual Copy

1. **Locate your HA config directory:**
   - HA OS: `/config`
   - HA Container: `/usr/share/hassio/homeassistant`
   - HA Core: `~/.homeassistant` or `/config`

2. **Copy the integration:**
   ```bash
   cp -r custom_components/appliance_health_monitor /path/to/config/custom_components/
   ```

3. **Verify file structure:**
   ```
   /config/
   └── custom_components/
       └── appliance_health_monitor/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           ├── const.py
           ├── sensor.py
           ├── binary_sensor.py
           ├── strings.json
           ├── hacs.json
           ├── README.md
           └── translations/
               └── en.json
   ```

4. **Restart Home Assistant**

---

## Setup in Home Assistant

### Step 1: Add Integration

1. Go to **Settings → Devices & Services**
2. Click **"+ Add Integration"** (bottom right)
3. Search for **"Appliance Health Monitor"**
4. Click on it

### Step 2: Configure Basic Info

**Form 1 - Basic Configuration:**
- **Appliance Name:** `Refrigerator` (or whatever you want)
- **Power Sensor:** Select your Shelly PM2 sensor
  - Look for `sensor.refrigerator_power` or similar
  - Should show device class "power" with unit W
- **Appliance Type:** `Refrigerator`
  - This sets optimal defaults for compressor cycles

Click **Submit** →

### Step 3: Configure Thresholds (Optional)

**Form 2 - Detection Thresholds:**

For first-time setup, **accept all defaults**:
- Learning Period: 48 hours
- Door Sensitivity: 2.5
- Door Grace Period: 3 minutes
- Compressor Threshold: 30W
- Max Compressor Off: 4 hours
- Baseline Drift: 15%
- Expected Cycles: 30/day
- Cycle Tolerance: 50%

Click **Submit**

### Step 4: Verify Installation

Check that these entities were created:

**Sensors:**
- `sensor.refrigerator_health_state` → Should show "initializing"
- `sensor.refrigerator_learning_progress` → Should show 0%
- `sensor.refrigerator_baseline_average_power` → Shows 0W initially
- `sensor.refrigerator_compressor_cycles_daily` → Shows 0

**Binary Sensors:**
- `binary_sensor.refrigerator_door_open` → Should be OFF
- `binary_sensor.refrigerator_needs_attention` → Should be OFF
- `binary_sensor.refrigerator_compressor_running` → Will update as it learns

### Step 5: Monitor Learning Progress

**Initial State:**
```
Health State: initializing
Learning Progress: 0%
```

**After 24 hours:**
```
Learning Progress: 50%
```

**After 48 hours:**
```
Health State: normal
Learning Progress: 100%
Baseline Average: ~45W (example)
Compressor ON: ~120W (example)
Compressor OFF: ~5W (example)
```

---

## Quick Dashboard Setup

**Create a card to monitor learning:**

```yaml
type: entities
title: Refrigerator Monitor
entities:
  - entity: sensor.refrigerator_health_state
    name: Health Status
  - entity: sensor.refrigerator_learning_progress
    name: Learning Progress
  - entity: sensor.refrigerator_baseline_average_power
    name: Baseline Power
  - entity: binary_sensor.refrigerator_compressor_running
    name: Compressor
  - entity: sensor.refrigerator_compressor_cycles_daily
    name: Cycles Today
```

---

## Testing Before Full Learning

If you want to test that it's working **before waiting 48 hours**:

### Speed Up Learning (Testing Only)

1. **Reconfigure the integration:**
   - Settings → Devices & Services
   - Find "Appliance Health Monitor"
   - Click **Configure**
   - Change "Learning Period" to **1 hour**
   - Save

2. **Wait 1 hour**, then check:
   - `sensor.refrigerator_learning_progress` should reach 100%
   - `sensor.refrigerator_health_state` should change to "normal"
   - Baseline values should be populated

3. **After testing, reconfigure back to 48 hours** for production use

---

## Troubleshooting

### Integration doesn't appear in "Add Integration"

**Solution:**
1. Check files are in correct location: `/config/custom_components/appliance_health_monitor/`
2. Check file permissions (should be readable)
3. Restart HA again (sometimes needs 2 restarts)
4. Check HA logs: Settings → System → Logs
   - Search for "appliance_health_monitor"
   - Look for errors

### Entities not created

**Solution:**
1. Check HA logs for errors
2. Verify power sensor exists and is updating
3. Try removing and re-adding the integration

### Learning not progressing

**Solution:**
1. Check `sensor.refrigerator_power` is actually updating
   - Go to Developer Tools → States
   - Find your power sensor
   - Verify "Last Changed" timestamp updates regularly
2. Check HA logs for errors in `appliance_health_monitor`
3. Ensure appliance is actually running (not unplugged!)

### Power sensor not in dropdown

**Solution:**
1. Your power sensor must have:
   - Domain: `sensor`
   - Device class: `power`
   - Unit: W (watts)
2. If missing, create a template sensor:
   ```yaml
   template:
     - sensor:
         - name: "Refrigerator Power"
           state: "{{ states('sensor.your_shelly_sensor') }}"
           unit_of_measurement: "W"
           device_class: power
   ```

---

## Example: Complete Setup Session

```bash
# 1. Deploy
cd /home/mike/github/personal/ha-energy-usage-monitor
./deploy.sh /config

# 2. Restart HA (via SSH or UI)
ha core restart

# 3. Wait for restart (30-60 seconds)

# 4. Open HA UI
# Settings → Devices & Services → + Add Integration
# Search "Appliance" → Select "Appliance Health Monitor"

# 5. Fill form:
# Name: Refrigerator
# Sensor: sensor.refrigerator_power
# Type: Refrigerator
# Accept defaults → Submit

# 6. Verify in Developer Tools → States:
# Search "refrigerator" → Should see 10 new entities

# 7. Create dashboard card to monitor
# 8. Wait 48 hours
# 9. Enjoy automatic monitoring!
```

---

## Next Steps After Learning

Once learning is complete (48 hours):

1. **Verify baseline values make sense:**
   - Check `sensor.refrigerator_baseline_average_power`
   - Should match your expected refrigerator power consumption
   - Typical: 30-80W average

2. **Test door open detection:**
   - Open refrigerator door for 5+ minutes
   - Check if `binary_sensor.refrigerator_door_open` turns ON
   - Check if `sensor.refrigerator_health_state` shows "door_open"

3. **Create automations** for notifications (see README.md)

4. **Fine-tune thresholds** if getting false alerts

---

## Where is Everything?

**Integration Code:**
```
/config/custom_components/appliance_health_monitor/
```

**Logs:**
```
Settings → System → Logs
Search: "appliance_health_monitor"
```

**Entities:**
```
Settings → Devices & Services → Entities
Filter: "refrigerator"
```

**Device Info:**
```
Settings → Devices & Services → Appliance Health Monitor
Click on device name
```

---

## Ready to Test!

You're all set. Just run:
```bash
./deploy.sh /your/ha/config/path
```

Then add the integration via UI and start monitoring! 🎉
