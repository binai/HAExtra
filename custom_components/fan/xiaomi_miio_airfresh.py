"""
Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/fan.xiaomi_miio_airfresh/
"""
import asyncio
from enum import Enum
from functools import partial
import logging

import voluptuous as vol

from homeassistant.components.fan import (FanEntity, PLATFORM_SCHEMA,
                                          SUPPORT_SET_SPEED, DOMAIN, )
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_TOKEN,
                                 ATTR_ENTITY_ID, )
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Miio Air Fresh'
DATA_KEY = 'fan.xiaomi_miio_airfresh'

CONF_MODEL = 'model'
MODEL_AIRFRESH = 'zhimi.airfresh'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MODEL): vol.In(
        ['zhimi.airfresh.va2']),
})

REQUIREMENTS = ['python-miio==0.4.0', 'construct==2.9.41']

ATTR_MODEL = 'model'

# Air Purifier
ATTR_TEMPERATURE = 'temperature'
ATTR_HUMIDITY = 'humidity'
ATTR_AIR_QUALITY_INDEX = 'aqi'
ATTR_CO2 = 'co2'
ATTR_MODE = 'mode'
ATTR_FILTER_HOURS_USED = 'filter_hours_used'
ATTR_BUZZER = 'buzzer'
ATTR_CHILD_LOCK = 'child_lock'
ATTR_LED = 'led'
ATTR_MOTOR_SPEED = 'motor_speed'

AVAILABLE_ATTRIBUTES_AIRFRESH = {
    ATTR_TEMPERATURE: 'temperature',
    ATTR_HUMIDITY: 'humidity',
    ATTR_AIR_QUALITY_INDEX: 'aqi',
    ATTR_MODE: 'mode',
    ATTR_FILTER_HOURS_USED: 'filter_hours_used',
    ATTR_CHILD_LOCK: 'child_lock',
    ATTR_LED: 'led',
    ATTR_MOTOR_SPEED: 'motor_speed',
    ATTR_BUZZER: 'buzzer',
    ATTR_CO2: 'co2',
    #"temp_dec", "f1_hour_used", "motor1_speed"
}

OPERATION_MODES_AIRFRESH = ['Auto', 'Silent', 'Interval', 'Low',
                                  'Middle', 'Strong']

SUCCESS = ['ok']

FEATURE_SET_BUZZER = 1
FEATURE_SET_LED = 2
FEATURE_SET_CHILD_LOCK = 4

FEATURE_FLAGS_GENERIC = (FEATURE_SET_BUZZER |
                         FEATURE_SET_CHILD_LOCK)

FEATURE_FLAGS_AIRFRESH = (FEATURE_FLAGS_GENERIC |
                          FEATURE_SET_LED)

SERVICE_SET_BUZZER_ON = 'xiaomi_miio_set_buzzer_on'
SERVICE_SET_BUZZER_OFF = 'xiaomi_miio_set_buzzer_off'
SERVICE_SET_LED_ON = 'xiaomi_miio_set_led_on'
SERVICE_SET_LED_OFF = 'xiaomi_miio_set_led_off'
SERVICE_SET_CHILD_LOCK_ON = 'xiaomi_miio_set_child_lock_on'
SERVICE_SET_CHILD_LOCK_OFF = 'xiaomi_miio_set_child_lock_off'

AIRPURIFIER_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


SERVICE_TO_METHOD = {
    SERVICE_SET_BUZZER_ON: {'method': 'async_set_buzzer_on'},
    SERVICE_SET_BUZZER_OFF: {'method': 'async_set_buzzer_off'},
    SERVICE_SET_LED_ON: {'method': 'async_set_led_on'},
    SERVICE_SET_LED_OFF: {'method': 'async_set_led_off'},
    SERVICE_SET_CHILD_LOCK_ON: {'method': 'async_set_child_lock_on'},
    SERVICE_SET_CHILD_LOCK_OFF: {'method': 'async_set_child_lock_off'},
}

import enum
import logging
import re
from collections import defaultdict
from typing import Any, Dict, Optional

import click

from miio.click_common import command, format_output, EnumType
from miio.device import Device, DeviceException

class AirFreshException(DeviceException):
    pass


class OperationMode(enum.Enum):
    # Supported modes of the Air Fresh
    Auto = 'auto'
    Silent = 'silent'
    Interval = 'interval'
    Low = 'low'
    Middle = 'middle'
    Strong = 'strong'


