"""gPlug Energy Cockpit integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CoreState, EVENT_HOMEASSISTANT_STARTED, HomeAssistant

from .const import DOMAIN
from .frontend import async_register_frontend
from .runtime import GPlugEnergyRuntime

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if hass.state == CoreState.running:
        await async_register_frontend(hass)
    else:
        async def register_after_start(_event) -> None:
            await async_register_frontend(hass)
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, register_after_start)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    runtime = GPlugEnergyRuntime(hass, entry)
    await runtime.async_setup()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime: GPlugEnergyRuntime = hass.data[DOMAIN].pop(entry.entry_id)
        await runtime.async_unload()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the cockpit after options have changed."""
    await hass.config_entries.async_reload(entry.entry_id)
