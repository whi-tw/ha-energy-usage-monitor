# Appliance Health Monitor

A Home Assistant custom integration for monitoring the health of always-on appliances (refrigerators, freezers, HVAC systems) using **power-only monitors** like Shelly PM2 Mini.

## Features

✅ **Automatic Baseline Learning** - Learns your appliance's normal power consumption patterns over 24-168 hours
✅ **Door Left Open Detection** - Alerts when power consumption spikes (e.g., refrigerator door left open)
✅ **Compressor Failure Detection** - Detects abnormally low power or missing compressor cycles
✅ **Baseline Drift Detection** - Tracks gradual efficiency changes over time
✅ **Cycle Pattern Analysis** - Monitors compressor on/off cycles for anomalies
✅ **Zero YAML Required** - Complete UI-based setup via config flow
✅ **Event-Driven** - No polling, leverages Home Assistant's state change events

## Installation

### Via HACS (Recommended - Coming Soon)

1. Open HACS → Integrations
2. Click "+" → Search for "Appliance Health Monitor"
3. Install
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/appliance_health_monitor` directory to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Setup

### Step 1: Add Integration

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for "Appliance Health Monitor"
4. Click to add

### Step 2: Basic Configuration

Fill in the form:

- **Appliance Name**: e.g., "Refrigerator", "Freezer"
- **Power Sensor**: Select your power monitoring sensor (e.g., `sensor.refrigerator_power`)
- **Appliance Type**: Select type for preset defaults (Refrigerator/Freezer/HVAC/Custom)

### Step 3: Configure Thresholds (Optional)

Adjust detection sensitivity or accept defaults:

| Setting | Default | Description |
|---------|---------|-------------|
| **Learning Period** | 48 hours | How long to observe before monitoring |
| **Door Sensitivity** | 2.5× StdDev | How far above normal = door open |
| **Door Grace Period** | 3 minutes | Wait time before alerting |
| **Compressor Cycle Threshold** | 30W | Power difference to detect ON/OFF |
| **Max Compressor Off Time** | 4 hours | Alert if no cycles for this long |
| **Baseline Drift Threshold** | 15% | % change to trigger drift alert |
| **Expected Daily Cycles** | 30 | Normal compressor cycles per day |
| **Cycle Anomaly Tolerance** | 50% | % deviation before alerting |

**TIP:** Accept all defaults initially, then tune based on your appliance's actual behavior after the learning period.

### Step 4: Wait for Learning

The integration will spend 24-168 hours (default 48) learning your appliance's:
- Average power consumption
- Standard deviation
- Compressor ON power level
- Compressor OFF power level
- Normal cycle patterns

Monitor progress via the **Learning Progress** sensor (0-100%).

### Step 5: Monitoring Begins

After learning completes, the **Health State** sensor will show:
- `normal` - Everything OK
- `door_open` - Power spike detected
- `compressor_failing` - Low power or no cycles
- `baseline_drift_high` - Efficiency decreasing
- `baseline_drift_low` - Possible cooling issue
- `cycle_anomaly` - Irregular cycling

## Entities Created

For each appliance, 10 entities are created:

### Sensors (7)

1. **Health State** - Current health status
2. **Baseline Average Power** - Learned average power (W)
3. **Baseline Standard Deviation** - Power variance (W)
4. **Compressor ON Power** - Average power when running (W)
5. **Compressor OFF Power** - Average power when idle (W)
6. **Compressor Cycles (Daily)** - Cycle count today
7. **Learning Progress** - Learning phase progress (0-100%)

### Binary Sensors (3)

8. **Door Open** - ON when door may be open
9. **Needs Attention** - ON when any anomaly detected
10. **Compressor Running** - ON when compressor is active

## Example Automations

### Door Open Alert

```yaml
automation:
  - alias: "Refrigerator Door Open Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.refrigerator_door_open
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Refrigerator Alert"
          message: "Door may be left open - high power consumption detected"
          data:
            priority: high
```

### Compressor Failure Warning

```yaml
automation:
  - alias: "Refrigerator Compressor Issue"
    trigger:
      - platform: state
        entity_id: sensor.refrigerator_health_state
        to: "compressor_failing"
    action:
      - service: notify.mobile_app
        data:
          title: "Refrigerator Warning"
          message: "Compressor may be failing - check immediately"
