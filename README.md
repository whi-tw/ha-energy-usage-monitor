# Home Assistant Energy Usage Monitor

Custom Home Assistant integration for monitoring always-on appliance health using power consumption patterns.

## 📦 What's Inside

This repository contains a production-ready **custom integration** for Home Assistant that monitors appliances like refrigerators, freezers, and HVAC systems using power-only monitors (e.g., Shelly PM2 Mini).

### Key Features

- ✅ **Zero YAML Configuration** - Complete UI-based setup
- ✅ **Automatic Baseline Learning** - Adapts to your specific appliance
- ✅ **Event-Driven Architecture** - No polling, instant response
- ✅ **Multiple Detection Types**:
  - Door left open (power spike)
  - Compressor failure (low power or no cycles)
  - Cycle pattern anomalies
  - Baseline drift (future enhancement)
- ✅ **10 Entities Per Appliance** - 7 sensors + 3 binary sensors
- ✅ **Reusable** - Monitor multiple appliances independently

## 🚀 Quick Start

### Installation Methods

#### Option A: HACS (Recommended)

1. **Open HACS** in Home Assistant
2. Go to **Integrations**
3. Click **⋮** (three dots in top right) → **Custom repositories**
4. Add repository:
   - **URL:** `https://github.com/whi-tw/ha-energy-usage-monitor`
   - **Category:** Integration
5. Click **Add**
6. Find **"Appliance Health Monitor"** in HACS
7. Click **Download**
8. Restart Home Assistant

#### Option B: Manual Installation

```bash
# Clone or navigate to this repo
cd /path/to/ha-energy-usage-monitor

# Deploy to your HA instance
./deploy.sh /config

# Or copy manually
cp -r custom_components/appliance_health_monitor /config/custom_components/
```

### Setup After Installation

1. **Restart Home Assistant** (if using manual installation; HACS prompts you automatically)

2. **Add Integration**
   - **Settings → Devices & Services → + Add Integration**
   - Search for **"Appliance Health Monitor"**
   - Configure your appliance:
     - Name: `Refrigerator`
     - Power Sensor: `sensor.refrigerator_power` (your Shelly PM2)
     - Type: `Refrigerator`
   - Accept default thresholds (or customize)
   - Wait 48 hours for baseline learning

3. **Monitor & Enjoy**

Watch these entities:
- `sensor.refrigerator_health_state` - Current status
- `sensor.refrigerator_learning_progress` - Learning progress (0-100%)
- `binary_sensor.refrigerator_door_open` - Door alert
- `binary_sensor.refrigerator_needs_attention` - Any anomaly

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Detailed deployment and setup instructions
- **[VALIDATION_CHECKLIST.md](VALIDATION_CHECKLIST.md)** - Testing checklist
- **[custom_components/appliance_health_monitor/README.md](custom_components/appliance_health_monitor/README.md)** - Complete integration documentation

## 📊 What It Monitors

### During Learning Phase (48 hours default)

The integration observes your appliance to learn:
- Average power consumption
- Power variance (standard deviation)
- Compressor ON power level
- Compressor OFF power level
- Normal cycle patterns

### During Monitoring Phase

Detects these anomalies:

| Anomaly | Trigger | Action |
|---------|---------|--------|
| **Door Open** | Power > baseline + 2.5×σ for 3+ min | Alert, set binary sensor |
| **Compressor Failing** | Power < 30% baseline OR no cycles for 4h | Alert, change state |
| **Cycle Anomaly** | Daily cycles ±50% from expected | Alert, change state |
| **Offline** | Power sensor unavailable | Change state to offline |

## 🔧 Requirements

- **Home Assistant:** 2024.1 or newer
- **Power Monitor:** Any sensor with:
  - Domain: `sensor`
  - Device Class: `power`
  - Unit: `W` (watts)
  - Updates: Every 1-5 minutes recommended
- **Examples:** Shelly PM2 Mini, Shelly Plug S, Sonoff POW, TP-Link HS110, Zigbee plugs with power monitoring

## 📁 Project Structure

```
.
├── custom_components/
│   └── appliance_health_monitor/      # The integration
│       ├── __init__.py                 # Core logic + monitoring coordinator
│       ├── config_flow.py              # UI configuration
│       ├── sensor.py                   # 7 sensor entities
│       ├── binary_sensor.py            # 3 binary sensor entities
│       ├── const.py                    # Constants and defaults
│       ├── manifest.json               # Integration metadata
│       ├── strings.json                # UI text
│       ├── translations/en.json        # English translations
│       ├── hacs.json                   # HACS metadata
│       └── README.md                   # Integration docs
├── deploy.sh                           # Deployment script
├── QUICKSTART.md                       # Setup guide
├── VALIDATION_CHECKLIST.md             # Testing checklist
└── README.md                           # This file
```

## 🎯 Roadmap

### ✅ Completed (v1.0)

- Event-driven monitoring architecture
- Baseline learning with statistics
- Door open detection
- Compressor failure detection
- Cycle pattern analysis
- UI-based configuration
- Comprehensive documentation

### 🔮 Future Enhancements (v1.1+)

- [ ] Custom services (`reset_baseline`, `force_state`)
- [ ] Baseline drift detection using 7-day rolling averages
- [ ] Seasonal adjustment recommendations
- [ ] Machine learning for pattern recognition
- [ ] Multi-language translations
- [ ] Energy cost tracking integration
- [ ] Historical trend charts
- [ ] HACS default repository submission

## 🤝 Contributing

This is a personal project, but contributions are welcome!

**To contribute:**
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with VALIDATION_CHECKLIST.md
5. Submit a pull request

**Areas needing help:**
- Testing with different appliance types (freezers, HVAC, etc.)
- Translations (non-English languages)
- Dashboard card templates
- Additional detection algorithms

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Credits

**Inspired by:**
- [Appliance Status Monitor](https://github.com/leofabri/hassio_appliance-status-monitor) by @leofabri - Excellent blueprint for cyclical appliances (washing machines, dishwashers)

**Built with:**
- Home Assistant Core
- Python 3.11+
- Event-driven architecture patterns

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/whi-tw/ha-energy-usage-monitor/issues)
- **Discussions:** [GitHub Discussions](https://github.com/whi-tw/ha-energy-usage-monitor/discussions)
- **Home Assistant Community:** [Coming soon]

## ⚠️ Disclaimer

This integration monitors appliance health for informational purposes only. It does not replace professional appliance maintenance or safety inspections. Always consult a qualified technician for appliance issues.

---

**Made with ❤️ for the Home Assistant community**

**Status:** ✅ Production Ready | 🧪 Testing Phase | 📦 Version 1.0.0
