"""The Appliance Health Monitor integration."""

import asyncio
from datetime import datetime, timedelta
import logging
import statistics
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_APPLIANCE_NAME,
    CONF_BASELINE_DRIFT_THRESHOLD,
    CONF_COMPRESSOR_CYCLE_THRESHOLD,
    CONF_CYCLE_ANOMALY_TOLERANCE,
    CONF_DOOR_GRACE_MINUTES,
    CONF_DOOR_OPEN_SENSITIVITY,
    CONF_EXPECTED_DAILY_CYCLES,
    CONF_LEARNING_PERIOD_HOURS,
    CONF_MAX_COMPRESSOR_OFF_HOURS,
    CONF_POWER_SENSOR,
    DOMAIN,
    STATE_BASELINE_DRIFT_HIGH,
    STATE_BASELINE_DRIFT_LOW,
    STATE_COMPRESSOR_FAILING,
    STATE_CYCLE_ANOMALY,
    STATE_DOOR_OPEN,
    STATE_INITIALIZING,
    STATE_NORMAL,
    STATE_OFFLINE,
    STATE_POWER_SPIKE,
    SUFFIX_BASELINE_AVERAGE,
    SUFFIX_BASELINE_STDDEV,
    SUFFIX_COMPRESSOR_CYCLES,
    SUFFIX_COMPRESSOR_OFF_POWER,
    SUFFIX_COMPRESSOR_ON_POWER,
    SUFFIX_COMPRESSOR_STATE,
    SUFFIX_DOOR_OPEN,
    SUFFIX_HEALTH_STATE,
    SUFFIX_LEARNING_PROGRESS,
    SUFFIX_NEEDS_ATTENTION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Appliance Health Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Set up platforms first (creates entities)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Wait a bit for entities to be created
    await asyncio.sleep(0.5)

    # Create and start the monitoring coordinator
    coordinator = ApplianceHealthCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "options": entry.options,
        "coordinator": coordinator,
    }

    # Start monitoring
    await coordinator.async_start()

    # Register update listener for options flow
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info(
        "Appliance Health Monitor set up for '%s'",
        entry.data.get(CONF_APPLIANCE_NAME, "Unknown")
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop the coordinator
    coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
    if coordinator:
        await coordinator.async_stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class ApplianceHealthCoordinator:
    """Coordinator for appliance health monitoring."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self._config = {**entry.data, **entry.options}

        # Entity IDs
        self._power_sensor = self._config[CONF_POWER_SENSOR]
        entry_id = entry.entry_id
        self._health_sensor_id = f"sensor.{entry_id}_{SUFFIX_HEALTH_STATE}"
        self._baseline_sensor_id = f"sensor.{entry_id}_{SUFFIX_BASELINE_AVERAGE}"
        self._stddev_sensor_id = f"sensor.{entry_id}_{SUFFIX_BASELINE_STDDEV}"
        self._compressor_on_id = f"sensor.{entry_id}_{SUFFIX_COMPRESSOR_ON_POWER}"
        self._compressor_off_id = f"sensor.{entry_id}_{SUFFIX_COMPRESSOR_OFF_POWER}"
        self._cycles_sensor_id = f"sensor.{entry_id}_{SUFFIX_COMPRESSOR_CYCLES}"
        self._learning_sensor_id = f"sensor.{entry_id}_{SUFFIX_LEARNING_PROGRESS}"
        self._door_open_sensor_id = f"binary_sensor.{entry_id}_{SUFFIX_DOOR_OPEN}"
        self._needs_attention_id = f"binary_sensor.{entry_id}_{SUFFIX_NEEDS_ATTENTION}"
        self._compressor_state_id = f"binary_sensor.{entry_id}_{SUFFIX_COMPRESSOR_STATE}"

        # Learning phase tracking
        self._baseline_samples: list[float] = []
        self._learning_start_time: datetime | None = None
        self._learning_complete = False

        # Learned values
        self._baseline_mean = 0.0
        self._baseline_stddev = 0.0
        self._compressor_on_power = 0.0
        self._compressor_off_power = 0.0

        # Compressor cycle tracking
        self._compressor_is_on = False
        self._last_compressor_on_time: datetime | None = None
        self._last_compressor_off_time: datetime | None = None
        self._daily_cycles = 0
        self._last_cycle_reset = dt_util.now().date()

        # Anomaly detection state
        self._door_open_start: datetime | None = None
        self._current_state = STATE_INITIALIZING

        # Event listeners
        self._unsub_power_listener = None
        self._unsub_daily_reset = None
        self._unsub_stop_listener = None

    async def async_start(self) -> None:
        """Start monitoring."""
        # Subscribe to power sensor state changes
        self._unsub_power_listener = async_track_state_change_event(
            self.hass,
            [self._power_sensor],
            self._async_power_sensor_changed,
        )

        # Subscribe to daily reset (midnight)
        self._unsub_daily_reset = async_track_time_interval(
            self.hass,
            self._async_daily_reset,
            timedelta(hours=24),
        )

        # Subscribe to HA stop event
        self._unsub_stop_listener = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP,
            self._async_stop,
        )

        # Start learning
        self._learning_start_time = dt_util.now()
        await self._update_health_state(STATE_INITIALIZING)

        _LOGGER.info("Monitoring started for %s", self._config[CONF_APPLIANCE_NAME])

    async def async_stop(self) -> None:
        """Stop monitoring."""
        if self._unsub_power_listener:
            self._unsub_power_listener()
        if self._unsub_daily_reset:
            self._unsub_daily_reset()
        if self._unsub_stop_listener:
            self._unsub_stop_listener()

        _LOGGER.info("Monitoring stopped for %s", self._config[CONF_APPLIANCE_NAME])

    async def _async_stop(self, event: Event) -> None:
        """Handle HA stop event."""
        await self.async_stop()

    @callback
    async def _async_power_sensor_changed(self, event: Event) -> None:
        """Handle power sensor state change."""
        new_state = event.data.get("new_state")

        # Handle sensor unavailable
        if new_state is None or new_state.state in ("unavailable", "unknown"):
            await self._update_health_state(STATE_OFFLINE)
            return

        try:
            current_power = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid power value: %s", new_state.state)
            return

        # Learning phase
        if not self._learning_complete:
            await self._process_learning_phase(current_power)
            return

        # Normal monitoring
        await self._process_monitoring_phase(current_power)

    async def _process_learning_phase(self, current_power: float) -> None:
        """Process power reading during learning phase."""
        # Initialize learning start time if not set
        if self._learning_start_time is None:
            self._learning_start_time = dt_util.now()
            _LOGGER.debug("Learning phase started")

        # Collect sample
        self._baseline_samples.append(current_power)

        # Update learning progress
        learning_hours = self._config[CONF_LEARNING_PERIOD_HOURS]
        elapsed_hours = (dt_util.now() - self._learning_start_time).total_seconds() / 3600
        progress = min(100, int((elapsed_hours / learning_hours) * 100))

        await self._update_learning_progress(progress)

        # Check if learning is complete
        if elapsed_hours >= learning_hours:
            await self._complete_learning()

    async def _complete_learning(self) -> None:
        """Complete the learning phase and calculate baselines."""
        if len(self._baseline_samples) < 10:
            _LOGGER.warning("Not enough samples collected (%d), extending learning", len(self._baseline_samples))
            return

        # Calculate baseline statistics
        self._baseline_mean = statistics.mean(self._baseline_samples)
        self._baseline_stddev = statistics.stdev(self._baseline_samples) if len(self._baseline_samples) > 1 else 0.0

        # Detect compressor ON/OFF power levels
        # Assume ON is in top 40%, OFF is in bottom 40%
        sorted_samples = sorted(self._baseline_samples)
        percentile_40 = int(len(sorted_samples) * 0.4)
        percentile_60 = int(len(sorted_samples) * 0.6)

        self._compressor_off_power = statistics.mean(sorted_samples[:percentile_40])
        self._compressor_on_power = statistics.mean(sorted_samples[percentile_60:])

        # Update sensors
        await self._update_baseline_sensors()

        # Mark learning complete
        self._learning_complete = True
        await self._update_learning_progress(100)
        await self._update_health_state(STATE_NORMAL)

        _LOGGER.info(
            "Learning complete for %s: baseline=%.1fW±%.1fW, ON=%.1fW, OFF=%.1fW",
            self._config[CONF_APPLIANCE_NAME],
            self._baseline_mean,
            self._baseline_stddev,
            self._compressor_on_power,
            self._compressor_off_power,
        )

    async def _process_monitoring_phase(self, current_power: float) -> None:
        """Process power reading during monitoring phase."""
        # Update compressor state
        await self._update_compressor_state(current_power)

        # Detect anomalies
        await self._detect_anomalies(current_power)

    async def _update_compressor_state(self, current_power: float) -> None:
        """Update compressor on/off state based on power."""
        threshold = self._config[CONF_COMPRESSOR_CYCLE_THRESHOLD]
        mid_power = (self._compressor_on_power + self._compressor_off_power) / 2

        was_on = self._compressor_is_on

        # Detect state change with hysteresis
        if not self._compressor_is_on and current_power > (mid_power + threshold / 2):
            # Compressor turned ON
            self._compressor_is_on = True
            self._last_compressor_on_time = dt_util.now()
            self._daily_cycles += 1
            await self._update_compressor_binary_sensor(True)
            await self._update_cycles_sensor()
            _LOGGER.debug("Compressor ON (power: %.1fW)", current_power)

        elif self._compressor_is_on and current_power < (mid_power - threshold / 2):
            # Compressor turned OFF
            self._compressor_is_on = False
            self._last_compressor_off_time = dt_util.now()
            await self._update_compressor_binary_sensor(False)
            _LOGGER.debug("Compressor OFF (power: %.1fW)", current_power)

    async def _detect_anomalies(self, current_power: float) -> None:
        """Detect anomalies in power consumption."""
        sensitivity = self._config[CONF_DOOR_OPEN_SENSITIVITY]
        grace_minutes = self._config[CONF_DOOR_GRACE_MINUTES]

        # 1. Door open detection (power spike)
        door_threshold = self._baseline_mean + (sensitivity * self._baseline_stddev)

        if current_power > door_threshold:
            if self._door_open_start is None:
                self._door_open_start = dt_util.now()

            # Check if grace period elapsed
            elapsed = (dt_util.now() - self._door_open_start).total_seconds() / 60
            if elapsed >= grace_minutes:
                if self._current_state != STATE_DOOR_OPEN:
                    await self._update_health_state(STATE_DOOR_OPEN)
                    await self._update_door_open_binary_sensor(True)
                    _LOGGER.warning(
                        "Door may be open: %.1fW > %.1fW (threshold)",
                        current_power,
                        door_threshold,
                    )
        else:
            # Power returned to normal
            if self._door_open_start is not None:
                self._door_open_start = None
                if self._current_state == STATE_DOOR_OPEN:
                    await self._update_health_state(STATE_NORMAL)
                    await self._update_door_open_binary_sensor(False)

        # 2. Compressor failure detection (low power or no cycles)
        if current_power < (self._baseline_mean * 0.3):
            if self._current_state != STATE_COMPRESSOR_FAILING:
                await self._update_health_state(STATE_COMPRESSOR_FAILING)
                _LOGGER.warning("Compressor may be failing: %.1fW is very low", current_power)

        # Check for no compressor cycles
        max_off_hours = self._config[CONF_MAX_COMPRESSOR_OFF_HOURS]
        if self._last_compressor_off_time:
            hours_since_cycle = (dt_util.now() - self._last_compressor_off_time).total_seconds() / 3600
            if hours_since_cycle > max_off_hours:
                if self._current_state != STATE_COMPRESSOR_FAILING:
                    await self._update_health_state(STATE_COMPRESSOR_FAILING)
                    _LOGGER.warning("No compressor cycles for %.1f hours", hours_since_cycle)

        # 3. Cycle anomaly detection
        expected_cycles = self._config[CONF_EXPECTED_DAILY_CYCLES]
        tolerance = self._config[CONF_CYCLE_ANOMALY_TOLERANCE] / 100

        if self._daily_cycles > 0:
            deviation = abs(self._daily_cycles - expected_cycles) / expected_cycles
            if deviation > tolerance:
                if self._current_state not in (STATE_DOOR_OPEN, STATE_COMPRESSOR_FAILING):
                    await self._update_health_state(STATE_CYCLE_ANOMALY)
                    _LOGGER.warning(
                        "Cycle anomaly: %d cycles (expected %d±%d%%)",
                        self._daily_cycles,
                        expected_cycles,
                        int(tolerance * 100),
                    )

        # If no anomalies, return to normal
        if self._current_state != STATE_NORMAL and current_power < door_threshold:
            if self._current_state in (STATE_POWER_SPIKE, STATE_CYCLE_ANOMALY):
                await self._update_health_state(STATE_NORMAL)

    async def _daily_reset(self, now: datetime) -> None:
        """Reset daily counters at midnight."""
        today = now.date()
        if today != self._last_cycle_reset:
            _LOGGER.info("Daily reset: %d cycles yesterday", self._daily_cycles)
            self._daily_cycles = 0
            self._last_cycle_reset = today
            await self._update_cycles_sensor()

    # Entity update methods
    def _get_entity_by_suffix(self, suffix: str):
        """Get entity by suffix."""
        unique_id = f"{self.entry.entry_id}_{suffix}"
        return self.hass.data[DOMAIN].get("entities", {}).get(unique_id)

    async def _update_health_state(self, new_state: str) -> None:
        """Update the health state sensor."""
        self._current_state = new_state

        # Update needs attention binary sensor
        needs_attention = new_state not in (STATE_NORMAL, STATE_INITIALIZING, STATE_OFFLINE)
        await self._update_needs_attention_binary_sensor(needs_attention)

        # Update health state sensor
        entity = self._get_entity_by_suffix(SUFFIX_HEALTH_STATE)
        if entity and hasattr(entity, "async_update_state"):
            await entity.async_update_state(new_state)

    async def _update_baseline_sensors(self) -> None:
        """Update baseline-related sensors."""
        # Update baseline average
        entity = self._get_entity_by_suffix(SUFFIX_BASELINE_AVERAGE)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._baseline_mean)

        # Update baseline stddev
        entity = self._get_entity_by_suffix(SUFFIX_BASELINE_STDDEV)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._baseline_stddev)

        # Update compressor ON power
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_ON_POWER)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._compressor_on_power)

        # Update compressor OFF power
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_OFF_POWER)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._compressor_off_power)

    async def _update_learning_progress(self, progress: int) -> None:
        """Update learning progress sensor."""
        entity = self._get_entity_by_suffix(SUFFIX_LEARNING_PROGRESS)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(progress)

    async def _update_compressor_binary_sensor(self, is_on: bool) -> None:
        """Update compressor state binary sensor."""
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_STATE)
        if entity and hasattr(entity, "async_update_state"):
            await entity.async_update_state(is_on)

    async def _update_door_open_binary_sensor(self, is_open: bool) -> None:
        """Update door open binary sensor."""
        entity = self._get_entity_by_suffix(SUFFIX_DOOR_OPEN)
        if entity and hasattr(entity, "async_update_state"):
            await entity.async_update_state(is_open)

    async def _update_needs_attention_binary_sensor(self, needs_attention: bool) -> None:
        """Update needs attention binary sensor."""
        entity = self._get_entity_by_suffix(SUFFIX_NEEDS_ATTENTION)
        if entity and hasattr(entity, "async_update_state"):
            await entity.async_update_state(needs_attention)

    async def _update_cycles_sensor(self) -> None:
        """Update daily cycles sensor."""
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_CYCLES)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._daily_cycles)