```

### Learning Complete Notification

```yaml
automation:
  - alias: "Refrigerator Learning Complete"
    trigger:
      - platform: numeric_state
        entity_id: sensor.refrigerator_learning_progress
        above: 99
    action:
      - service: persistent_notification.create
        data:
          title: "Refrigerator Monitoring Active"
          message: >
            Baseline learning complete!
            Average: {{ states('sensor.refrigerator_baseline_average_power') }}W
            Compressor ON: {{ states('sensor.refrigerator_compressor_on_power') }}W
            Compressor OFF: {{ states('sensor.refrigerator_compressor_off_power') }}W
```

## Dashboard Card Example

```yaml
type: entities
title: Refrigerator Health
entities:
  - entity: sensor.refrigerator_health_state
    name: Status
  - entity: binary_sensor.refrigerator_needs_attention
    name: Needs Attention
  - entity: binary_sensor.refrigerator_compressor_running
    name: Compressor
  - entity: sensor.refrigerator_compressor_cycles_daily
    name: Cycles Today
  - entity: sensor.refrigerator_baseline_average_power
    name: Baseline Power
  - entity: sensor.refrigerator_learning_progress
    name: Learning Progress
```

## Troubleshooting

### Integration not detecting anomalies

- **Check learning is complete**: `sensor.<appliance>_learning_progress` should be 100%
- **Verify baseline values**: Check that `sensor.<appliance>_baseline_average_power` is reasonable
- **Adjust sensitivity**: Reconfigure integration and lower the door sensitivity multiplier
- **Check power sensor**: Ensure power sensor is updating regularly

### False door open alerts

- **Increase sensitivity**: Reconfigure integration, raise door sensitivity from 2.5 to 3.0 or higher
- **Increase grace period**: Raise from 3 minutes to 5+ minutes
- **Check defrost cycles**: Some refrigerators have defrost cycles that spike power

### Compressor cycles not detected

- **Adjust cycle threshold**: Lower the compressor cycle threshold (try 20W instead of 30W)
- **Check power readings**: Ensure power sensor shows clear ON/OFF differences
- **Verify baseline learning**: Compressor ON and OFF power should be significantly different

### Learning taking too long

- **Check power sensor frequency**: Sensor should update at least every 1-5 minutes
- **Extend learning period**: Reconfigure integration, increase learning period to 72+ hours
- **Ensure appliance is running**: Appliance must be powered and cycling normally during learning

## Advanced Configuration

### Reconfigure Thresholds

1. Go to **Settings → Devices & Services**
2. Find "Appliance Health Monitor"
3. Click **Configure** on your appliance
4. Adjust thresholds
5. Save (monitoring continues with new settings)

### Multiple Appliances

Add the integration multiple times (once per appliance):

1. Click **Add Integration** again
2. Configure for second appliance (different name/sensor)
3. Repeat for each appliance

Each instance operates independently with its own baseline learning.

## How It Works

### Event-Driven Architecture

The integration:
1. Subscribes to power sensor state changes (no polling)
2. Collects power readings during learning phase
3. Calculates statistical baselines (mean, standard deviation, compressor ON/OFF levels)
4. Monitors for deviations using configured thresholds
5. Updates entity states when anomalies detected

### Detection Algorithms

**Door Open**: `current_power > (baseline_mean + sensitivity × baseline_stddev)`

**Compressor Failure**: `current_power < (baseline_mean × 0.3)` OR `no_cycles_for > max_off_hours`

**Baseline Drift**: `7day_average > (baseline_mean × 1.15)` (high) or `< 0.85` (low)

**Cycle Anomaly**: `daily_cycles > (expected × 1.5)` OR `< (expected × 0.5)`

### No Polling

Unlike traditional integrations, this uses **event listeners**:
- HA notifies the integration when power sensor changes
- More efficient than polling
- Instant response to power changes
- Leverages HA's existing infrastructure

## Technical Details

- **Platforms**: sensor, binary_sensor
- **Dependencies**: None (pure Python + HA core)
- **Config Flow**: Yes (UI-based setup)
- **Options Flow**: Yes (reconfigure after setup)
- **IoT Class**: local_polling (monitors local sensors)
- **Minimum HA Version**: 2024.1+

## Support

- **Issues**: [GitHub Issues](https://github.com/your_username/ha-energy-usage-monitor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your_username/ha-energy-usage-monitor/discussions)

## License

MIT License - see LICENSE file for details

## Credits

Inspired by the [Appliance Status Monitor](https://github.com/leofabri/hassio_appliance-status-monitor) blueprint for cyclical appliances.

---

**Made with ❤️ for the Home Assistant community**
