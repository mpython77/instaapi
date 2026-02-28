"""
Agent Plugin System — Custom Tool Registration
================================================
Allows users to register their own tools (functions)
that the agent can call during conversations.

Usage:
    agent.register_tool(
        name="translate",
        handler=my_translate_func,
        schema={"type": "object", "properties": {...}},
        description="Translate text between languages",
    )
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("instaharvest_v2.agent.plugins")


@dataclass
class PluginTool:
    """A user-registered tool (plugin)."""
    name: str
    handler: Callable
    description: str
    schema: Dict[str, Any]
    category: str = "custom"
    requires_permission: bool = False
    version: str = "1.0"

    def to_tool_schema(self) -> Dict:
        """Convert to the agent tool schema format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.schema,
        }


class PluginManager:
    """
    Manages user-registered plugins (custom tools).

    Usage:
        pm = PluginManager()

        # Register a tool
        pm.register(
            name="sentiment",
            handler=analyze_sentiment,
            description="Analyze text sentiment",
            schema={...},
        )

        # Check if tool exists
        if pm.has("sentiment"):
            result = pm.execute("sentiment", {"text": "Great post!"})

        # Get all plugin schemas for AI
        schemas = pm.get_tool_schemas()
    """

    def __init__(self):
        self._plugins: Dict[str, PluginTool] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        schema: Optional[Dict] = None,
        category: str = "custom",
        requires_permission: bool = False,
    ) -> PluginTool:
        """Register a new plugin tool."""
        if not callable(handler):
            raise TypeError(f"Handler for '{name}' must be callable")

        if name in self._plugins:
            logger.warning(f"Overwriting plugin: {name}")

        # Auto-generate schema if not provided
        if schema is None:
            schema = self._auto_schema(handler)

        plugin = PluginTool(
            name=name,
            handler=handler,
            description=description or f"Custom tool: {name}",
            schema=schema,
            category=category,
            requires_permission=requires_permission,
        )

        self._plugins[name] = plugin
        logger.info(f"Plugin registered: {name}")
        return plugin

    def unregister(self, name: str) -> bool:
        """Remove a registered plugin."""
        if name in self._plugins:
            del self._plugins[name]
            logger.info(f"Plugin unregistered: {name}")
            return True
        return False

    def has(self, name: str) -> bool:
        """Check if a plugin is registered."""
        return name in self._plugins

    def get(self, name: str) -> Optional[PluginTool]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def execute(self, name: str, args: Dict) -> Any:
        """Execute a plugin handler."""
        plugin = self._plugins.get(name)
        if not plugin:
            return f"Error: plugin '{name}' not found"

        try:
            result = plugin.handler(args)
            return result if result is not None else "Done"
        except Exception as e:
            logger.error(f"Plugin '{name}' error: {e}")
            return f"Plugin error: {e}"

    def get_tool_schemas(self) -> List[Dict]:
        """Get tool schemas for all registered plugins."""
        return [p.to_tool_schema() for p in self._plugins.values()]

    def list_plugins(self) -> List[Dict]:
        """List all registered plugins."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "version": p.version,
            }
            for p in self._plugins.values()
        ]

    @property
    def count(self) -> int:
        return len(self._plugins)

    @staticmethod
    def _auto_schema(handler: Callable) -> Dict:
        """Auto-generate a basic schema from function signature."""
        import inspect
        sig = inspect.signature(handler)
        properties = {}

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls", "args", "kwargs"):
                continue
            prop = {"type": "string", "description": param_name}
            if param.annotation != inspect.Parameter.empty:
                type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
                prop["type"] = type_map.get(param.annotation, "string")
            properties[param_name] = prop

        return {
            "type": "object",
            "properties": properties,
        }
