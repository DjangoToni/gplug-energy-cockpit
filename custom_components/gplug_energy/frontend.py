"""Register the bundled gPlug Energy dashboard card."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)
CARD_URL = f"/{DOMAIN}/gplug-energy-card.js"


async def async_register_frontend(hass: HomeAssistant) -> None:
    path = Path(__file__).parent / "www"
    try:
        await hass.http.async_register_static_paths([StaticPathConfig(f"/{DOMAIN}", str(path), False)])
    except RuntimeError:
        _LOGGER.debug("gPlug Energy frontend path already registered")
    lovelace = hass.data.get("lovelace")
    mode = getattr(lovelace, "mode", getattr(lovelace, "resource_mode", "yaml")) if lovelace else "yaml"
    if mode != "storage":
        return

    async def wait_for_resources(_now: Any = None) -> None:
        resources = getattr(lovelace, "resources", None)
        if resources is None or not getattr(resources, "loaded", False):
            async_call_later(hass, 5, wait_for_resources)
            return
        url = f"{CARD_URL}?v={VERSION}"
        existing = [item for item in resources.async_items() if item.get("url", "").split("?")[0] == CARD_URL]
        if existing:
            if existing[0].get("url") != url:
                await resources.async_update_item(existing[0]["id"], {"res_type": "module", "url": url})
        else:
            await resources.async_create_item({"res_type": "module", "url": url})

    await wait_for_resources()

