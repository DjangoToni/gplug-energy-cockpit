# gPlug Energy Cockpit 0.3.3

<p align="center">
  <img src="custom_components/gplug_energy/brand/icon@2x.png" width="180" alt="gPlug Energy Cockpit logo">
</p>

<p align="center">
  Universal smart-meter dashboard for Home Assistant, with optional inverter comparison.
</p>

Universal Home Assistant dashboard integration for gPlug smart-meter data. It
works with or without a solar installation and does not communicate with the
meter itself; it uses existing Home Assistant sensor entities created by
Tasmota, MQTT, AMSreader, or another gPlug integration.

## Features

- guided UI setup with optional gPlug device selection
- automatic entity suggestions based on names and common OBIS identifiers
- manual correction of every suggested mapping
- signed net power or separate import/export power inputs
- total and tariff energy meters
- daily import/export, cost, remuneration, and peak power
- per-phase voltage/current, frequency, and voltage imbalance
- optional inverter grid-power comparison
- adaptive bundled dashboard card
- missing optional values are automatically hidden
- sensor assignments, prices, and inverter comparison can be edited later
- all public power values use kW and all energy values use kWh
- bundled transparent gPlug monogram displayed in the dashboard header
- bundled light and dark brand icons for the Home Assistant integration tile

## Installation

### HACS custom repository

1. Open HACS and select **Custom repositories**.
2. Add `https://github.com/DjangoToni/gplug-energy-cockpit` with category
   **Integration**.
3. Install **gPlug Energy Cockpit** and restart Home Assistant.
4. Open **Settings > Devices & services > Add integration**.

### Manual installation

1. Copy `custom_components/gplug_energy` into the Home Assistant `/config`
   directory.
2. Restart Home Assistant.
3. Open **Settings > Devices & services > Add integration**.
4. Search for **gPlug Energy Cockpit**.
5. Select the existing gPlug/Tasmota/MQTT device and verify the suggested
   entities.

No `configuration.yaml` entry is required.

## Integration tile logo

Home Assistant 2026.3 and newer load the bundled images from
`custom_components/gplug_energy/brand`. The gPlug monogram therefore appears
automatically on the integration tile after restarting Home Assistant. Older
Home Assistant releases ignore this folder but continue to run the integration.

## Edit an existing cockpit

Open **Settings > Devices & services**, select **gPlug Energy Cockpit**, and
choose **Configure**. Power sensors, tariff meters, phase measurements, prices,
and the optional inverter comparison can be changed without deleting the
integration. Home Assistant reloads the cockpit after saving.

## Dashboard card

With standard Lovelace storage mode, the integration registers the card
automatically. Add a manual dashboard card with:

```yaml
type: custom:gplug-energy-card
```

If multiple cockpits exist, specify the status sensor belonging to one cockpit:

```yaml
type: custom:gplug-energy-card
entity: sensor.your_gplug_cockpit_status
title: My Smart Meter
```

For Lovelace YAML mode, register the resource first:

```yaml
lovelace:
  resources:
    - url: /gplug_energy/gplug-energy-card.js?v=0.3.3
      type: module
```

After an update, perform a hard browser refresh if an older card remains in the
frontend cache.

## Support

Report reproducible problems through the
[GitHub issue tracker](https://github.com/DjangoToni/gplug-energy-cockpit/issues).

## License

This project is licensed under the MIT License.

## Sign convention

The normalized convention is:

- grid import: positive net power
- grid export: negative net power

Separate import/export sensors are expected to be positive. If a directly
selected net-power or inverter sensor uses the opposite convention, enable its
sign inversion during setup.

## Daily values

When total imported/exported energy meters are mapped, daily energy is derived
from their change since local midnight. If no energy meter is available, the
integration estimates daily energy by integrating the corresponding power
sensor every ten seconds. Daily values and peaks survive Home Assistant restarts
and reset at local midnight.
