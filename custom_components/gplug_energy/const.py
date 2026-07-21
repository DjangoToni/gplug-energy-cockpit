"""Constants for gPlug Energy Cockpit."""

DOMAIN = "gplug_energy"
NAME = "gPlug Energy Cockpit"
VERSION = "0.3.3"

CONF_NAME = "name"
CONF_SOURCE_DEVICE = "source_device"
CONF_NET_POWER = "net_power"
CONF_IMPORT_POWER = "import_power"
CONF_EXPORT_POWER = "export_power"
CONF_IMPORT_ENERGY = "import_energy"
CONF_EXPORT_ENERGY = "export_energy"
CONF_IMPORT_ENERGY_T1 = "import_energy_t1"
CONF_IMPORT_ENERGY_T2 = "import_energy_t2"
CONF_EXPORT_ENERGY_T1 = "export_energy_t1"
CONF_EXPORT_ENERGY_T2 = "export_energy_t2"
CONF_VOLTAGE_L1 = "voltage_l1"
CONF_VOLTAGE_L2 = "voltage_l2"
CONF_VOLTAGE_L3 = "voltage_l3"
CONF_CURRENT_L1 = "current_l1"
CONF_CURRENT_L2 = "current_l2"
CONF_CURRENT_L3 = "current_l3"
CONF_FREQUENCY = "frequency"
CONF_INVERTER_GRID_POWER = "inverter_grid_power"
CONF_INVERT_NET_POWER = "invert_net_power"
CONF_INVERT_INVERTER_POWER = "invert_inverter_power"
CONF_IMPORT_PRICE = "import_price"
CONF_EXPORT_PRICE = "export_price"
CONF_CURRENCY = "currency"
CONF_PERCENT_MINIMUM = "percent_minimum"

DEFAULT_NAME = "gPlug Energy Cockpit"
DEFAULT_IMPORT_PRICE = 0.0
DEFAULT_EXPORT_PRICE = 0.0
DEFAULT_CURRENCY = "CHF"
DEFAULT_PERCENT_MINIMUM = 200.0

ENTITY_CONFIG_KEYS = (
    CONF_NET_POWER,
    CONF_IMPORT_POWER,
    CONF_EXPORT_POWER,
    CONF_IMPORT_ENERGY,
    CONF_EXPORT_ENERGY,
    CONF_IMPORT_ENERGY_T1,
    CONF_IMPORT_ENERGY_T2,
    CONF_EXPORT_ENERGY_T1,
    CONF_EXPORT_ENERGY_T2,
    CONF_VOLTAGE_L1,
    CONF_VOLTAGE_L2,
    CONF_VOLTAGE_L3,
    CONF_CURRENT_L1,
    CONF_CURRENT_L2,
    CONF_CURRENT_L3,
    CONF_FREQUENCY,
    CONF_INVERTER_GRID_POWER,
)
