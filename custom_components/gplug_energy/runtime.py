"""Runtime data model for gPlug Energy Cockpit."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .calculations import energy_in_kwh, percentage_difference, power_in_watts, scaled_value
from .const import (
    CONF_CURRENCY,
    CONF_CURRENT_L1,
    CONF_CURRENT_L2,
    CONF_CURRENT_L3,
    CONF_EXPORT_ENERGY,
    CONF_EXPORT_ENERGY_T1,
    CONF_EXPORT_ENERGY_T2,
    CONF_EXPORT_POWER,
    CONF_EXPORT_PRICE,
    CONF_FREQUENCY,
    CONF_IMPORT_ENERGY,
    CONF_IMPORT_ENERGY_T1,
    CONF_IMPORT_ENERGY_T2,
    CONF_IMPORT_POWER,
    CONF_IMPORT_PRICE,
    CONF_INVERTER_GRID_POWER,
    CONF_INVERT_INVERTER_POWER,
    CONF_INVERT_NET_POWER,
    CONF_NET_POWER,
    CONF_PERCENT_MINIMUM,
    CONF_VOLTAGE_L1,
    CONF_VOLTAGE_L2,
    CONF_VOLTAGE_L3,
    DEFAULT_CURRENCY,
    DEFAULT_EXPORT_PRICE,
    DEFAULT_IMPORT_PRICE,
    DEFAULT_PERCENT_MINIMUM,
    DOMAIN,
    ENTITY_CONFIG_KEYS,
)

Listener = Callable[[], None]


class GPlugEnergyRuntime:
    """Normalize gPlug values and maintain daily counters."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config = {**entry.data, **entry.options}
        self.day = dt_util.now().date().isoformat()
        self.import_baseline: float | None = None
        self.export_baseline: float | None = None
        self.integrated_import_kwh = 0.0
        self.integrated_export_kwh = 0.0
        self.peak_import_w = 0.0
        self.peak_export_w = 0.0
        self._last_integrated: datetime | None = None
        self._listeners: list[Listener] = []
        self._unsubscribers: list[Callable[[], None]] = []
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")

    async def async_setup(self) -> None:
        stored = await self._store.async_load()
        if stored and stored.get("day") == self.day:
            stored_import_entity = stored.get("import_energy_entity", self.config.get(CONF_IMPORT_ENERGY))
            stored_export_entity = stored.get("export_energy_entity", self.config.get(CONF_EXPORT_ENERGY))
            if stored_import_entity == self.config.get(CONF_IMPORT_ENERGY):
                self.import_baseline = stored.get("import_baseline")
            if stored_export_entity == self.config.get(CONF_EXPORT_ENERGY):
                self.export_baseline = stored.get("export_baseline")
            self.integrated_import_kwh = float(stored.get("integrated_import_kwh", 0))
            self.integrated_export_kwh = float(stored.get("integrated_export_kwh", 0))
            self.peak_import_w = float(stored.get("peak_import_w", 0))
            self.peak_export_w = float(stored.get("peak_export_w", 0))
        self._ensure_baselines()
        self._last_integrated = dt_util.utcnow()
        entity_ids = [self.config[key] for key in ENTITY_CONFIG_KEYS if self.config.get(key)]
        if entity_ids:
            self._unsubscribers.append(
                async_track_state_change_event(self.hass, entity_ids, self._handle_source_update)
            )
        self._unsubscribers.append(
            async_track_time_interval(self.hass, self._handle_timer, timedelta(seconds=10))
        )
        self._update_peaks()

    async def async_unload(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        await self._store.async_save(self._storage_data())

    @callback
    def add_listener(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def _handle_source_update(self, event: Event) -> None:
        self._reset_day_if_needed()
        self._update_peaks()
        self._schedule_save()
        self._notify()

    @callback
    def _handle_timer(self, now: datetime) -> None:
        self._reset_day_if_needed()
        self._integrate_power(dt_util.utcnow())
        self._update_peaks()
        self._schedule_save()
        self._notify()

    def power(self, key: str) -> float | None:
        state = self._state_for(key)
        if state is None:
            return None
        return power_in_watts(state.state, state.attributes.get("unit_of_measurement"))

    def energy(self, key: str) -> float | None:
        state = self._state_for(key)
        if state is None:
            return None
        return energy_in_kwh(state.state, state.attributes.get("unit_of_measurement"))

    def measurement(self, key: str, target: str) -> float | None:
        state = self._state_for(key)
        if state is None:
            return None
        return scaled_value(state.state, state.attributes.get("unit_of_measurement"), target)

    def net_power(self) -> float | None:
        direct = self.power(CONF_NET_POWER)
        if direct is not None:
            return -direct if self.config.get(CONF_INVERT_NET_POWER, False) else direct
        imported = self.power(CONF_IMPORT_POWER)
        exported = self.power(CONF_EXPORT_POWER)
        if imported is None and exported is None:
            return None
        return (imported or 0.0) - (exported or 0.0)

    def import_power(self) -> float | None:
        direct = self.power(CONF_IMPORT_POWER)
        if direct is not None:
            return max(0.0, direct)
        net = self.net_power()
        return max(0.0, net) if net is not None else None

    def export_power(self) -> float | None:
        direct = self.power(CONF_EXPORT_POWER)
        if direct is not None:
            return max(0.0, direct)
        net = self.net_power()
        return max(0.0, -net) if net is not None else None

    def import_today(self) -> float:
        total = self.energy(CONF_IMPORT_ENERGY)
        if total is not None and self.import_baseline is not None:
            return max(0.0, total - self.import_baseline)
        return self.integrated_import_kwh

    def export_today(self) -> float:
        total = self.energy(CONF_EXPORT_ENERGY)
        if total is not None and self.export_baseline is not None:
            return max(0.0, total - self.export_baseline)
        return self.integrated_export_kwh

    def inverter_power(self) -> float | None:
        value = self.power(CONF_INVERTER_GRID_POWER)
        if value is not None and self.config.get(CONF_INVERT_INVERTER_POWER, False):
            value *= -1
        return value

    def get_value(self, key: str) -> float | str | None:
        if key == "net_power":
            return _kilowatts(self.net_power())
        if key == "import_power":
            return _kilowatts(self.import_power())
        if key == "export_power":
            return _kilowatts(self.export_power())
        if key == "import_today":
            return self.import_today()
        if key == "export_today":
            return self.export_today()
        if key == "import_cost_today":
            return self.import_today() * float(self.config.get(CONF_IMPORT_PRICE, DEFAULT_IMPORT_PRICE) or 0)
        if key == "export_revenue_today":
            return self.export_today() * float(self.config.get(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE) or 0)
        if key == "net_cost_today":
            return self.get_value("import_cost_today") - self.get_value("export_revenue_today")
        if key == "peak_import_today":
            return _kilowatts(self.peak_import_w)
        if key == "peak_export_today":
            return _kilowatts(self.peak_export_w)
        if key == "data_age":
            return self._data_age()
        if key == "meter_status":
            age = self._data_age()
            if self.net_power() is None:
                return "unavailable"
            return "online" if age is not None and age <= 90 else "stale"
        passthrough_energy = {
            "import_energy_total": CONF_IMPORT_ENERGY,
            "export_energy_total": CONF_EXPORT_ENERGY,
            "import_energy_t1": CONF_IMPORT_ENERGY_T1,
            "import_energy_t2": CONF_IMPORT_ENERGY_T2,
            "export_energy_t1": CONF_EXPORT_ENERGY_T1,
            "export_energy_t2": CONF_EXPORT_ENERGY_T2,
        }
        if key in passthrough_energy:
            return self.energy(passthrough_energy[key])
        passthrough_measurements = {
            "voltage_l1": (CONF_VOLTAGE_L1, "V"), "voltage_l2": (CONF_VOLTAGE_L2, "V"),
            "voltage_l3": (CONF_VOLTAGE_L3, "V"), "current_l1": (CONF_CURRENT_L1, "A"),
            "current_l2": (CONF_CURRENT_L2, "A"), "current_l3": (CONF_CURRENT_L3, "A"),
            "frequency": (CONF_FREQUENCY, "Hz"),
        }
        if key in passthrough_measurements:
            config_key, target = passthrough_measurements[key]
            return self.measurement(config_key, target)
        if key == "voltage_imbalance":
            values = [self.measurement(config_key, "V") for config_key in (CONF_VOLTAGE_L1, CONF_VOLTAGE_L2, CONF_VOLTAGE_L3)]
            if any(value is None for value in values):
                return None
            average = sum(values) / 3
            return (max(values) - min(values)) / average * 100 if average else None
        if key == "inverter_grid_power":
            return _kilowatts(self.inverter_power())
        if key in {"inverter_difference", "inverter_absolute_difference", "inverter_agreement"}:
            reference = self.net_power()
            comparison = self.inverter_power()
            if reference is None or comparison is None:
                return None
            difference = reference - comparison
            if key == "inverter_difference":
                return _kilowatts(difference)
            if key == "inverter_absolute_difference":
                return _kilowatts(abs(difference))
            percent = percentage_difference(
                reference, comparison,
                float(self.config.get(CONF_PERCENT_MINIMUM, DEFAULT_PERCENT_MINIMUM) or 0),
            )
            return max(0.0, 100.0 - percent) if percent is not None else None
        return None

    def currency(self) -> str:
        return str(self.config.get(CONF_CURRENCY, DEFAULT_CURRENCY) or DEFAULT_CURRENCY)

    def day_start(self) -> datetime:
        return dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def is_available(self, key: str) -> bool:
        value = self.get_value(key)
        return value is not None and value != "unavailable"

    def attributes(self, metric_key: str) -> dict[str, Any]:
        return {
            "cockpit_group_id": self.entry.entry_id,
            "metric_key": metric_key,
            "source_device": self.config.get("source_device"),
        }

    def _state_for(self, key: str) -> State | None:
        entity_id = self.config.get(key)
        return self.hass.states.get(entity_id) if entity_id else None

    def _data_age(self) -> float | None:
        states = [
            self._state_for(key)
            for key in (CONF_NET_POWER, CONF_IMPORT_POWER, CONF_EXPORT_POWER)
            if self.config.get(key)
        ]
        states = [state for state in states if state is not None]
        if not states:
            return None
        # Import or export can legitimately remain unchanged for hours. Use the
        # freshest power channel and, on newer Home Assistant versions,
        # last_reported so an identical MQTT value still counts as received.
        timestamps = [getattr(state, "last_reported", None) or state.last_updated for state in states]
        freshest = max(timestamps)
        return max(0.0, (dt_util.utcnow() - freshest).total_seconds())

    def _ensure_baselines(self) -> None:
        if self.import_baseline is None:
            self.import_baseline = self.energy(CONF_IMPORT_ENERGY)
        if self.export_baseline is None:
            self.export_baseline = self.energy(CONF_EXPORT_ENERGY)

    def _integrate_power(self, now: datetime) -> None:
        if self._last_integrated is None:
            self._last_integrated = now
            return
        seconds = (now - self._last_integrated).total_seconds()
        self._last_integrated = now
        if seconds <= 0 or seconds > 120:
            return
        hours = seconds / 3600
        if self.energy(CONF_IMPORT_ENERGY) is None:
            self.integrated_import_kwh += (self.import_power() or 0.0) * hours / 1000
        if self.energy(CONF_EXPORT_ENERGY) is None:
            self.integrated_export_kwh += (self.export_power() or 0.0) * hours / 1000

    def _update_peaks(self) -> None:
        self.peak_import_w = max(self.peak_import_w, self.import_power() or 0.0)
        self.peak_export_w = max(self.peak_export_w, self.export_power() or 0.0)

    def _reset_day_if_needed(self) -> None:
        today = dt_util.now().date().isoformat()
        if today == self.day:
            return
        self.day = today
        self.import_baseline = self.energy(CONF_IMPORT_ENERGY)
        self.export_baseline = self.energy(CONF_EXPORT_ENERGY)
        self.integrated_import_kwh = 0.0
        self.integrated_export_kwh = 0.0
        self.peak_import_w = 0.0
        self.peak_export_w = 0.0
        self._last_integrated = dt_util.utcnow()

    def _storage_data(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "import_baseline": self.import_baseline,
            "export_baseline": self.export_baseline,
            "integrated_import_kwh": self.integrated_import_kwh,
            "integrated_export_kwh": self.integrated_export_kwh,
            "peak_import_w": self.peak_import_w,
            "peak_export_w": self.peak_export_w,
            "import_energy_entity": self.config.get(CONF_IMPORT_ENERGY),
            "export_energy_entity": self.config.get(CONF_EXPORT_ENERGY),
        }

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._storage_data, 15)

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()


def _kilowatts(watts: float | None) -> float | None:
    """Convert the internal watt representation to the public kW unit."""
    return watts / 1000 if watts is not None else None
