"""Config flow for Viggo integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_URL
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, UPDATE_INTERVAL
from .viggo_api import viggo_api

_LOGGER = logging.getLogger(__name__)

CONF_UPDATE_INTERVAL = "update_interval"
CONF_MFA_CODE = "mfa_code"
MFA_EXPIRY_MINUTES = 15


class ViggoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Viggo."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        super().__init__()
        self.viggo_instance: Optional[viggo_api] = None
        self.mfa_expiry: Optional[datetime] = None

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this config entry."""
        return ViggoOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate the connection and check for MFA
            try:
                viggo = viggo_api(
                    url=user_input.get(CONF_URL, ""),
                    username=user_input.get(CONF_USERNAME, ""),
                    password=user_input.get(CONF_PASSWORD, ""),
                )
                # Try login - this will raise an exception if MFA is required
                mfa_required = await self.hass.async_add_executor_job(
                    viggo.login_initial
                )
                
                if mfa_required:
                    # MFA is required - store the instance and move to MFA step
                    self.viggo_instance = viggo
                    self.mfa_expiry = datetime.now() + timedelta(minutes=MFA_EXPIRY_MINUTES)
                    return await self.async_step_mfa()
                else:
                    # No MFA required - complete the setup
                    await self.async_set_unique_id(user_input.get(CONF_USERNAME))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Viggo - {user_input.get(CONF_USERNAME)}",
                        data=user_input,
                    )
            except Exception as err:
                _LOGGER.error("Error connecting to Viggo: %s", err)
                errors["base"] = "invalid_auth"

        schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the MFA step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Check if MFA code has expired
            if self.mfa_expiry and datetime.now() > self.mfa_expiry:
                errors["base"] = "mfa_expired"
                self.mfa_expiry = None
                self.viggo_instance = None
                return await self.async_step_user()

            # Validate MFA code
            try:
                if not self.viggo_instance:
                    errors["base"] = "mfa_session_expired"
                    return await self.async_step_user()

                mfa_code = user_input.get(CONF_MFA_CODE, "")
                await self.hass.async_add_executor_job(
                    self.viggo_instance.login_mfa, mfa_code
                )
                
                # MFA validated - complete the setup
                username = self.viggo_instance.username
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()
                
                # Prepare the config data
                config_data = {
                    CONF_URL: self.viggo_instance.baseUrl,
                    CONF_USERNAME: self.viggo_instance.username,
                    CONF_PASSWORD: self.viggo_instance.password,
                }
                
                # Clear the temporary instances
                self.viggo_instance = None
                self.mfa_expiry = None
                
                return self.async_create_entry(
                    title=f"Viggo - {username}",
                    data=config_data,
                )
            except Exception as err:
                _LOGGER.error("Error validating MFA code: %s", err)
                errors["base"] = "invalid_mfa_code"

        schema = vol.Schema(
            {
                vol.Required(CONF_MFA_CODE): str,
            }
        )

        return self.async_show_form(
            step_id="mfa",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "expiry_minutes": str(MFA_EXPIRY_MINUTES),
            },
        )


class ViggoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Viggo."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    "userinfo", default=self.config_entry.options.get("userinfo", True)
                ): bool,
                vol.Optional(
                    "unread", default=self.config_entry.options.get("unread", True)
                ): bool,
                vol.Optional(
                    "amount", default=self.config_entry.options.get("amount", 5)
                ): int,
                vol.Optional(
                    "relations", default=self.config_entry.options.get("relations", True)
                ): bool,
                vol.Optional(
                    "schedule", default=self.config_entry.options.get("schedule", True)
                ): bool,
                vol.Optional(
                    "homework", default=self.config_entry.options.get("homework", True)
                ): bool,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self.config_entry.options.get(CONF_UPDATE_INTERVAL, UPDATE_INTERVAL),
                ): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
