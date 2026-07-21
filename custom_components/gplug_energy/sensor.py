"""Sensor platform for gPlug Energy Cockpit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfFrequency, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CURRENT_L1, CONF_CURRENT_L2, CONF_CURRENT_L3,
    CONF_EXPORT_ENERGY, CONF_EXPORT_ENERGY_T1, CONF_EXPORT_ENERGY_T2,
    CONF_FREQUENCY, CONF_IMPORT_ENERGY, CONF_IMPORT_ENERGY_T1, CONF_IMPORT_ENERGY_T2,
    CONF_INVERTER_GRID_POWER, CONF_VOLTAGE_L1, CONF_VOLTAGE_L2, CONF_VOLTAGE_L3,
    DOMAIN, VERSION,
)
from .runtime import GPlugEnergyRuntime


@dataclass(frozen=True, kw_only=True)
class GPlugSensorDescription:
    key: str
    translation_key: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    icon: str | None = None
    precision: int | None = 1
    required: tuple[str, ...] = ()
    all_required: bool = False


SENSORS = (
    GPlugSensorDescription(key="meter_status", translation_key="meter_status", device_class=SensorDeviceClass.ENUM, state_class=None, icon="mdi:connection"),
    GPlugSensorDescription(key="net_power", translation_key="net_power", unit=UnitOfPower.KILO_WATT, device_class=SensorDeviceClass.POWER, icon="mdi:transmission-tower", precision=3),
    GPlugSensorDescription(key="import_power", translation_key="import_power", unit=UnitOfPower.KILO_WATT, device_class=SensorDeviceClass.POWER, icon="mdi:transmission-tower-import", precision=3),
    GPlugSensorDescription(key="export_power", translation_key="export_power", unit=UnitOfPower.KILO_WATT, device_class=SensorDeviceClass.POWER, icon="mdi:transmission-tower-export", precision=3),
    GPlugSensorDescription(key="import_today", translation_key="import_today", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL, icon="mdi:home-import-outline", precision=3),
    GPlugSensorDescription(key="export_today", translation_key="export_today", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL, icon="mdi:home-export-outline", precision=3),
    GPlugSensorDescription(key="import_cost_today", translation_key="import_cost_today", device_class=SensorDeviceClass.MONETARY, state_class=SensorStateClass.TOTAL, icon="mdi:cash", precision=2),
    GPlugSensorDescription(key="export_revenue_today", translation_key="export_revenue_today", device_class=SensorDeviceClass.MONETARY, state_class=SensorStateClass.TOTAL, icon="mdi:cash-plus", precision=2),
    GPlugSensorDescription(key="net_cost_today", translation_key="net_cost_today", device_class=SensorDeviceClass.MONETARY, state_class=SensorStateClass.TOTAL, icon="mdi:cash-sync", precision=2),
    GPlugSensorDescription(key="peak_import_today", translation_key="peak_import_today", unit=UnitOfPower.KILO_WATT, device_class=SensorDeviceClass.POWER, icon="mdi:chart-line-variant", precision=3),
    GPlugSensorDescription(key="peak_export_today", translation_key="peak_export_today", unit=UnitOfPower.KILO_WATT, device_class=SensorDeviceClass.POWER, icon="mdi:chart-line-variant", precision=3),
    GPlugSensorDescription(key="data_age", translation_key="data_age", unit=UnitOfTime.SECONDS, device_class=SensorDeviceClass.DURATION, icon="mdi:update", precision=0),
    GPlugSensorDescription(key="import_energy_total", translation_key="import_energy_total", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, required=(CONF_IMPORT_ENERGY,), precision=3),
    GPlugSensorDescription(key="export_energy_total", translation_key="export_energy_total", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, required=(CONF_EXPORT_ENERGY,), precision=3),
    GPlugSensorDescription(key="import_energy_t1", translation_key="import_energy_t1", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, required=(CONF_IMPORT_ENERGY_T1,), precision=3),
    GPlugSensorDescription(key="import_energy_t2", translation_key="import_energy_t2", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, required=(CONF_IMPORT_ENERGY_T2,), precision=3),
    GPlugSensorDescription(key="export_energy_t1", translation_key="export_energy_t1", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, required=(CONF_EXPORT_ENERGY_T1,), precision=3),
    GPlugSensorDescription(key="export_energy_t2", translation_key="export_energy_t2", unit=UnitOfEnergy.KILO_WATT_HOUR, device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING, required=(CONF_EXPORT_ENERGY_T2,), precision=3),
    GPlugSensorDescription(key="voltage_l1", translation_key="voltage_l1", unit=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, required=(CONF_VOLTAGE_L1,)),
    GPlugSensorDescription(key="voltage_l2", translation_key="voltage_l2", unit=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, required=(CONF_VOLTAGE_L2,)),
    GPlugSensorDescription(key="voltage_l3", translation_key="voltage_l3", unit=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, required=(CONF_VOLTAGE_L3,)),
    GPlugSensorDescription(key="current_l1", translation_key="current_l1", unit=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, required=(CONF_CURRENT_L1,)),
    GPlugSensorDescription(key="current_l2", translation_key="current_l2", unit=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, required=(CONF_CURRENT_L2,)),
    GPlugSensorDescription(key="current_l3", translation_key="current_l3", unit=UnitOfElectricCurrent.AMPERE, device_class=SensorDeviceClass.CURRENT, required=(CONF_CURRENT_L3,)),
    GPlugSensorDescription(key="frequency", translation_key="frequency", unit=UnitOfFrequency.HERTZ, device_class=SensorDeviceClass.FREQUENCY, required=(CONF_FREQUENCY,), precision=2),
    GPlugSensorDescription(key="voltage_imbalance", translation_key="voltage_imbalance", unit=PERCENTAGE, icon="mdi:sine-wave", required=(CONF_VOLTAGE_L1, CONF_VOLTAGE_L2, CONF_VOLTAGE_L3), all_required=True, precision=2),
    GPlugSensorDescription(key="inverter_grid_power", translation_key="inverter_grid_power", unit=UnitOfPower.KILO_WATT, device_class=SensorDeviceClass.POWER, icon="mdi:solar-power", required=(CONF_INVERTER_GRID_POWER,), precision=3),
    GPlugSensorDescription(key="inverter_difference", translation_key="inverter_difference", unit=UnitOfPower.KILO_WATT, device_class=SensorDeviceClass.POWER, icon="mdi:delta", required=(CONF_INVERTER_GRID_POWER,), precision=3),
    GPlugSensorDescription(key="inverter_absolute_difference", translation_key="inverter_absolute_difference", unit=UnitOfPower.KILO_WATT, device_class=SensorDeviceClass.POWER, icon="mdi:arrow-expand-horizontal", required=(CONF_INVERTER_GRID_POWER,), precision=3),
    GPlugSensorDescription(key="inverter_agreement", translation_key="inverter_agreement", unit=PERCENTAGE, icon="mdi:check-decagram", required=(CONF_INVERTER_GRID_POWER,)),
)

DAILY_TOTAL_KEYS = {"import_today", "export_today", "import_cost_today", "export_revenue_today", "net_cost_today"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime: GPlugEnergyRuntime = hass.data[DOMAIN][entry.entry_id]
    descriptions = [description for description in SENSORS if _supported(entry, description)]
    async_add_entities(GPlugEnergySensor(entry, runtime, description) for description in descriptions)


def _supported(entry: ConfigEntry, description: GPlugSensorDescription) -> bool:
    if not description.required:
        return True
    config = {**entry.data, **entry.options}
    checks = [bool(config.get(key)) for key in description.required]
    return all(checks) if description.all_required else any(checks)


class GPlugEnergySensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, runtime: GPlugEnergyRuntime, description: GPlugSensorDescription) -> None:
        self._entry = entry
        self._runtime = runtime
        self._description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_native_unit_of_measurement = runtime.currency() if description.device_class == SensorDeviceClass.MONETARY else description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_icon = description.icon
        self._attr_suggested_display_precision = description.precision
        if description.key == "meter_status":
            self._attr_options = ["online", "stale"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="gPlug Energy Cockpit",
            model="Smart meter dashboard",
            sw_version=VERSION,
            configuration_url="https://gplug.ch/",
        )

    @property
    def available(self) -> bool:
        return self._runtime.is_available(self._description.key)

    @property
    def native_value(self) -> float | str | None:
        value = self._runtime.get_value(self._description.key)
        if isinstance(value, float) and self._description.precision is not None:
            return round(value, self._description.precision)
        return value

    @property
    def last_reset(self) -> datetime | None:
        return self._runtime.day_start() if self._description.key in DAILY_TOTAL_KEYS else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return self._runtime.attributes(self._description.key)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
