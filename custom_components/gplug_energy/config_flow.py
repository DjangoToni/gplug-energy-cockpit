"""Config flow for gPlug Energy Cockpit."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er, selector

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
    CONF_NAME,
    CONF_NET_POWER,
    CONF_PERCENT_MINIMUM,
    CONF_SOURCE_DEVICE,
    CONF_VOLTAGE_L1,
    CONF_VOLTAGE_L2,
    CONF_VOLTAGE_L3,
    DEFAULT_CURRENCY,
    DEFAULT_EXPORT_PRICE,
    DEFAULT_IMPORT_PRICE,
    DEFAULT_NAME,
    DEFAULT_PERCENT_MINIMUM,
    DOMAIN,
    ENTITY_CONFIG_KEYS,
)

_LOGGER = logging.getLogger(__name__)

POWER_PATTERNS = {
    CONF_NET_POWER: ("net_power", "grid_power", "netzleistung", "power_total"),
    CONF_IMPORT_POWER: ("1_7_0", "1.7.0", "power_import", "import_power", "bezugsleistung", "_pi"),
    CONF_EXPORT_POWER: ("2_7_0", "2.7.0", "power_export", "export_power", "einspeiseleistung", "_po"),
    CONF_IMPORT_ENERGY: ("1_8_0", "1.8.0", "energy_import", "import_energy", "bezug_gesamt", "_ei"),
    CONF_EXPORT_ENERGY: ("2_8_0", "2.8.0", "energy_export", "export_energy", "einspeisung_gesamt", "_eo"),
    CONF_IMPORT_ENERGY_T1: ("1_8_1", "1.8.1", "ei1", "import_t1", "tarif_1"),
    CONF_IMPORT_ENERGY_T2: ("1_8_2", "1.8.2", "ei2", "import_t2", "tarif_2"),
    CONF_EXPORT_ENERGY_T1: ("2_8_1", "2.8.1", "eo1", "export_t1"),
    CONF_EXPORT_ENERGY_T2: ("2_8_2", "2.8.2", "eo2", "export_t2"),
    CONF_VOLTAGE_L1: ("32_7_0", "32.7.0", "voltage_l1", "spannung_l1"),
    CONF_VOLTAGE_L2: ("52_7_0", "52.7.0", "voltage_l2", "spannung_l2"),
    CONF_VOLTAGE_L3: ("72_7_0", "72.7.0", "voltage_l3", "spannung_l3"),
    CONF_CURRENT_L1: ("31_7_0", "31.7.0", "current_l1", "strom_l1"),
    CONF_CURRENT_L2: ("51_7_0", "51.7.0", "current_l2", "strom_l2"),
    CONF_CURRENT_L3: ("71_7_0", "71.7.0", "current_l3", "strom_l3"),
    CONF_FREQUENCY: ("14_7_0", "14.7.0", "frequency", "frequenz"),
}


class GPlugEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a gPlug Energy Cockpit."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow used to edit an existing cockpit."""
        # Home Assistant injects config_entry into OptionsFlow. Passing and
        # assigning it manually fails on releases where the property is
        # read-only and results in a 500 error when opening Configure.
        return GPlugEnergyOptionsFlow()

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._suggestions: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update({key: value for key, value in user_input.items() if value})
            # Entity registry data can contain non-string sentinel values on some
            # Home Assistant releases. Suggestions are optional, so never let a
            # malformed registry entry abort the setup flow.
            try:
                self._suggestions = self._find_suggestions(user_input.get(CONF_SOURCE_DEVICE))
            except (AttributeError, TypeError, ValueError):
                _LOGGER.exception("Could not build automatic gPlug entity suggestions")
                self._suggestions = {}
            return await self.async_step_power()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
                    vol.Optional(CONF_SOURCE_DEVICE): selector.DeviceSelector(),
                }
            ),
        )

    async def async_step_power(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            if not any(user_input.get(key) for key in (CONF_NET_POWER, CONF_IMPORT_POWER, CONF_EXPORT_POWER)):
                return self.async_show_form(
                    step_id="power", data_schema=self._power_schema(user_input), errors={"base": "power_required"}
                )
            self._data.update(_clean(user_input))
            return await self.async_step_details()
        return self.async_show_form(step_id="power", data_schema=self._power_schema())

    async def async_step_details(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(_clean(user_input))
            return await self.async_step_options()
        fields = (
            CONF_IMPORT_ENERGY_T1, CONF_IMPORT_ENERGY_T2, CONF_EXPORT_ENERGY_T1, CONF_EXPORT_ENERGY_T2,
            CONF_VOLTAGE_L1, CONF_VOLTAGE_L2, CONF_VOLTAGE_L3,
            CONF_CURRENT_L1, CONF_CURRENT_L2, CONF_CURRENT_L3, CONF_FREQUENCY,
        )
        return self.async_show_form(step_id="details", data_schema=self._entity_schema(fields))

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(_clean(user_input, keep_zero=True))
            device_id = self._data.get(CONF_SOURCE_DEVICE)
            unique = device_id or "|".join(
                str(self._data.get(key, "")) for key in (CONF_NET_POWER, CONF_IMPORT_POWER, CONF_EXPORT_POWER)
            )
            await self.async_set_unique_id(unique)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_INVERTER_GRID_POWER): _entity_selector(),
                    vol.Required(CONF_INVERT_NET_POWER, default=False): selector.BooleanSelector(),
                    vol.Required(CONF_INVERT_INVERTER_POWER, default=False): selector.BooleanSelector(),
                    vol.Required(CONF_IMPORT_PRICE, default=DEFAULT_IMPORT_PRICE): _number(0, 10, 0.01),
                    vol.Required(CONF_EXPORT_PRICE, default=DEFAULT_EXPORT_PRICE): _number(0, 10, 0.01),
                    vol.Required(CONF_CURRENCY, default=DEFAULT_CURRENCY): selector.TextSelector(),
                    vol.Required(CONF_PERCENT_MINIMUM, default=DEFAULT_PERCENT_MINIMUM): _number(0, 10000, 10, "W"),
                }
            ),
        )

    def _power_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        return self._entity_schema(
            (CONF_NET_POWER, CONF_IMPORT_POWER, CONF_EXPORT_POWER, CONF_IMPORT_ENERGY, CONF_EXPORT_ENERGY), defaults
        )

    def _entity_schema(self, fields: tuple[str, ...], defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        schema: dict[Any, Any] = {}
        for field in fields:
            default = defaults.get(field) or self._suggestions.get(field)
            if not isinstance(default, str) or not default.startswith("sensor."):
                default = None
            marker = vol.Optional(field, default=default) if default else vol.Optional(field)
            schema[marker] = _entity_selector()
        return vol.Schema(schema)

    def _find_suggestions(self, device_id: str | dict[str, Any] | None) -> dict[str, str]:
        if isinstance(device_id, dict):
            device_id = device_id.get("device_id")
        if not device_id:
            return {}
        registry = er.async_get(self.hass)
        suggestions: dict[str, tuple[int, str]] = {}
        entries = getattr(registry, "entities", {})
        entries = entries.values() if hasattr(entries, "values") else entries
        for entry in entries:
            entity_id = getattr(entry, "entity_id", None)
            if getattr(entry, "device_id", None) != device_id or not isinstance(entity_id, str) or not entity_id.startswith("sensor."):
                continue
            state = self.hass.states.get(entity_id)
            values = (entity_id, getattr(entry, "original_name", None), getattr(state, "name", None))
            searchable = " ".join(value for value in values if isinstance(value, str)).lower()
            for role, patterns in POWER_PATTERNS.items():
                score = max((len(pattern) for pattern in patterns if pattern in searchable), default=0)
                if score and score > suggestions.get(role, (0, ""))[0]:
                    suggestions[role] = (score, entity_id)
        return {role: entity_id for role, (_score, entity_id) in suggestions.items()}


class GPlugEnergyOptionsFlow(config_entries.OptionsFlow):
    """Edit sensor mappings and comparison settings after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self._data = {**self.config_entry.data, **self.config_entry.options}
        return await self.async_step_power(user_input)

    async def async_step_power(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        fields = (CONF_NET_POWER, CONF_IMPORT_POWER, CONF_EXPORT_POWER, CONF_IMPORT_ENERGY, CONF_EXPORT_ENERGY)
        if user_input is not None:
            if not any(user_input.get(key) for key in (CONF_NET_POWER, CONF_IMPORT_POWER, CONF_EXPORT_POWER)):
                return self.async_show_form(
                    step_id="power",
                    data_schema=_options_entity_schema(self._data, fields),
                    errors={"base": "power_required"},
                )
            self._store_fields(fields, user_input)
            return await self.async_step_details()
        return self.async_show_form(step_id="power", data_schema=_options_entity_schema(self._data, fields))

    async def async_step_details(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        fields = (
            CONF_IMPORT_ENERGY_T1, CONF_IMPORT_ENERGY_T2, CONF_EXPORT_ENERGY_T1, CONF_EXPORT_ENERGY_T2,
            CONF_VOLTAGE_L1, CONF_VOLTAGE_L2, CONF_VOLTAGE_L3,
            CONF_CURRENT_L1, CONF_CURRENT_L2, CONF_CURRENT_L3, CONF_FREQUENCY,
        )
        if user_input is not None:
            self._store_fields(fields, user_input)
            return await self.async_step_comparison()
        return self.async_show_form(step_id="details", data_schema=_options_entity_schema(self._data, fields))

    async def async_step_comparison(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            fields = (
                CONF_INVERTER_GRID_POWER, CONF_INVERT_NET_POWER, CONF_INVERT_INVERTER_POWER,
                CONF_IMPORT_PRICE, CONF_EXPORT_PRICE, CONF_CURRENCY, CONF_PERCENT_MINIMUM,
            )
            self._store_fields(fields, user_input)
            return self.async_create_entry(
                title="",
                data={key: self._data.get(key) for key in (*ENTITY_CONFIG_KEYS, *fields)},
            )
        return self.async_show_form(
            step_id="comparison",
            data_schema=vol.Schema(
                {
                    _optional_entity(CONF_INVERTER_GRID_POWER, self._data): _entity_selector(),
                    vol.Required(CONF_INVERT_NET_POWER, default=self._data.get(CONF_INVERT_NET_POWER, False)): selector.BooleanSelector(),
                    vol.Required(CONF_INVERT_INVERTER_POWER, default=self._data.get(CONF_INVERT_INVERTER_POWER, False)): selector.BooleanSelector(),
                    vol.Required(CONF_IMPORT_PRICE, default=self._data.get(CONF_IMPORT_PRICE, DEFAULT_IMPORT_PRICE)): _number(0, 10, 0.01),
                    vol.Required(CONF_EXPORT_PRICE, default=self._data.get(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE)): _number(0, 10, 0.01),
                    vol.Required(CONF_CURRENCY, default=self._data.get(CONF_CURRENCY, DEFAULT_CURRENCY)): selector.TextSelector(),
                    vol.Required(CONF_PERCENT_MINIMUM, default=self._data.get(CONF_PERCENT_MINIMUM, DEFAULT_PERCENT_MINIMUM)): _number(0, 10000, 10, "W"),
                }
            ),
        )

    def _store_fields(self, fields: tuple[str, ...], user_input: dict[str, Any]) -> None:
        for field in fields:
            self._data[field] = user_input.get(field)


def _optional_entity(field: str, values: dict[str, Any]):
    default = values.get(field)
    return vol.Optional(field, default=default) if isinstance(default, str) and default else vol.Optional(field)


def _options_entity_schema(values: dict[str, Any], fields: tuple[str, ...]) -> vol.Schema:
    return vol.Schema({_optional_entity(field, values): _entity_selector() for field in fields})


def _entity_selector():
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _number(minimum: float, maximum: float, step: float, unit: str | None = None):
    # Keep the selector configuration deliberately minimal. Older supported
    # Home Assistant releases do not expose NumberSelectorMode or the unit
    # option in the same way and otherwise abort the flow with "Unknown error".
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum, max=maximum, step=step,
        )
    )


def _clean(data: dict[str, Any], keep_zero: bool = False) -> dict[str, Any]:
    return {
        key: value for key, value in data.items()
        if value is not None and value != "" and (keep_zero or value != 0)
    }