class AirFreshStatus:
    """Container for status reports from the air fresh."""

    _filter_type_cache = {}

    def __init__(self, data: Dict[str, Any]) -> None:
        """
        A request is limited to 16 properties.
        """

        self.data = data

    @property
    def power(self) -> str:
        """Power state."""
        return self.data["power"]

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.power == "on"

    @property
    def aqi(self) -> int:
        """Air quality index."""
        return self.data["aqi"]

    @property
    def co2(self) -> int:
        """Air quality index."""
        return self.data["co2"]

    @property
    def average_aqi(self) -> int:
        """Average of the air quality index."""
        return self.data["average_aqi"]

    @property
    def humidity(self) -> int:
        """Current humidity."""
        return self.data["humidity"]

    @property
    def temperature(self) -> Optional[float]:
        """Current temperature, if available."""
        if self.data["temp_dec"] is not None:
            return self.data["temp_dec"] / 10.0

        return None

    @property
    def mode(self) -> OperationMode:
        """Current operation mode."""
        return OperationMode(self.data["mode"])

    @property
    def led(self) -> bool:
        """Return True if LED is on."""
        return self.data["led"] == "on"

    @property
    def buzzer(self) -> Optional[bool]:
        """Return True if buzzer is on."""
        if self.data["buzzer"] is not None:
            return self.data["buzzer"] == "on"

        return None

    @property
    def child_lock(self) -> bool:
        """Return True if child lock is on."""
        return self.data["child_lock"] == "on"

    @property
    def filter_hours_used(self) -> int:
        """How long the filter has been in use."""
        return self.data["f1_hour_used"]

    @property
    def motor_speed(self) -> int:
        """Speed of the motor."""
        return self.data["motor1_speed"]

    def __repr__(self) -> str:
        s = "<AirFreshStatus power=%s, " \
            "aqi=%s, " \
            "co2=%s, " \
            "average_aqi=%s, " \
            "temperature=%s, " \
            "humidity=%s%%, " \
            "mode=%s, " \
            "led=%s, " \
            "buzzer=%s, " \
            "child_lock=%s, " \
            "filter_hours_used=%s, " \
            "motor_speed=%s, " \
            (self.power,
             self.aqi,
             self.co2,
             self.average_aqi,
             self.temperature,
             self.humidity,
             self.mode,
             self.led,
             self.buzzer,
             self.child_lock,
             self.filter_hours_used,
             self.motor1_speed)
        return s

    def __json__(self):
        return self.data


class AirFresh(Device):
    """Main class representing the air fresh."""

    @command(
        default_output=format_output(
            "",
            "Power: {result.power}\n"
            "AQI: {result.aqi} μg/m³\n"
            "CO2: {result.co2} mg/m³\n"
            "Temperature: {result.temperature} °C\n"
            "Humidity: {result.humidity} %\n"
            "Mode: {result.mode.value}\n"
            "LED: {result.led}\n"
            "Buzzer: {result.buzzer}\n"
            "Child lock: {result.child_lock}\n"
            "Filter hours used: {result.filter_hours_used}\n"
            "Motor speed: {result.motor_speed} rpm\n"
        )
    )
    def status(self) -> AirFreshStatus:
        """Retrieve properties."""

        properties = ["power", "mode", "aqi", "co2", "led_level", "temp_dec", "humidity", "buzzer", "child_lock", "f1_hour_used", "motor1_speed"]

        # A single request is limited to 16 properties. Therefore the
        # properties are divided into multiple requests
        _props = properties.copy()
        values = []
        while _props:
            values.extend(self.send("get_prop", _props[:15]))
            _props[:] = _props[15:]

        properties_count = len(properties)
        values_count = len(values)
        if properties_count != values_count:
            _LOGGER.debug(
                "Count (%s) of requested properties does not match the "
                "count (%s) of received values.",
                properties_count, values_count)

        return AirFreshStatus(
            defaultdict(lambda: None, zip(properties, values)))

    @command(
        default_output=format_output("Powering on"),
    )
    def on(self):
        """Power on."""
        return self.send("set_power", ["on"])

    @command(
        default_output=format_output("Powering off"),
    )
    def off(self):
        """Power off."""
        return self.send("set_power", ["off"])

    @command(
        click.argument("mode", type=EnumType(OperationMode, False)),
        default_output=format_output("Setting mode to '{mode.value}'")
    )
    def set_mode(self, mode: OperationMode):
        """Set mode."""
        return self.send("set_mode", [mode.value])

    @command(
        click.argument("led", type=bool),
        default_output=format_output(
            lambda led: "Turning on LED"
            if led else "Turning off LED"
        )
    )
    def set_led(self, led: bool):
        """Turn led on/off."""
        if led:
            return self.send("set_led", ['on'])
        else:
            return self.send("set_led", ['off'])

    @command(
        click.argument("buzzer", type=bool),
        default_output=format_output(
            lambda buzzer: "Turning on buzzer"
            if buzzer else "Turning off buzzer"
        )
    )
    def set_buzzer(self, buzzer: bool):
        """Set buzzer on/off."""
        if buzzer:
            return self.send("set_buzzer", ["on"])
        else:
            return self.send("set_buzzer", ["off"])

    @command(
        click.argument("lock", type=bool),
        default_output=format_output(
            lambda lock: "Turning on child lock"
            if lock else "Turning off child lock"
        )
    )
    def set_child_lock(self, lock: bool):
        """Set child lock on/off."""
        if lock:
            return self.send("set_child_lock", ["on"])
        else:
            return self.send("set_child_lock", ["off"])


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the miio fan device from config."""
    from miio import Device, DeviceException
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    model = config.get(CONF_MODEL)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])
    unique_id = None

    if model is None:
        try:
            miio_device = Device(host, token)
            device_info = miio_device.info()
            model = device_info.model
            unique_id = "{}-{}".format(model, device_info.mac_address)
            _LOGGER.info("%s %s %s detected",
                         model,
                         device_info.firmware_version,
                         device_info.hardware_version)
        except DeviceException:
            raise PlatformNotReady

    if model.startswith('zhimi.airfresh.'):
        air_fresh = AirFresh(host, token)
        device = XiaomiAirFresh(name, air_fresh, model, unique_id)
    else:
        _LOGGER.error(
            'Unsupported device found! Please create an issue at '
            'https://github.com/Yonsm/HAExtra/issues '
            'and provide the following data: %s', model)
        return False

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)

    async def async_service_handler(service):
        """Map services to methods on XiaomiAirPurifier."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [device for device in hass.data[DATA_KEY].values() if
                       device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_KEY].values()

        update_tasks = []
        for device in devices:
            if not hasattr(device, method['method']):
                continue
            await getattr(device, method['method'])(**params)
            update_tasks.append(device.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks, loop=hass.loop)

    for air_fresh_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[air_fresh_service].get(
            'schema', AIRPURIFIER_SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, air_fresh_service, async_service_handler, schema=schema)


