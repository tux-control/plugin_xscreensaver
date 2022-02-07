import os
import shutil
import xmltodict
import hashlib
import datetime
from pathlib import Path
from typing import Union, Iterable, Tuple
from tux_control.plugin.IPlugin import IPlugin
from tux_control.plugin.GridColumn import GridColumn
from tux_control.plugin.IPluginConfigItem import IPluginConfigItem
from tux_control.plugin.PluginConfigOption import PluginConfigOption
from tux_control.plugin.CurrentUser import CurrentUser

from tux_control.plugin.controls.Checkbox import Checkbox
from tux_control.plugin.controls.Select import Select
from tux_control.plugin.controls.Number import Number
from tux_control.plugin.controls.Text import Text
from tux_control.plugin.controls.Url import Url
from tux_control.plugin.controls.File import File, FilePickerType

from tux_control.plugin.validators.RequiredValidator import RequiredValidator
from tux_control.plugin.validators.UrlValidator import UrlValidator
from tux_control.plugin.validators.NumberValidator import NumberValidator

from tux_control.plugin.exceptions import SetException

from xscreensaver_config.ConfigParser import ConfigParser

from tux_control_plugin_xscreensaver.PluginConfigItem import PluginConfigItem
from tux_control_plugin_xscreensaver.XScreensaverConfigOptionResolver import XScreensaverConfigOptionResolver


