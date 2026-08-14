from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_URL

from .viggo_api import viggo_api
from .const import (
    CONF_CLIENT,
    CONF_CONFIG,
    CONF_DEFAULT,
    CONF_SHOW,
    CONF_PLATFORM,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .config_flow import ViggoConfigFlow, ViggoOptionsFlowHandler

_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Viggo integration from YAML configuration (legacy)."""
    # Get the configuration
    conf = config.get(DOMAIN)
    # If no config, abort
    if conf is None:
        return True

    # Create a instance of Viggo
    viggo = viggo_api(
        url=conf.get(CONF_URL, ""),
        username=conf.get(CONF_USERNAME, ""),
        password=conf.get(CONF_PASSWORD, ""),
    )

    # Loop the custom config
    # If the config key exist in the default config, update it
    config_options = CONF_DEFAULT.copy()
    for confKey, confValue in conf.get(CONF_SHOW, {}).items():
        if confKey in config_options.keys():
            config_options.update({confKey: confValue})
    config_options[CONF_UPDATE_INTERVAL] = conf.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL)

    # Add Viggo and the config to the stack
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][CONF_CLIENT] = viggo
    hass.data[DOMAIN][CONF_CONFIG] = config_options

    # Add sensors
    hass.async_create_task(
        hass.helpers.discovery.load_platform(CONF_PLATFORM, DOMAIN, conf, config)
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Viggo from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create Viggo API instance
    viggo = viggo_api(
        url=entry.data.get(CONF_URL, ""),
        username=entry.data.get(CONF_USERNAME, ""),
        password=entry.data.get(CONF_PASSWORD, ""),
    )

    # Create config with defaults and options
    config_options = CONF_DEFAULT.copy()
    config_options.update(entry.options)
    if CONF_UPDATE_INTERVAL not in config_options:
        config_options[CONF_UPDATE_INTERVAL] = UPDATE_INTERVAL

    # Store in hass data
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_CLIENT: viggo,
        CONF_CONFIG: config_options,
        "entry": entry,
    }

    # Set up options listener
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    # Forward entry setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