class XiaomiGenericDevice(FanEntity):
    """Representation of a generic Xiaomi device."""

    def __init__(self, name, device, model, unique_id):
        """Initialize the generic Xiaomi device."""
        self._name = name
        self._device = device
        self._model = model
        self._unique_id = unique_id

        self._available = False
        self._state = None
        self._state_attrs = {
            ATTR_MODEL: self._model,
        }
        self._device_features = FEATURE_FLAGS_GENERIC
        self._skip_update = False

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def should_poll(self):
        """Poll the device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a miio device command handling error messages."""
        from miio import DeviceException
        try:
            result = await self.hass.async_add_job(
                partial(func, *args, **kwargs))

            _LOGGER.debug("Response received from miio device: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            self._available = False
            return False

    async def async_turn_on(self, speed: str = None,
                            **kwargs) -> None:
        """Turn the device on."""
        if speed:
            # If operation mode was set the device must not be turned on.
            result = await self.async_set_speed(speed)
        else:
            result = await self._try_command(
                "Turning the miio device on failed.", self._device.on)

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.off)

        if result:
            self._state = False
            self._skip_update = True

    async def async_set_buzzer_on(self):
        """Turn the buzzer on."""
        if self._device_features & FEATURE_SET_BUZZER == 0:
            return

        await self._try_command(
            "Turning the buzzer of the miio device on failed.",
            self._device.set_buzzer, True)

    async def async_set_buzzer_off(self):
        """Turn the buzzer off."""
        if self._device_features & FEATURE_SET_BUZZER == 0:
            return

        await self._try_command(
            "Turning the buzzer of the miio device off failed.",
            self._device.set_buzzer, False)

    async def async_set_child_lock_on(self):
        """Turn the child lock on."""
        if self._device_features & FEATURE_SET_CHILD_LOCK == 0:
            return

        await self._try_command(
            "Turning the child lock of the miio device on failed.",
            self._device.set_child_lock, True)

    async def async_set_child_lock_off(self):
        """Turn the child lock off."""
        if self._device_features & FEATURE_SET_CHILD_LOCK == 0:
            return

        await self._try_command(
            "Turning the child lock of the miio device off failed.",
            self._device.set_child_lock, False)


class XiaomiAirFresh(XiaomiGenericDevice):
    """Representation of a Xiaomi Air Purifier."""

    def __init__(self, name, device, model, unique_id):
        """Initialize the plug switch."""
        super().__init__(name, device, model, unique_id)

        self._device_features = FEATURE_FLAGS_AIRFRESH
        self._available_attributes = AVAILABLE_ATTRIBUTES_AIRFRESH
        self._speed_list = OPERATION_MODES_AIRFRESH

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes})

    async def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_job(
                self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs.update(
                {key: self._extract_value_from_attribute(state, value) for
                 key, value in self._available_attributes.items()})

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def speed(self):
        """Return the current speed."""
        if self._state:
            return OperationMode(self._state_attrs[ATTR_MODE]).name

        return None

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if self.supported_features & SUPPORT_SET_SPEED == 0:
            return

        _LOGGER.debug("Setting the operation mode to: %s", speed)

        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode, OperationMode[speed.title()])

    async def async_set_led_on(self):
        """Turn the led on."""
        if self._device_features & FEATURE_SET_LED == 0:
            return

        await self._try_command(
            "Turning the led of the miio device off failed.",
            self._device.set_led, True)

    async def async_set_led_off(self):
        """Turn the led off."""
        if self._device_features & FEATURE_SET_LED == 0:
            return

        await self._try_command(
            "Turning the led of the miio device off failed.",
            self._device.set_led, False)