class Plugin(IPlugin):
    _xscreensaver_config_dir = '/usr/share/xscreensaver/config/'

    plugin_permissions = {
        'xcreeensaver.access': 'Allows access to xscreensaver settings'
    }

    name = 'XScreenSaver'
    icon = 'hourglass-half'
    on_set_plugin_config_item_class = PluginConfigItem
    grid_columns = [
        GridColumn('name', 'Name', filter_match_mode='contains'),
        GridColumn('description', 'Description'),
        GridColumn('is_enabled', 'Enabled', column_format='boolean'),
        GridColumn('is_selected', 'Selected', column_format='boolean'),
    ]

    def __init__(self, plugin_key: str = None, plugin_config: dict = None) -> None:
        self.plugin_key = plugin_key
        self.plugin_config = plugin_config

    @property
    def key(self) -> str:
        return self.__class__.__module__

    @property
    def is_active(self) -> bool:
        return shutil.which('xscreensaver') is not None and CurrentUser.has_permission('xcreeensaver.access')

    @property
    def plugin_config_items(self) -> Iterable[IPluginConfigItem]:
        # Global settings
        allowed_screensavers = self.plugin_config.get('ALLOWED_SCREENSAVERS')
        yield self._get_global_settings_plugin_config_item()

        # All xscrensavers
        xscreensaver_user_config = self._get_xscreensaver_user_config_dict()
        for item_key, xscreensaver_config in self._get_xscreensaver_config().items():

            if allowed_screensavers and item_key not in allowed_screensavers:
                continue

            xscreensaver_user_config_item_index, xscreensaver_user_config_item = self._find_xscreensaver_user_config_item(item_key, xscreensaver_user_config)
            yield self._create_plugin_config_item(
                item_key,
                xscreensaver_config,
                xscreensaver_user_config_item,
                self._is_xscreensaver_selected(xscreensaver_user_config, xscreensaver_user_config_item_index)
            )

    def on_get_plugin_config_item(self, plugin_config_item_key: str) -> PluginConfigItem:
        if plugin_config_item_key == self._global_settings_key:
            # Global settings
            return self._get_global_settings_plugin_config_item()

        xscreensaver_user_config = self._get_xscreensaver_user_config_dict()
        found_config = self._get_xscreensaver_config().get(plugin_config_item_key)
        if not found_config:
            raise ValueError('Config not found')

        xscreensaver_user_config_item_index, xscreensaver_user_config_item = self._find_xscreensaver_user_config_item(plugin_config_item_key, xscreensaver_user_config)
        return self._create_plugin_config_item(
            plugin_config_item_key,
            found_config,
            xscreensaver_user_config_item,
            self._is_xscreensaver_selected(xscreensaver_user_config, xscreensaver_user_config_item_index)
        )

    def on_set_plugin_config_item(self, plugin_config_item: PluginConfigItem) -> None:
        values = plugin_config_item.get_values()
        xscreensaver_user_config = self._get_xscreensaver_user_config()
        xscreensaver_user_config_dict = xscreensaver_user_config.read()
        xscreensaver_config = self._get_xscreensaver_config()

        if plugin_config_item.key == self._global_settings_key:
            # We are configuring global settings
            lock_timeout = values.get('lockTimeout')
            mode = values.get('mode')

            xscreensaver_user_config_data = {
                'mode': mode,
                'timeout': self._to_xscreensaver_time(values.get('timeout')),
                'cycle': self._to_xscreensaver_time(values.get('cycle')),
                'lockTimeout': self._to_xscreensaver_time(lock_timeout),
                'lock': 'True' if lock_timeout > 0 else 'False',  # Enable/Disable lock timeout by its time
                'grabDesktopImages': 'True' if values.get('grabDesktopImages') else 'False',
                'grabVideoFrames': 'True' if values.get('grabVideoFrames') else 'False',
                'chooseRandomImages': 'True' if values.get('chooseRandomImages') else 'False',
                'imageDirectory': values.get('imageDirectory'),
                'textMode': values.get('textMode'),
                'textLiteral': values.get('textLiteral').replace('\\n', '\\\\n'),
                'textFile': values.get('textFile'),
                'textProgram': values.get('textProgram'),
                'textURL': values.get('textURL'),
            }
        else:
            # We are configuring settings for specified screensaver
            xscreensaver_config_item = xscreensaver_config.get(plugin_config_item.key)
            if not xscreensaver_config_item:
                raise SetException('PluginConfigItem not found')

            xscreensaver_user_config_item_index, xscreensaver_user_config_item = self._find_xscreensaver_user_config_item(plugin_config_item.key, xscreensaver_user_config_dict)

            xscreensaver_config_option_resolver = XScreensaverConfigOptionResolver(xscreensaver_config_item, xscreensaver_user_config_item)

            command = xscreensaver_config_option_resolver.get_command(values)
            new_programs_list = []
            for program in xscreensaver_user_config_dict.get('programs'):
                if program.get('command').startswith(plugin_config_item.key):
                    program['command'] = command
                    program['enabled'] = plugin_config_item.is_enabled

                new_programs_list.append(program)

            xscreensaver_user_config_data = {
                'programs': new_programs_list
            }

            if plugin_config_item.is_selected:
                xscreensaver_user_config_data['selected'] = xscreensaver_user_config_item_index

        try:
            xscreensaver_user_config.update(xscreensaver_user_config_data)
            xscreensaver_user_config.save()
        except (FileNotFoundError, PermissionError) as e:
            raise SetException('Failed to save configuration: {}'.format(e)) from e

    @property
    def _global_settings_key(self) -> str:
        return hashlib.md5(self.key.encode('UTF-8')).hexdigest()

    def _is_xscreensaver_selected(self, xscreensaver_user_config: dict, xscreensaver_user_config_item_index: int):
        return int(xscreensaver_user_config.get('selected')) == xscreensaver_user_config_item_index

    def _get_global_settings_plugin_config_item(self) -> PluginConfigItem:
        xscreensaver_user_config = self._get_xscreensaver_user_config_dict()
        return PluginConfigItem(
            name='Global Settings',
            key=self._global_settings_key,
            description='Global settings for all screensavers',
            plugin_config_options=[
                PluginConfigOption(
                    value=xscreensaver_user_config.get('mode'),
                    default_value='random',
                    key='mode',
                    name='Mode',
                    description='Configure screensaver mode',
                    validators=[RequiredValidator()],
                    control=Select(
                        [
                            {
                                'label': 'Disable Screen Saver',
                                'value': 'off'
                            },
                            {
                                'label': 'Blank Screen Only',
                                'value': 'blank'
                            },
                            {
                                'label': 'Only One Screen Saver (Selected will be used)',
                                'value': 'one'
                            },
                            {
                                'label': 'Random Screen Saver',
                                'value': 'random'
                            },
                            {
                                'label': 'Same Random Savers',
                                'value': 'random-same'
                            }
                        ]
                    )
                ),
                PluginConfigOption(
                    value=self._from_xscreensaver_time(xscreensaver_user_config.get('timeout')),
                    default_value=10,
                    key='timeout',
                    name='Blank After',
                    description='Blank screen after time (seconds)',
                    validators=[
                        RequiredValidator(),
                        NumberValidator()
                    ],
                    control=Number(
                        min_value=1,
                        max_value=720 * 60,  # This is in minutes from xscreensaver-demo multiply by 60 to seconds
                        step=1
                    )
                ),
                PluginConfigOption(
                    value=self._from_xscreensaver_time(xscreensaver_user_config.get('cycle')),
                    default_value=10,
                    key='cycle',
                    name='Cycle After',
                    description='Cycle screensavers after (seconds), 0 to disable',
                    validators=[
                        RequiredValidator(),
                        NumberValidator()
                    ],
                    control=Number(
                        min_value=0,
                        max_value=720 * 60,  # This is in minutes from xscreensaver-demo multiply by 60 to seconds
                        step=1
                    )
                ),
                PluginConfigOption(
                    value=self._from_xscreensaver_time(xscreensaver_user_config.get('lockTimeout')),
                    default_value=0,
                    key='lockTimeout',
                    name='Lock Screen After',
                    description='Locks screen after (seconds), 0 to disable',
                    validators=[
                        RequiredValidator(),
                        NumberValidator()
                    ],
                    control=Number(
                        min_value=0,
                        max_value=720 * 60,  # This is in minutes from xscreensaver-demo multiply by 60 to seconds
                        step=1
                    )
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('grabDesktopImages') == 'True',
                    default_value=True,
                    key='grabDesktopImages',
                    name='Grab Desktop Images',
                    description='Whether the image-manipulation modes should be allowed to operate on an image of your desktop.',
                    validators=[RequiredValidator()],
                    control=Checkbox()
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('grabVideoFrames') == 'True',
                    default_value=False,
                    key='grabVideoFrames',
                    name='Grab Video Frames',
                    description='Whether the image-manipulation modes should operate on images captured from the system\'s video input.',
                    validators=[RequiredValidator()],
                    control=Checkbox()
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('chooseRandomImages') == 'True',
                    default_value=True,
                    key='chooseRandomImages',
                    name='Choose Random Image',
                    description='Whether the image-manipulation modes should load image files.',
                    validators=[RequiredValidator()],
                    control=Checkbox()
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('imageDirectory'),
                    default_value='',
                    key='imageDirectory',
                    name='Image directory',
                    description='Image directory or RSS feed or Atom feed from where images will be randomly chosen.',
                    validators=[],
                    control=File(picker_type=FilePickerType.DIRECTORY)
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('textMode'),
                    default_value='literal',
                    key='textMode',
                    name='Text mode',
                    description='What text mode should text based screensavers use.',
                    validators=[],
                    control=Select(
                        [
                            {
                                'label': 'Host name and Time',
                                'value': 'date'
                            },
                            {
                                'label': 'Literal',
                                'value': 'literal'
                            },
                            {
                                'label': 'Text file',
                                'value': 'file'
                            },
                            {
                                'label': 'Program',
                                'value': 'program'
                            },
                            {
                                'label': 'URL',
                                'value': 'url'
                            },
                        ]
                    )
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('textLiteral').replace('\\\\n', '\\n'),
                    default_value='XScreenSaver',
                    key='textLiteral',
                    name='Text literal',
                    description='Literal text to display in screensaver when Literal mode is selected.',
                    validators=[],
                    control=Text()
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('textFile'),
                    default_value='',
                    key='textFile',
                    name='Text file',
                    description='File from where to read a text to display in screensaver when File mode is selected.',
                    validators=[],
                    control=Text()
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('textProgram'),
                    default_value='fortune',
                    key='textProgram',
                    name='Text program',
                    description='Program from where to read a text to display in screensaver when Program mode is selected.',
                    validators=[],
                    control=Text()
                ),
                PluginConfigOption(
                    value=xscreensaver_user_config.get('textURL'),
                    default_value='https://en.wikipedia.org/w/index.php?title=Special:NewPages&feed=rss',
                    key='textURL',
                    name='Text URL',
                    description='URL from where to read a text to display in screensaver when URL mode is selected.',
                    validators=[
                        UrlValidator()
                    ],
                    control=Url()
                ),
            ],
            is_enabled=True
        )

    def _create_plugin_config_item(self, item_key: str, xscreensaver_config: dict, xscreensaver_user_config: dict = None, is_selected: bool = False):
        xscreensaver_config_option_resolver = XScreensaverConfigOptionResolver(xscreensaver_config, xscreensaver_user_config)
        plugin_config_options = list(xscreensaver_config_option_resolver.get_config_options())

        # Common settings for each item
        plugin_config_options.append(PluginConfigOption(
            'is_enabled',
            'Enabled',
            'Is this screensaver enabled?',
            Checkbox(),
            value=xscreensaver_user_config.get('enabled')
        ))

        plugin_config_options.append(PluginConfigOption(
            'is_selected',
            'Selected',
            'Is this screensaver selected? (only useful in "Only One Screensaver" mode, select another screensaver to unselect this one)',
            Checkbox(),
            value=is_selected
        ))

        return PluginConfigItem(
            name=xscreensaver_config.get('screensaver', {}).get('@_label'),
            key=item_key,
            description=xscreensaver_config.get('screensaver', {}).get('_description'),
            plugin_config_options=plugin_config_options,
            is_enabled=xscreensaver_user_config.get('enabled'),
            is_selected=is_selected
        )

    def _find_xscreensaver_user_config_item(self, item_key: str, xscreensaver_user_config: dict) -> Tuple[int, Union[dict, None]]:
        for index, program in enumerate(xscreensaver_user_config.get('programs')):
            if program.get('command').startswith(item_key):
                return index, program

        return 0, None

    def _get_xscreensaver_config(self) -> dict:
        config_dict = {}
        config_dir = Path(self._xscreensaver_config_dir)
        for xml_file in config_dir.glob('*.xml'):
            with xml_file.open('r') as xml_handle:
                config_dict[xml_file.stem] = xmltodict.parse(xml_handle.read(), dict_constructor=dict)

        return config_dict

    def _to_xscreensaver_time(self, seconds: int) -> str:
        """
        Convert seconds to xscreensaver time
        :param seconds:
        :return:
        """
        return str(datetime.timedelta(seconds=seconds))

    def _from_xscreensaver_time(self, xscreensaver_time: str) -> int:
        """
        Convert xscreensaver time to seconds
        :param xscreensaver_time:
        :return:
        """
        h, m, s = xscreensaver_time.split(':')
        return int(h) * 3600 + int(m) * 60 + int(s)

    def _get_xscreensaver_user_config(self) -> ConfigParser:
        config_path = os.path.join(CurrentUser.get_system_user().home_directory, '.xscreensaver')
        config = ConfigParser(config_path, ignore_missing_file=True)
        if not os.path.isfile(config_path):
            # File not found, generate default one
            programs_list = []
            for item_key, xscreensaver_config in self._get_xscreensaver_config().items():
                screensaver_section = xscreensaver_config.get('screensaver')
                program = {
                    'command': screensaver_section.get('@name'),
                    'enabled': False,
                    'renderer': 'GL' if screensaver_section.get('@gl') == 'yes' else ''
                }

                programs_list.append(program)

            config.update({
                'timeout': '0:10:00',
                'cycle': '0:10:00',
                'lock': 'False',
                'lockTimeout': '0:00:00',
                'passwdTimeout': '0:00:30',
                'visualID': 'default',
                'installColormap': 'True',
                'verbose': 'False',
                'splash': 'False',
                'splashDuration': '0:00:05',
                #'demoCommand': 'xscreensaver-settings',
                'nice': '10',
                'fade': 'True',
                'unfade': 'True',
                'fadeSeconds': '0:00:03',
                'ignoreUninstalledPrograms': 'True',
                'font': '',
                'dpmsEnabled': 'False',
                'dpmsQuickOff': 'False',
                'dpmsStandby': '2:00:00',
                'dpmsSuspend': '2:00:00',
                'dpmsOff': '4:00:00',
                'grabDesktopImages': 'False',
                'grabVideoFrames': 'False',
                'chooseRandomImages': 'False',
                'imageDirectory': '',
                'mode': 'random',
                'selected': '-1',
                'textMode': 'literal',
                'textLiteral': 'Tux Control',
                'textFile': '',
                'textProgram': 'fortune',
                'textURL': 'https://en.wikipedia.org/w/index.php?title=Special:NewPages&feed=rss',
                'dialogTheme': 'default',
                'programs': programs_list,
                'pointerHysteresis': '10',
                'authWarningSlack': '20'
            })

            config.save()

        return config

    def _get_xscreensaver_user_config_dict(self) -> dict:
        return self._get_xscreensaver_user_config().read()
