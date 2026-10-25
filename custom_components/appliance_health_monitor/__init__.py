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
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

STORAGE_VERSION = 1
# Saved state without this marker predates timer-based sampling. Its samples were only
# taken on state changes, which skipped steady readings (e.g. an idle 0W) and biased
# the learned baseline, so it is discarded.
SAMPLING_VERSION = 2
STORAGE_KEY_PREFIX = "appliance_health_monitor"

from .const import (
    APPLIANCE_SMART_DEFAULTS,
    CONF_APPLIANCE_NAME,
    CONF_APPLIANCE_TYPE,
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
    LEARNING_SAMPLE_INTERVAL_SECONDS,
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

        # Get smart defaults for this appliance type
        appliance_type = self._config.get(CONF_APPLIANCE_TYPE, "custom")
        defaults = APPLIANCE_SMART_DEFAULTS.get(appliance_type, APPLIANCE_SMART_DEFAULTS["custom"])

        # Learning phase tracking
        self._baseline_samples: list[float] = []
        self._learning_start_time: datetime | None = None
        self._learning_complete = False

        # Default values (used during learning, replaced after learning completes)
        self._default_baseline_mean = defaults["baseline_mean"]
        self._default_baseline_stddev = defaults["baseline_stddev"]
        self._default_compressor_on_power = defaults["compressor_on_power"]
        self._default_compressor_off_power = defaults["compressor_off_power"]

        # Learned values (0.0 until learning completes)
        self._learned_baseline_mean = 0.0
        self._learned_baseline_stddev = 0.0
        self._learned_compressor_on_power = 0.0
        self._learned_compressor_off_power = 0.0

        # Compressor cycle tracking
        self._compressor_is_on = False
        self._last_compressor_on_time: datetime | None = None
        self._last_compressor_off_time: datetime | None = None
        self._daily_cycles = 0
        self._last_cycle_reset = dt_util.now().date()

        # Anomaly detection state
        self._door_open_start: datetime | None = None
        self._current_state = STATE_NORMAL  # Start with NORMAL, not INITIALIZING

        # Event listeners
        self._unsub_power_listener = None
        self._unsub_daily_reset = None
        self._unsub_stop_listener = None
        self._unsub_sample_timer = None

        # Latest valid power reading, used by the periodic sample timer
        self._last_power: float | None = None
        self._low_power_since: datetime | None = None

        # Persistent storage
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{entry.entry_id}",
        )
        self._last_save_sample_count = 0

    # Helper methods to get current baseline values (defaults or learned)
    def _get_baseline_mean(self) -> float:
        """Get current baseline mean (default or learned)."""
        if self._learning_complete:
            return self._learned_baseline_mean
        return self._default_baseline_mean

    def _get_baseline_stddev(self) -> float:
        """Get current baseline stddev (default or learned)."""
        if self._learning_complete:
            return self._learned_baseline_stddev
        return self._default_baseline_stddev

    def _get_compressor_on_power(self) -> float:
        """Get current compressor ON power (default or learned)."""
        if self._learning_complete:
            return self._learned_compressor_on_power
        return self._default_compressor_on_power

    def _get_compressor_off_power(self) -> float:
        """Get current compressor OFF power (default or learned)."""
        if self._learning_complete:
            return self._learned_compressor_off_power
        return self._default_compressor_off_power

    async def _async_save_state(self) -> None:
        """Save learning state to persistent storage."""
        data = {
            "sampling_version": SAMPLING_VERSION,
            "learning_start_time": self._learning_start_time.isoformat() if self._learning_start_time else None,
            "learning_complete": self._learning_complete,
            "baseline_samples": self._baseline_samples,
            "learned_baseline_mean": self._learned_baseline_mean,
            "learned_baseline_stddev": self._learned_baseline_stddev,
            "learned_compressor_on_power": self._learned_compressor_on_power,
            "learned_compressor_off_power": self._learned_compressor_off_power,
        }
        await self._store.async_save(data)
        self._last_save_sample_count = len(self._baseline_samples)
        _LOGGER.debug(
            "State saved for %s: %d samples, learning_complete=%s",
            self._config[CONF_APPLIANCE_NAME],
            len(self._baseline_samples),
            self._learning_complete,
        )

    async def _async_restore_state(self) -> bool:
        """Restore learning state from persistent storage. Returns True if state was restored."""
        data = await self._store.async_load()
        if data is None:
            _LOGGER.debug("No saved state found for %s", self._config[CONF_APPLIANCE_NAME])
            return False

        if data.get("sampling_version") != SAMPLING_VERSION:
            _LOGGER.info(
                "Discarding learning state for %s saved by an older version, restarting learning",
                self._config[CONF_APPLIANCE_NAME],
            )
            return False

        # Restore learning start time
        if data.get("learning_start_time"):
            try:
                self._learning_start_time = datetime.fromisoformat(data["learning_start_time"])
            except (ValueError, TypeError):
                self._learning_start_time = None

        # Restore learning state
        self._learning_complete = data.get("learning_complete", False)
        self._baseline_samples = data.get("baseline_samples", [])
        self._last_save_sample_count = len(self._baseline_samples)

        # Restore learned values
        self._learned_baseline_mean = data.get("learned_baseline_mean", 0.0)
        self._learned_baseline_stddev = data.get("learned_baseline_stddev", 0.0)
        self._learned_compressor_on_power = data.get("learned_compressor_on_power", 0.0)
        self._learned_compressor_off_power = data.get("learned_compressor_off_power", 0.0)

        _LOGGER.info(
            "State restored for %s: %d samples, learning_complete=%s",
            self._config[CONF_APPLIANCE_NAME],
            len(self._baseline_samples),
            self._learning_complete,
        )
        return True

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
            self._daily_reset,
            timedelta(hours=24),
        )

        # Subscribe to HA stop event
        self._unsub_stop_listener = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP,
            self._async_stop,
        )

        # Try to restore saved state
        state_restored = await self._async_restore_state()

        if state_restored and self._learning_complete:
            # Learning was already complete - use learned values
            await self._update_health_state(STATE_NORMAL)
            await self._update_baseline_sensors()
            await self._update_learning_progress(100)
            _LOGGER.info(
                "Monitoring started for %s (using learned values: baseline=%.1fW±%.1fW, ON=%.1fW, OFF=%.1fW)",
                self._config[CONF_APPLIANCE_NAME],
                self._learned_baseline_mean,
                self._learned_baseline_stddev,
                self._learned_compressor_on_power,
                self._learned_compressor_off_power,
            )
        elif state_restored and self._learning_start_time:
            # Learning in progress - restore progress and continue with defaults
            learning_hours = self._config[CONF_LEARNING_PERIOD_HOURS]
            elapsed_hours = (dt_util.now() - self._learning_start_time).total_seconds() / 3600
            progress = min(100, int((elapsed_hours / learning_hours) * 100))
            await self._update_health_state(STATE_NORMAL)
            await self._update_baseline_sensors_with_defaults()
            await self._update_learning_progress(progress)
            _LOGGER.info(
                "Monitoring resumed for %s (learning %d%% complete with %d samples, using smart defaults)",
                self._config[CONF_APPLIANCE_NAME],
                progress,
                len(self._baseline_samples),
            )
        else:
            # Fresh start - initialize with smart defaults
            self._learning_start_time = dt_util.now()
            await self._update_health_state(STATE_NORMAL)
            await self._update_baseline_sensors_with_defaults()
            await self._update_learning_progress(0)
            # Save now so the start time survives a crash before the first periodic save
            await self._async_save_state()
            _LOGGER.info(
                "Monitoring started for %s (using smart defaults: baseline=%.1fW±%.1fW, ON=%.1fW, OFF=%.1fW)",
                self._config[CONF_APPLIANCE_NAME],
                self._default_baseline_mean,
                self._default_baseline_stddev,
                self._default_compressor_on_power,
                self._default_compressor_off_power,
            )

        # Seed the latest reading, then sample on a timer. State change events
        # are not fired for steady readings, so they alone would under-sample
        # periods like an appliance sitting idle at a constant 0W.
        power_state = self.hass.states.get(self._power_sensor)
        if power_state is not None:
            try:
                self._last_power = float(power_state.state)
            except (ValueError, TypeError):
                self._last_power = None
        self._unsub_sample_timer = async_track_time_interval(
            self.hass,
            self._async_sample_tick,
            timedelta(seconds=LEARNING_SAMPLE_INTERVAL_SECONDS),
        )

    async def async_stop(self) -> None:
        """Stop monitoring."""
        # Save state before stopping
        await self._async_save_state()

        if self._unsub_power_listener:
            self._unsub_power_listener()
            self._unsub_power_listener = None
        if self._unsub_daily_reset:
            self._unsub_daily_reset()
            self._unsub_daily_reset = None
        if self._unsub_stop_listener:
            self._unsub_stop_listener()
            self._unsub_stop_listener = None
        if self._unsub_sample_timer:
            self._unsub_sample_timer()
            self._unsub_sample_timer = None

        _LOGGER.info("Monitoring stopped for %s", self._config[CONF_APPLIANCE_NAME])

    async def _async_stop(self, event: Event) -> None:
        """Handle HA stop event."""
        # listen_once has already removed this listener; don't unsubscribe it again
        self._unsub_stop_listener = None
        await self.async_stop()

    @callback
    async def _async_power_sensor_changed(self, event: Event) -> None:
        """Handle power sensor state change."""
        new_state = event.data.get("new_state")

        # Handle sensor unavailable
        if new_state is None or new_state.state in ("unavailable", "unknown"):
            self._last_power = None
            await self._update_health_state(STATE_OFFLINE)
            return

        try:
            current_power = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid power value: %s", new_state.state)
            return

        self._last_power = current_power

        # Learning samples are collected by the sample timer, not here
        # Always monitor with current values (defaults or learned)
        await self._process_monitoring_phase(current_power)

    async def _async_sample_tick(self, now: datetime) -> None:
        """Sample the latest reading and re-run checks that must not depend on sensor changes."""
        if self._last_power is None:
            return

        if not self._learning_complete:
            await self._process_learning_phase(self._last_power)

        await self._detect_anomalies(self._last_power)

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

        # Periodically save state during learning (every 50 new samples)
        samples_since_save = len(self._baseline_samples) - self._last_save_sample_count
        if samples_since_save >= 50:
            await self._async_save_state()

        # Check if learning is complete
        if elapsed_hours >= learning_hours:
            await self._complete_learning()

    async def _complete_learning(self) -> None:
        """Complete the learning phase and calculate baselines."""
        if len(self._baseline_samples) < 10:
            _LOGGER.warning("Not enough samples collected (%d), extending learning", len(self._baseline_samples))
            return

        # Calculate learned baseline statistics
        self._learned_baseline_mean = statistics.mean(self._baseline_samples)
        self._learned_baseline_stddev = statistics.stdev(self._baseline_samples) if len(self._baseline_samples) > 1 else 0.0

        # Detect compressor ON/OFF power levels
        # Assume ON is in top 40%, OFF is in bottom 40%
        sorted_samples = sorted(self._baseline_samples)
        percentile_40 = int(len(sorted_samples) * 0.4)
        percentile_60 = int(len(sorted_samples) * 0.6)

        self._learned_compressor_off_power = statistics.mean(sorted_samples[:percentile_40])
        self._learned_compressor_on_power = statistics.mean(sorted_samples[percentile_60:])

        # Update sensors with learned values
        await self._update_baseline_sensors()

        # Mark learning complete
        self._learning_complete = True
        await self._update_learning_progress(100)

        _LOGGER.info(
            "Learning complete for %s - switching from defaults to learned values:",
            self._config[CONF_APPLIANCE_NAME],
        )
        _LOGGER.info(
            "  Baseline: %.1fW±%.1fW (was %.1fW±%.1fW)",
            self._learned_baseline_mean,
            self._learned_baseline_stddev,
            self._default_baseline_mean,
            self._default_baseline_stddev,
        )
        _LOGGER.info(
            "  Compressor ON: %.1fW (was %.1fW), OFF: %.1fW (was %.1fW)",
            self._learned_compressor_on_power,
            self._default_compressor_on_power,
            self._learned_compressor_off_power,
            self._default_compressor_off_power,
        )

        # Save state now that learning is complete
        await self._async_save_state()

    async def _process_monitoring_phase(self, current_power: float) -> None:
        """Process power reading during monitoring phase."""
        # Update compressor state
        await self._update_compressor_state(current_power)

        # Detect anomalies
        await self._detect_anomalies(current_power)

    async def _update_compressor_state(self, current_power: float) -> None:
        """Update compressor on/off state based on power."""
        threshold = self._config[CONF_COMPRESSOR_CYCLE_THRESHOLD]

        # Use current baseline values (defaults or learned)
        compressor_on = self._get_compressor_on_power()
        compressor_off = self._get_compressor_off_power()
        mid_power = (compressor_on + compressor_off) / 2

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

        # Use current baseline values (defaults or learned)
        baseline_mean = self._get_baseline_mean()
        baseline_stddev = self._get_baseline_stddev()

        # 1. Door open detection (power spike)
        door_threshold = baseline_mean + (sensitivity * baseline_stddev)

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
        # Low power is only a failure if it lasts longer than the max off time,
        # since an idle reading near 0W is normal between cycles. It is skipped
        # while learning: the smart defaults are too generic to judge "very low".
        max_off_hours = self._config[CONF_MAX_COMPRESSOR_OFF_HOURS]
        low_power = False
        if self._learning_complete and current_power < (baseline_mean * 0.3):
            if self._low_power_since is None:
                self._low_power_since = dt_util.now()
            low_hours = (dt_util.now() - self._low_power_since).total_seconds() / 3600
            if low_hours > max_off_hours:
                low_power = True
                if self._current_state != STATE_COMPRESSOR_FAILING:
                    await self._update_health_state(STATE_COMPRESSOR_FAILING)
                    _LOGGER.warning(
                        "Compressor may be failing: %.1fW has been very low for %.1f hours",
                        current_power,
                        low_hours,
                    )
        else:
            self._low_power_since = None

        # Check for no compressor cycles
        no_cycles = False
        if self._last_compressor_off_time:
            hours_since_cycle = (dt_util.now() - self._last_compressor_off_time).total_seconds() / 3600
            if hours_since_cycle > max_off_hours:
                no_cycles = True
                if self._current_state != STATE_COMPRESSOR_FAILING:
                    await self._update_health_state(STATE_COMPRESSOR_FAILING)
                    _LOGGER.warning("No compressor cycles for %.1f hours", hours_since_cycle)

        # Recover once neither failure condition holds any more
        if self._current_state == STATE_COMPRESSOR_FAILING and not (low_power or no_cycles):
            await self._update_health_state(STATE_NORMAL)
            _LOGGER.info("Compressor failure condition cleared for %s", self._config[CONF_APPLIANCE_NAME])

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

    async def _update_baseline_sensors_with_defaults(self) -> None:
        """Update baseline sensors with default values on startup."""
        # Update baseline average
        entity = self._get_entity_by_suffix(SUFFIX_BASELINE_AVERAGE)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._default_baseline_mean)

        # Update baseline stddev
        entity = self._get_entity_by_suffix(SUFFIX_BASELINE_STDDEV)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._default_baseline_stddev)

        # Update compressor ON power
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_ON_POWER)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._default_compressor_on_power)

        # Update compressor OFF power
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_OFF_POWER)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._default_compressor_off_power)

    async def _update_baseline_sensors(self) -> None:
        """Update baseline-related sensors with learned values."""
        # Update baseline average
        entity = self._get_entity_by_suffix(SUFFIX_BASELINE_AVERAGE)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._learned_baseline_mean)

        # Update baseline stddev
        entity = self._get_entity_by_suffix(SUFFIX_BASELINE_STDDEV)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._learned_baseline_stddev)

        # Update compressor ON power
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_ON_POWER)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._learned_compressor_on_power)

        # Update compressor OFF power
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_OFF_POWER)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(self._learned_compressor_off_power)

    async def _update_learning_progress(self, progress: int) -> None:
        """Update learning progress sensor."""
        entity = self._get_entity_by_suffix(SUFFIX_LEARNING_PROGRESS)
        if entity and hasattr(entity, "async_update_value"):
            await entity.async_update_value(progress)

    async def _update_compressor_binary_sensor(self, is_on: bool) -> None:
        """Update compressor state binary sensor."""
        entity = self._get_entity_by_suffix(SUFFIX_COMPRESSOR_STATE)
        if entity and hasattr(entity, "async_update_state"):
            await entity.async_update_state(is_on, learning=not self._learning_complete)

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
