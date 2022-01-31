from typing import List
from tux_control.plugin.IPluginConfigItem import IPluginConfigItem
from tux_control.plugin.PluginConfigOption import PluginConfigOption


class PluginConfigItem(IPluginConfigItem):
    name = None
    key = None
    plugin_config_options = None
    is_deletable = False
    is_editable = True

    def __init__(self, name: str, key: str, description: str, plugin_config_options: List[PluginConfigOption] = None, is_enabled: bool = False, is_selected: bool = False):
        self.name = name
        self.key = key
        self.description = description
        self.plugin_config_options = plugin_config_options
        self.is_enabled = is_enabled
        self.is_selected = is_selected

    @staticmethod
    def from_dict(data: dict) -> 'PluginConfigItem':
        is_enabled = False
        is_selected = False
        plugin_config_options = []
        for item in data.get('plugin_config_options'):
            plugin_config_option = PluginConfigOption.from_dict(item)
            if plugin_config_option.key == 'is_enabled':
                is_enabled = plugin_config_option.value

            if plugin_config_option.key == 'is_selected':
                is_selected = plugin_config_option.value

            plugin_config_options.append(plugin_config_option)

        name = data.get('name')
        key = data.get('key')
        description = data.get('description')

        return PluginConfigItem(
            name=name,
            key=key,
            description=description,
            plugin_config_options=plugin_config_options,
            is_enabled=is_enabled,
            is_selected=is_selected
        )

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'key': self.key,
            'description': self.description,
            'is_deletable': self.is_deletable,
            'is_editable': self.is_editable,
            'plugin_config_options': self.plugin_config_options,
            'is_enabled': self.is_enabled,
            'is_selected': self.is_selected
        }

