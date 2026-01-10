"""Constants for the Appliance Health Monitor integration."""

DOMAIN = "appliance_health_monitor"

# Config flow constants
CONF_APPLIANCE_NAME = "appliance_name"
CONF_APPLIANCE_TYPE = "appliance_type"
CONF_POWER_SENSOR = "power_sensor"
CONF_LEARNING_PERIOD_HOURS = "learning_period_hours"
CONF_DOOR_OPEN_SENSITIVITY = "door_open_sensitivity"
CONF_DOOR_GRACE_MINUTES = "door_grace_minutes"
CONF_COMPRESSOR_CYCLE_THRESHOLD = "compressor_cycle_threshold"
CONF_MAX_COMPRESSOR_OFF_HOURS = "max_compressor_off_hours"
CONF_BASELINE_DRIFT_THRESHOLD = "baseline_drift_threshold"
CONF_EXPECTED_DAILY_CYCLES = "expected_daily_cycles"
CONF_CYCLE_ANOMALY_TOLERANCE = "cycle_anomaly_tolerance"

# Appliance types
APPLIANCE_TYPE_REFRIGERATOR = "refrigerator"
APPLIANCE_TYPE_FREEZER = "freezer"
APPLIANCE_TYPE_HVAC = "hvac"
APPLIANCE_TYPE_SUMP_PUMP = "sump_pump"
APPLIANCE_TYPE_CUSTOM = "custom"

APPLIANCE_TYPES = [
    APPLIANCE_TYPE_REFRIGERATOR,
    APPLIANCE_TYPE_FREEZER,
    APPLIANCE_TYPE_HVAC,
    APPLIANCE_TYPE_SUMP_PUMP,
    APPLIANCE_TYPE_CUSTOM,
]

# Health states
STATE_OFFLINE = "offline"
STATE_INITIALIZING = "initializing"
STATE_NORMAL = "normal"
STATE_DOOR_OPEN = "door_open"
STATE_COMPRESSOR_FAILING = "compressor_failing"
STATE_BASELINE_DRIFT_HIGH = "baseline_drift_high"
STATE_BASELINE_DRIFT_LOW = "baseline_drift_low"
STATE_CYCLE_ANOMALY = "cycle_anomaly"
STATE_POWER_SPIKE = "power_spike"

HEALTH_STATES = [
    STATE_OFFLINE,
    STATE_INITIALIZING,
    STATE_NORMAL,
    STATE_DOOR_OPEN,
    STATE_COMPRESSOR_FAILING,
    STATE_BASELINE_DRIFT_HIGH,
    STATE_BASELINE_DRIFT_LOW,
    STATE_CYCLE_ANOMALY,
    STATE_POWER_SPIKE,
]

# Default values
DEFAULT_LEARNING_PERIOD = 48  # hours
DEFAULT_DOOR_SENSITIVITY = 2.5  # standard deviations
DEFAULT_DOOR_GRACE_PERIOD = 3  # minutes
DEFAULT_COMPRESSOR_THRESHOLD = 30  # watts
DEFAULT_MAX_COMPRESSOR_OFF = 4  # hours
DEFAULT_DRIFT_THRESHOLD = 15  # percent
DEFAULT_EXPECTED_CYCLES = 30  # per day
DEFAULT_CYCLE_TOLERANCE = 50  # percent

# Appliance type presets
APPLIANCE_PRESETS = {
    APPLIANCE_TYPE_REFRIGERATOR: {
        CONF_EXPECTED_DAILY_CYCLES: 30,
        CONF_COMPRESSOR_CYCLE_THRESHOLD: 30,
    },
    APPLIANCE_TYPE_FREEZER: {
        CONF_EXPECTED_DAILY_CYCLES: 20,
        CONF_COMPRESSOR_CYCLE_THRESHOLD: 25,
    },
    APPLIANCE_TYPE_HVAC: {
        CONF_EXPECTED_DAILY_CYCLES: 15,
        CONF_COMPRESSOR_CYCLE_THRESHOLD: 50,
    },
    APPLIANCE_TYPE_SUMP_PUMP: {
        CONF_EXPECTED_DAILY_CYCLES: 5,  # Pumps run less frequently, depends on water table
        CONF_COMPRESSOR_CYCLE_THRESHOLD: 100,  # Higher power draw when pump motor runs
        CONF_MAX_COMPRESSOR_OFF_HOURS: 168,  # 7 days - alert if no activity in a week
        CONF_LEARNING_PERIOD_HOURS: 168,  # 7 days - need longer learning for infrequent cycles
    },
    APPLIANCE_TYPE_CUSTOM: {},
}

# Entity suffixes
SUFFIX_HEALTH_STATE = "health_state"
SUFFIX_BASELINE_AVERAGE = "baseline_average"
SUFFIX_BASELINE_STDDEV = "baseline_stddev"
SUFFIX_COMPRESSOR_ON_POWER = "compressor_on_power"
SUFFIX_COMPRESSOR_OFF_POWER = "compressor_off_power"
SUFFIX_COMPRESSOR_CYCLES = "compressor_cycles"
SUFFIX_LEARNING_PROGRESS = "learning_progress"
SUFFIX_DOOR_OPEN = "door_open"
SUFFIX_NEEDS_ATTENTION = "needs_attention"
SUFFIX_COMPRESSOR_STATE = "compressor_state"

# Services
SERVICE_RESET_BASELINE = "reset_baseline"
SERVICE_FORCE_STATE = "force_state"
SERVICE_RESET_COUNTERS = "reset_counters"

# Attributes
ATTR_BASELINE_MEAN = "baseline_mean"
ATTR_BASELINE_STDDEV = "baseline_stddev"
ATTR_COMPRESSOR_ON_POWER = "compressor_on_power"
ATTR_COMPRESSOR_OFF_POWER = "compressor_off_power"
ATTR_LEARNING_PROGRESS = "learning_progress"
ATTR_SAMPLES_COLLECTED = "samples_collected"
ATTR_LAST_CYCLE_TIME = "last_cycle_time"
ATTR_DAILY_CYCLES = "daily_cycles"
