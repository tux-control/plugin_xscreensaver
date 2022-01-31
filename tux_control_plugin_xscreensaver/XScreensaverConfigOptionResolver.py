import re
import shlex
from typing import Iterable, Union
from tux_control.plugin.controls.Select import Select
from tux_control.plugin.controls.Number import Number
from tux_control.plugin.controls.Slider import Slider
from tux_control.plugin.controls.Checkbox import Checkbox
from tux_control.plugin.controls.Text import Text

from tux_control.plugin.validators.RequiredValidator import RequiredValidator
from tux_control.plugin.validators.NumberValidator import NumberValidator

from tux_control.plugin.PluginConfigOption import PluginConfigOption


class XScreensaverConfigOptionResolver:

    def __init__(self, xscreensaver_config: dict, xscreensaver_user_config: dict = None):
        self.xscreensaver_config = xscreensaver_config
        self.xscreensaver_user_config = xscreensaver_user_config

        self.xscreensaver_control_handlers = {
            'number': self._resolve_number,
            'boolean': self._resolve_boolean,
            'select': self._resolve_select,
            'string': self._resolve_string,
            'hgroup': self._resolve_hgroup,
            'vgroup': self._resolve_vgroup,
        }

        self.xscreensaver_command_handlers = {
            'number': self._cmd_resolve_number,
            'boolean': self._cmd_resolve_boolean,
            'select': self._cmd_resolve_select,
            'string': self._cmd_resolve_string,
            'hgroup': self._cmd_resolve_hgroup,
            'vgroup': self._cmd_resolve_vgroup,
        }

    def get_config_options(self) -> Iterable[PluginConfigOption]:
        for item_name, item_value in self.xscreensaver_config.get('screensaver', {}).items():
            for resolved_control in self.resolve_xscreensaver_control(item_name, item_value):
                yield resolved_control

    def get_command(self, values: dict) -> str:
        screensaver_section = self.xscreensaver_config.get('screensaver', {})
        command_parts = [screensaver_section.get('@name')]

        for command in screensaver_section.get('command', []):
            command_parts.append(command.get('@arg', ''))

        for item_name, item_value in self.xscreensaver_config.get('screensaver', {}).items():
            for resolved_command in self.resolve_xscreensaver_command(item_name, item_value, values):
                command_parts.append(resolved_command)

        return ' '.join(command_parts)

    def resolve_xscreensaver_command(self, name: str, data: any, values: dict) -> Iterable[str]:
        if not isinstance(data, list):
            data = [data]

        for data_item in data:
            found_handler = self.xscreensaver_command_handlers.get(name)
            if found_handler:
                for item in found_handler(data_item, values):
                    yield item

    def _escape_value_for_cli(self, cli_value: str) -> str:
        # There are non alphanum chars in string, put it in ''
        return shlex.quote(cli_value).replace('\\n', '\\\\n')

    def _cmd_resolve_number(self, data_item: dict, values: dict) -> Iterable[str]:
        min_value = self._parse_number(data_item.get('@low'))
        max_value = self._parse_number(data_item.get('@high'))
        default_value = self._parse_number(data_item.get('@default'))
        found_value = values.get(data_item.get('@id'))

        if found_value:
            found_value = self._invert_range(min_value, max_value, found_value) if data_item.get('@convert') == 'invert' else found_value

        found_value = found_value if found_value else default_value
        if found_value != default_value:
            yield data_item.get('@arg').replace('%', '{}').format(self._escape_value_for_cli(str(found_value)))

    def _cmd_resolve_string(self, data_item: dict, values: dict) -> Iterable[str]:
        found_value = values.get(data_item.get('@id'))
        if found_value:
            yield data_item.get('@arg').replace('%', '{}').format(self._escape_value_for_cli(found_value))

    def _cmd_resolve_boolean(self, data_item: dict, values: dict) -> Iterable[str]:
        found_value = values.get(data_item.get('@id'))
        arg_unset = data_item.get('@arg-unset')
        arg_set = data_item.get('@arg-set')

        if arg_set and found_value:
            yield arg_set
        elif arg_unset and not found_value:
            yield arg_unset

    def _cmd_resolve_select(self, data_item: dict, values: dict) -> Iterable[str]:
        options = {}
        default_value = None
        for raw_option in data_item.get('option', []):
            options[raw_option.get('@id')] = raw_option.get('@arg-set')
            arg_set = raw_option.get('@arg-set')
            if not arg_set:
                default_value = raw_option.get('@id')

        found_value = values.get(data_item.get('@id'))
        found_value = found_value if found_value else default_value
        found_cmd = options.get(found_value)
        if found_cmd:
            yield found_cmd

    def _cmd_resolve_hgroup(self, data_item: dict = None, values: dict = None) -> Iterable[str]:
        if data_item:
            for item_name, item_value in data_item.items():
                for hgroup_item in self.resolve_xscreensaver_command(item_name, item_value, values):
                    yield hgroup_item

    def _cmd_resolve_vgroup(self, data_item: dict = None, values: dict = None) -> Iterable[str]:
        if data_item:
            for item_name, item_value in data_item.items():
                for vgroup_item in self.resolve_xscreensaver_command(item_name, item_value, values):
                    yield vgroup_item

    def _find_argument_value(self, argument_format: str) -> Union[str, None]:
        if not self.xscreensaver_user_config:
            return None

        command = self.xscreensaver_user_config.get('command')
        if not command:
            return None

        regex_string = argument_format.replace(' ', '').replace('%', r'\s+(\S+)')

        matches = re.search(regex_string, command)
        if matches:
            return matches.group(1).strip('"').strip("'")

    def _find_argument_set(self, argument_name: str) -> bool:
        if not self.xscreensaver_user_config:
            return False

        command = self.xscreensaver_user_config.get('command')
        if not command:
            return False

        return argument_name in command

    def _parse_number(self, value: str) -> Union[int, float]:
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            return 0

    def _invert_range(self, min_value: float, max_value: float, value: float):
        min_max_range = max_value-min_value
        off = value-min_value
        return min_value + (min_max_range - off)

    def _resolve_number(self, data_item: dict) -> Iterable[PluginConfigOption]:
        min_value = self._parse_number(data_item.get('@low'))
        max_value = self._parse_number(data_item.get('@high'))

        to_check_for_step = [data_item.get('@low'), data_item.get('@high'), data_item.get('@default')]

        decs = []
        if '.' in ''.join(to_check_for_step):

            for item in to_check_for_step:
                if '.' not in item:
                    continue
                whole, dec = item.split('.')

                number_of_decimals = len(dec)
                number_of_zeros = dec.count('0')
                if number_of_zeros != number_of_decimals:
                    decs.append(len(dec))

        step = float('0.{}1'.format('0' * (max(decs) - 1))) if decs else 1.0
        number_type = int if step == 1.0 else float

        if data_item.get('@type') == 'slider':
            control = Slider(
                min_value=min_value,
                max_value=max_value,
                step=step
            )
        else:
            control = Number(
                min_value=min_value,
                max_value=max_value,
                step=step
            )

        value = self._find_argument_value(data_item.get('@arg'))
        value = self._parse_number(value) if value else None
        if value:
            value = self._invert_range(min_value, max_value, value) if data_item.get('@convert') == 'invert' else value

        default_value = self._parse_number(data_item.get('@default'))
        default_value = self._invert_range(min_value, max_value, default_value) if data_item.get('@convert') == 'invert' else default_value

        yield PluginConfigOption(
            data_item.get('@id'),
            data_item.get('@_label', data_item.get('@_low-label')),
            '',
            control,
            validators=[
                RequiredValidator(),
                NumberValidator(number_type)
            ],
            value=value,
            default_value=default_value
        )

    def _resolve_string(self, data_item: dict) -> Iterable[PluginConfigOption]:
        control = Text()

        value = self._find_argument_value(data_item.get('@arg'))
        default_value = data_item.get('@default')

        yield PluginConfigOption(
            data_item.get('@id'),
            data_item.get('@_label'),
            '',
            control,
            validators=[RequiredValidator()],
            value=value,
            default_value=default_value
        )

    def _resolve_boolean(self, data_item: dict) -> Iterable[PluginConfigOption]:

        arg_unset = data_item.get('@arg-unset')
        arg_set = data_item.get('@arg-set')

        if arg_unset and not arg_set:
            value = not self._find_argument_set(arg_unset)
        elif not arg_unset and arg_set:
            value = self._find_argument_set(arg_set)
        else:
            raise ValueError

        yield PluginConfigOption(
            data_item.get('@id'),
            data_item.get('@_label', data_item.get('@id')),
            '',
            Checkbox(),
            validators=[RequiredValidator()],
            value=value,
            default_value=True if data_item.get('@arg-unset') else False,
        )

    def _resolve_select(self, data_item: dict) -> Iterable[PluginConfigOption]:
        options = []
        default_value = None
        selected_value = None
        for raw_option in data_item.get('option', []):
            options.append({
                'label': raw_option.get('@_label'),
                'value': raw_option.get('@id')
            })
            arg_set = raw_option.get('@arg-set')
            if not arg_set:
                default_value = raw_option.get('@id')
            elif self._find_argument_set(arg_set):
                selected_value = raw_option.get('@id')

        control = Select(options=options)

        yield PluginConfigOption(
            data_item.get('@id'),
            data_item.get('@_label', data_item.get('@id')),
            '',
            control,
            validators=[RequiredValidator()],
            value=selected_value,
            default_value=default_value,
        )

    def _resolve_hgroup(self, data_item: dict = None) -> Iterable[PluginConfigOption]:
        if data_item:
            for item_name, item_value in data_item.items():
                for hgroup_item in self.resolve_xscreensaver_control(item_name, item_value):
                    yield hgroup_item

    def _resolve_vgroup(self, data_item: dict = None) -> Iterable[PluginConfigOption]:
        if data_item:
            for item_name, item_value in data_item.items():
                for vgroup_item in self.resolve_xscreensaver_control(item_name, item_value):
                    yield vgroup_item

    def resolve_xscreensaver_control(self, name: str, data: any) -> Iterable[PluginConfigOption]:
        if not isinstance(data, list):
            data = [data]

        for data_item in data:
            found_handler = self.xscreensaver_control_handlers.get(name)
            if found_handler:
                for item in found_handler(data_item):
                    yield item
