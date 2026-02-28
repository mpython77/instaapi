"""
Plugin System
=============
Extensible plugin architecture for instaharvest_v2.
Register plugins that hook into request/error lifecycle events.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaharvest_v2.plugin")


class Plugin:
    """
    Base class for instaharvest_v2 plugins.

    Subclass this to create custom plugins:

        class MyPlugin(Plugin):
            name = "my_plugin"

            def on_install(self, ig):
                print(f"Installed on {ig}")

            def on_request(self, event):
                print(f"Request to {event.endpoint}")

            def on_error(self, event):
                print(f"Error: {event.error}")
    """

    name: str = "unnamed_plugin"
    version: str = "1.0.0"
    description: str = ""

    def on_install(self, ig) -> None:
        """Called when plugin is installed via ig.use()."""
        pass

    def on_uninstall(self) -> None:
        """Called when plugin is removed."""
        pass

    def on_request(self, event) -> None:
        """Called on every request (EventType.REQUEST)."""
        pass

    def on_response(self, event) -> None:
        """Called on successful response."""
        pass

    def on_error(self, event) -> None:
        """Called on any error (EventType.ERROR)."""
        pass

    def on_retry(self, event) -> None:
        """Called on retry (EventType.RETRY)."""
        pass

    def on_rate_limit(self, event) -> None:
        """Called on rate limit (EventType.RATE_LIMIT)."""
        pass

    def on_challenge(self, event) -> None:
        """Called on challenge (EventType.CHALLENGE)."""
        pass

    def on_login_required(self, event) -> None:
        """Called on login required (EventType.LOGIN_REQUIRED)."""
        pass

    def __repr__(self) -> str:
        return f"Plugin({self.name} v{self.version})"


class PluginManager:
    """
    Manages plugin lifecycle.

    Usage:
        pm = PluginManager(event_emitter)
        pm.install(MyPlugin(), ig_instance)
        pm.uninstall("my_plugin")
        pm.list_plugins()
    """

    def __init__(self, event_emitter=None):
        self._plugins: Dict[str, Plugin] = {}
        self._events = event_emitter

    def install(self, plugin: Plugin, ig=None) -> None:
        """
        Install a plugin.

        Args:
            plugin: Plugin instance
            ig: Instagram/AsyncInstagram instance (passed to on_install)
        """
        if plugin.name in self._plugins:
            logger.warning(f"Plugin '{plugin.name}' already installed, replacing")
            self.uninstall(plugin.name)

        self._plugins[plugin.name] = plugin

        # Register event hooks
        if self._events:
            self._register_hooks(plugin)

        # Call on_install
        try:
            plugin.on_install(ig)
        except Exception as e:
            logger.error(f"Plugin '{plugin.name}' on_install error: {e}")

        logger.info(f"Plugin installed: {plugin}")

    def uninstall(self, name: str) -> bool:
        """
        Uninstall a plugin by name.

        Returns:
            True if plugin was found and removed
        """
        plugin = self._plugins.pop(name, None)
        if plugin:
            try:
                plugin.on_uninstall()
            except Exception as e:
                logger.error(f"Plugin '{name}' on_uninstall error: {e}")
            logger.info(f"Plugin uninstalled: {name}")
            return True
        return False

    def _register_hooks(self, plugin: Plugin) -> None:
        """Register plugin methods as event listeners."""
        from .events import EventType

        hook_map = {
            EventType.REQUEST: plugin.on_request,
            EventType.ERROR: plugin.on_error,
            EventType.RETRY: plugin.on_retry,
            EventType.RATE_LIMIT: plugin.on_rate_limit,
            EventType.CHALLENGE: plugin.on_challenge,
            EventType.LOGIN_REQUIRED: plugin.on_login_required,
        }

        for event_type, handler in hook_map.items():
            # Only register if method is overridden (not base Plugin)
            base_method = getattr(Plugin, handler.__name__, None)
            if handler.__func__ is not base_method:
                self._events.on(event_type, handler)

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[Dict[str, str]]:
        """List all installed plugins."""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
            }
            for p in self._plugins.values()
        ]

    @property
    def count(self) -> int:
        """Number of installed plugins."""
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        return name in self._plugins

    def __repr__(self) -> str:
        names = ", ".join(self._plugins.keys())
        return f"PluginManager([{names}])"
