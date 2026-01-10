#!/bin/bash
# Deployment script for Appliance Health Monitor
# Usage: ./deploy.sh [ha_config_path]

set -e

# Default HA config path (adjust as needed)
HA_CONFIG_PATH="${1:-/config}"

echo "🚀 Deploying Appliance Health Monitor to Home Assistant..."
echo "Target: $HA_CONFIG_PATH"

# Check if target exists
if [ ! -d "$HA_CONFIG_PATH" ]; then
    echo "❌ Error: Home Assistant config directory not found: $HA_CONFIG_PATH"
    echo "Usage: ./deploy.sh /path/to/homeassistant/config"
    exit 1
fi

# Create custom_components directory if it doesn't exist
mkdir -p "$HA_CONFIG_PATH/custom_components"

# Copy the integration
echo "📦 Copying integration files..."
cp -r custom_components/appliance_health_monitor "$HA_CONFIG_PATH/custom_components/"

echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Restart Home Assistant"
echo "2. Go to Settings → Devices & Services"
echo "3. Click '+ Add Integration'"
echo "4. Search for 'Appliance Health Monitor'"
echo "5. Configure your appliance"
echo ""
echo "📖 See custom_components/appliance_health_monitor/README.md for details"
