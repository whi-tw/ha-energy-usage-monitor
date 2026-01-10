"""Sensor platform for Appliance Health Monitor."""

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    APPLIANCE_LABELS,
    APPLIANCE_TYPE_CUSTOM,
    ATTR_BASELINE_MEAN,
    ATTR_BASELINE_STDDEV,
    ATTR_COMPRESSOR_OFF_POWER,
    ATTR_COMPRESSOR_ON_POWER,
    ATTR_DAILY_CYCLES,
    ATTR_LAST_CYCLE_TIME,
    ATTR_LEARNING_PROGRESS,
    ATTR_SAMPLES_COLLECTED,
    CONF_APPLIANCE_NAME,
    CONF_APPLIANCE_TYPE,
    DOMAIN,
    HEALTH_STATES,
    STATE_INITIALIZING,
    SUFFIX_BASELINE_AVERAGE,
    SUFFIX_BASELINE_STDDEV,
    SUFFIX_COMPRESSOR_CYCLES,
    SUFFIX_COMPRESSOR_OFF_POWER,
    SUFFIX_COMPRESSOR_ON_POWER,
    SUFFIX_HEALTH_STATE,
    SUFFIX_LEARNING_PROGRESS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Appliance Health Monitor sensors from a config entry."""
    appliance_name = entry.data[CONF_APPLIANCE_NAME]
    appliance_type = entry.data.get(CONF_APPLIANCE_TYPE, APPLIANCE_TYPE_CUSTOM)

    entities = [
        ApplianceHealthStateSensor(entry, appliance_name, appliance_type),
        ApplianceBaselineSensor(entry, appliance_name, appliance_type),
        ApplianceStdDevSensor(entry, appliance_name, appliance_type),
        ApplianceCompressorOnPowerSensor(entry, appliance_name, appliance_type),
        ApplianceCompressorOffPowerSensor(entry, appliance_name, appliance_type),
        ApplianceCompressorCyclesSensor(entry, appliance_name, appliance_type),
        ApplianceLearningProgressSensor(entry, appliance_name, appliance_type),
    ]

    async_add_entities(entities)

    # Store entity references in hass.data for coordinator access
    hass.data[DOMAIN].setdefault("entities", {})
    for entity in entities:
        hass.data[DOMAIN]["entities"][entity.unique_id] = entity


class ApplianceHealthMonitorSensor(SensorEntity):
    """Base class for Appliance Health Monitor sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, appliance_name: str, appliance_type: str, suffix: str) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._appliance_name = appliance_name
        self._appliance_type = appliance_type
        self._labels = APPLIANCE_LABELS.get(appliance_type, APPLIANCE_LABELS[APPLIANCE_TYPE_CUSTOM])
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{appliance_name} Health Monitor",
            manufacturer="Appliance Health Monitor",
            model="Always-On Appliance",
            sw_version="1.0.2",
        )


class ApplianceHealthStateSensor(ApplianceHealthMonitorSensor):
    """Sensor for appliance health state."""

    _attr_icon = "mdi:state-machine"

    def __init__(self, entry: ConfigEntry, appliance_name: str, appliance_type: str) -> None:
        """Initialize the health state sensor."""
        super().__init__(entry, appliance_name, appliance_type, SUFFIX_HEALTH_STATE)
        self._attr_name = "Health State"
        self._state = STATE_INITIALIZING
        self._attr_extra_state_attributes = {}

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def options(self) -> list[str]:
        """Return a list of possible states."""
        return HEALTH_STATES

    async def async_update_state(self, new_state: str, attributes: dict[str, Any] | None = None) -> None:
        """Update the sensor state."""
        self._state = new_state
        if attributes:
            self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()


class ApplianceBaselineSensor(ApplianceHealthMonitorSensor):
    """Sensor for baseline average power."""

    _attr_icon = "mdi:chart-line"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: ConfigEntry, appliance_name: str, appliance_type: str) -> None:
        """Initialize the baseline sensor."""
        super().__init__(entry, appliance_name, appliance_type, SUFFIX_BASELINE_AVERAGE)
        self._attr_name = "Baseline Average Power"
        self._state = 0.0

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._state

    async def async_update_value(self, value: float) -> None:
        """Update the sensor value."""
        self._state = round(value, 2)
        self.async_write_ha_state()


class ApplianceStdDevSensor(ApplianceHealthMonitorSensor):
    """Sensor for baseline standard deviation."""

    _attr_icon = "mdi:chart-bell-curve"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: ConfigEntry, appliance_name: str, appliance_type: str) -> None:
        """Initialize the stddev sensor."""
        super().__init__(entry, appliance_name, appliance_type, SUFFIX_BASELINE_STDDEV)
        self._attr_name = "Baseline Standard Deviation"
        self._state = 0.0

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._state

    async def async_update_value(self, value: float) -> None:
        """Update the sensor value."""
        self._state = round(value, 2)
        self.async_write_ha_state()


class ApplianceCompressorOnPowerSensor(ApplianceHealthMonitorSensor):
    """Sensor for compressor ON power."""

    _attr_icon = "mdi:lightning-bolt"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: ConfigEntry, appliance_name: str, appliance_type: str) -> None:
        """Initialize the device ON power sensor."""
        super().__init__(entry, appliance_name, appliance_type, SUFFIX_COMPRESSOR_ON_POWER)
        self._attr_name = f"{self._labels['device_on']} Power"
        self._state = 0.0

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._state

    async def async_update_value(self, value: float) -> None:
        """Update the sensor value."""
        self._state = round(value, 2)
        self.async_write_ha_state()


class ApplianceCompressorOffPowerSensor(ApplianceHealthMonitorSensor):
    """Sensor for compressor OFF power."""

    _attr_icon = "mdi:power-standby"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: ConfigEntry, appliance_name: str, appliance_type: str) -> None:
        """Initialize the device OFF power sensor."""
        super().__init__(entry, appliance_name, appliance_type, SUFFIX_COMPRESSOR_OFF_POWER)
        self._attr_name = f"{self._labels['device_off']} Power"
        self._state = 0.0

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._state

    async def async_update_value(self, value: float) -> None:
        """Update the sensor value."""
        self._state = round(value, 2)
        self.async_write_ha_state()


class ApplianceCompressorCyclesSensor(ApplianceHealthMonitorSensor):
    """Sensor for daily compressor cycles."""

    _attr_icon = "mdi:sync"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, entry: ConfigEntry, appliance_name: str, appliance_type: str) -> None:
        """Initialize the device cycles sensor."""
        super().__init__(entry, appliance_name, appliance_type, SUFFIX_COMPRESSOR_CYCLES)
        self._attr_name = f"{self._labels['cycles']} (Daily)"
        self._state = 0

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state

    async def async_update_value(self, value: int) -> None:
        """Update the sensor value."""
        self._state = value
        self.async_write_ha_state()

    async def async_reset(self) -> None:
        """Reset the counter."""
        self._state = 0
        self.async_write_ha_state()


class ApplianceLearningProgressSensor(ApplianceHealthMonitorSensor):
    """Sensor for learning progress."""

    _attr_icon = "mdi:progress-clock"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: ConfigEntry, appliance_name: str, appliance_type: str) -> None:
        """Initialize the learning progress sensor."""
        super().__init__(entry, appliance_name, appliance_type, SUFFIX_LEARNING_PROGRESS)
        self._attr_name = "Learning Progress"
        self._state = 0

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._state

    async def async_update_value(self, value: int) -> None:
        """Update the sensor value."""
        self._state = min(100, max(0, value))
        self.async_write_ha_state()
