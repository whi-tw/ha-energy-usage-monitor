"""Binary sensor platform for Appliance Health Monitor."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_APPLIANCE_NAME,
    DOMAIN,
    SUFFIX_COMPRESSOR_STATE,
    SUFFIX_DOOR_OPEN,
    SUFFIX_NEEDS_ATTENTION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Appliance Health Monitor binary sensors from a config entry."""
    appliance_name = entry.data[CONF_APPLIANCE_NAME]

    entities = [
        ApplianceDoorOpenBinarySensor(entry, appliance_name),
        ApplianceNeedsAttentionBinarySensor(entry, appliance_name),
        ApplianceCompressorStateBinarySensor(entry, appliance_name),
    ]

    async_add_entities(entities)

    # Store entity references in hass.data for coordinator access
    hass.data[DOMAIN].setdefault("entities", {})
    for entity in entities:
        hass.data[DOMAIN]["entities"][entity.unique_id] = entity


class ApplianceHealthMonitorBinarySensor(BinarySensorEntity):
    """Base class for Appliance Health Monitor binary sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, appliance_name: str, suffix: str) -> None:
        """Initialize the binary sensor."""
        self._entry = entry
        self._appliance_name = appliance_name
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{appliance_name} Health Monitor",
            manufacturer="Appliance Health Monitor",
            model="Always-On Appliance",
            sw_version="1.0.0",
        )
        self._state = False


class ApplianceDoorOpenBinarySensor(ApplianceHealthMonitorBinarySensor):
    """Binary sensor for door open detection."""

    _attr_icon = "mdi:fridge-alert"
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, entry: ConfigEntry, appliance_name: str) -> None:
        """Initialize the door open sensor."""
        super().__init__(entry, appliance_name, SUFFIX_DOOR_OPEN)
        self._attr_name = "Door Open"

    @property
    def is_on(self) -> bool:
        """Return true if door is open."""
        return self._state

    async def async_update_state(self, is_open: bool) -> None:
        """Update the sensor state."""
        self._state = is_open
        self.async_write_ha_state()


class ApplianceNeedsAttentionBinarySensor(ApplianceHealthMonitorBinarySensor):
    """Binary sensor for needs attention."""

    _attr_icon = "mdi:alert-circle"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, entry: ConfigEntry, appliance_name: str) -> None:
        """Initialize the needs attention sensor."""
        super().__init__(entry, appliance_name, SUFFIX_NEEDS_ATTENTION)
        self._attr_name = "Needs Attention"

    @property
    def is_on(self) -> bool:
        """Return true if appliance needs attention."""
        return self._state

    async def async_update_state(self, needs_attention: bool) -> None:
        """Update the sensor state."""
        self._state = needs_attention
        self.async_write_ha_state()


class ApplianceCompressorStateBinarySensor(ApplianceHealthMonitorBinarySensor):
    """Binary sensor for compressor state."""

    _attr_icon = "mdi:engine"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, entry: ConfigEntry, appliance_name: str) -> None:
        """Initialize the compressor state sensor."""
        super().__init__(entry, appliance_name, SUFFIX_COMPRESSOR_STATE)
        self._attr_name = "Compressor Running"

    @property
    def is_on(self) -> bool:
        """Return true if compressor is running."""
        return self._state

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:engine" if self._state else "mdi:engine-off"

    async def async_update_state(self, is_running: bool) -> None:
        """Update the sensor state."""
        self._state = is_running
        self.async_write_ha_state()
