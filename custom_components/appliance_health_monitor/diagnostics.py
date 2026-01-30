"""Diagnostics support for Appliance Health Monitor."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")

    now = dt_util.now()

    # Build diagnostics
    diagnostics: dict[str, Any] = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": _get_coordinator_diagnostics(coordinator, now),
        "power_sensor": _get_power_sensor_diagnostics(hass, coordinator),
        "entities": _get_entity_diagnostics(hass, entry.entry_id),
        "diagnostics_generated_at": now.isoformat(),
    }

    return diagnostics


def _get_coordinator_diagnostics(
    coordinator: Any, now: datetime
) -> dict[str, Any]:
    """Get coordinator internal state."""
    if coordinator is None:
        return {"error": "Coordinator not found"}

    # Calculate learning timing info
    learning_start = coordinator._learning_start_time
    learning_hours_configured = coordinator._config.get("learning_period_hours", 0)

    elapsed_hours = None
    elapsed_seconds = None
    progress_expected = None
    time_remaining_hours = None

    if learning_start is not None:
        elapsed_seconds = (now - learning_start).total_seconds()
        elapsed_hours = elapsed_seconds / 3600
        if learning_hours_configured > 0:
            progress_expected = min(100, int((elapsed_hours / learning_hours_configured) * 100))
            time_remaining_hours = max(0, learning_hours_configured - elapsed_hours)

    # Calculate sample rate
    sample_count = len(coordinator._baseline_samples)
    samples_per_hour = None
    if elapsed_hours and elapsed_hours > 0:
        samples_per_hour = sample_count / elapsed_hours

    # Sample statistics (if any samples collected)
    sample_stats = None
    if sample_count > 0:
        samples = coordinator._baseline_samples
        sample_stats = {
            "count": sample_count,
            "min": round(min(samples), 2),
            "max": round(max(samples), 2),
            "first_10": [round(s, 2) for s in samples[:10]],
            "last_10": [round(s, 2) for s in samples[-10:]],
        }
        if sample_count > 1:
            import statistics
            sample_stats["mean"] = round(statistics.mean(samples), 2)
            sample_stats["stdev"] = round(statistics.stdev(samples), 2)

    return {
        "learning": {
            "is_complete": coordinator._learning_complete,
            "start_time": learning_start.isoformat() if learning_start else None,
            "configured_hours": learning_hours_configured,
            "elapsed_hours": round(elapsed_hours, 2) if elapsed_hours else None,
            "elapsed_seconds": round(elapsed_seconds, 1) if elapsed_seconds else None,
            "expected_progress_percent": progress_expected,
            "time_remaining_hours": round(time_remaining_hours, 2) if time_remaining_hours else None,
            "minimum_samples_required": 10,
        },
        "samples": sample_stats,
        "samples_per_hour": round(samples_per_hour, 2) if samples_per_hour else None,
        "default_values": {
            "baseline_mean": coordinator._default_baseline_mean,
            "baseline_stddev": coordinator._default_baseline_stddev,
            "compressor_on_power": coordinator._default_compressor_on_power,
            "compressor_off_power": coordinator._default_compressor_off_power,
        },
        "learned_values": {
            "baseline_mean": coordinator._learned_baseline_mean,
            "baseline_stddev": coordinator._learned_baseline_stddev,
            "compressor_on_power": coordinator._learned_compressor_on_power,
            "compressor_off_power": coordinator._learned_compressor_off_power,
        },
        "current_state": {
            "health_state": coordinator._current_state,
            "compressor_is_on": coordinator._compressor_is_on,
            "daily_cycles": coordinator._daily_cycles,
            "last_cycle_reset": coordinator._last_cycle_reset.isoformat() if coordinator._last_cycle_reset else None,
            "last_compressor_on_time": coordinator._last_compressor_on_time.isoformat() if coordinator._last_compressor_on_time else None,
            "last_compressor_off_time": coordinator._last_compressor_off_time.isoformat() if coordinator._last_compressor_off_time else None,
            "door_open_start": coordinator._door_open_start.isoformat() if coordinator._door_open_start else None,
        },
        "listeners_active": {
            "power_listener": coordinator._unsub_power_listener is not None,
            "daily_reset": coordinator._unsub_daily_reset is not None,
            "stop_listener": coordinator._unsub_stop_listener is not None,
        },
    }


def _get_power_sensor_diagnostics(hass: HomeAssistant, coordinator: Any) -> dict[str, Any]:
    """Get power sensor state and info."""
    if coordinator is None:
        return {"error": "Coordinator not found"}

    power_sensor_id = coordinator._power_sensor
    state = hass.states.get(power_sensor_id)

    if state is None:
        return {
            "entity_id": power_sensor_id,
            "error": "Entity not found in state machine",
            "possible_causes": [
                "Entity ID is incorrect",
                "The sensor integration is not loaded",
                "The sensor was removed",
            ],
        }

    return {
        "entity_id": power_sensor_id,
        "state": state.state,
        "last_changed": state.last_changed.isoformat() if state.last_changed else None,
        "last_updated": state.last_updated.isoformat() if state.last_updated else None,
        "attributes": dict(state.attributes),
        "is_available": state.state not in ("unavailable", "unknown"),
    }


def _get_entity_diagnostics(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    """Get all entity states for this config entry."""
    suffixes = [
        SUFFIX_HEALTH_STATE,
        SUFFIX_LEARNING_PROGRESS,
        SUFFIX_BASELINE_AVERAGE,
        SUFFIX_BASELINE_STDDEV,
        SUFFIX_COMPRESSOR_ON_POWER,
        SUFFIX_COMPRESSOR_OFF_POWER,
        SUFFIX_COMPRESSOR_CYCLES,
        SUFFIX_DOOR_OPEN,
        SUFFIX_NEEDS_ATTENTION,
        SUFFIX_COMPRESSOR_STATE,
    ]

    entities = {}
    for suffix in suffixes:
        # Try sensor first, then binary_sensor
        for platform in ("sensor", "binary_sensor"):
            entity_id = f"{platform}.{entry_id}_{suffix}"
            state = hass.states.get(entity_id)
            if state is not None:
                entities[suffix] = {
                    "entity_id": entity_id,
                    "state": state.state,
                    "last_changed": state.last_changed.isoformat() if state.last_changed else None,
                    "last_updated": state.last_updated.isoformat() if state.last_updated else None,
                    "attributes": dict(state.attributes),
                }
                break
        else:
            entities[suffix] = {"error": f"Entity not found for suffix: {suffix}"}

    return entities
