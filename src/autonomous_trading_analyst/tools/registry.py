"""Central tool registry and LLM function-calling schema generator."""

import inspect
import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    """Specification of a tool callable by an LLM agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_function_calling_dict(self) -> dict[str, Any]:
        """Format as a standard LLM function calling declaration."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry maintaining tools, generating JSON schemas, and routing execution."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._arg_models: dict[str, type[BaseModel]] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        args_schema: type[BaseModel] | dict[str, Any] | None = None,
    ) -> None:
        """Register a tool with its handler and parameter schema."""
        tool_name = name.strip()
        if not tool_name:
            msg = "Tool name cannot be empty"
            raise ValueError(msg)

        schema: dict[str, Any]
        if isinstance(args_schema, type) and issubclass(args_schema, BaseModel):
            schema = args_schema.model_json_schema()
            # Clean pydantic schema titles if needed
            schema.pop("title", None)
            self._arg_models[tool_name] = args_schema
        elif isinstance(args_schema, dict):
            schema = args_schema
        else:
            schema = {"type": "object", "properties": {}}

        definition = ToolDefinition(
            name=tool_name,
            description=description.strip(),
            parameters=schema,
        )
        self._tools[tool_name] = definition
        self._handlers[tool_name] = handler

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        args_schema: type[BaseModel] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a function as a tool."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or func.__name__
            tool_doc = description or (func.__doc__ or "").strip() or f"Execute {tool_name}"
            self.register(tool_name, tool_doc, func, args_schema=args_schema)
            return func

        return decorator

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Lookup tool definition by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """Return list of all registered tool definitions."""
        return list(self._tools.values())

    def get_function_schemas(self) -> list[dict[str, Any]]:
        """Return list of LLM function calling schemas."""
        return [tool.to_function_calling_dict() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any] | str | None = None) -> str:
        """Execute a tool by name with arguments and format output as a string observation."""
        if name not in self._handlers:
            available = ", ".join(self._tools.keys()) or "none"
            return f"Error: Tool '{name}' not found. Available tools: {available}."

        handler = self._handlers[name]

        # Parse stringified JSON arguments if provided
        args_dict: dict[str, Any] = {}
        if isinstance(arguments, str):
            try:
                args_dict = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as exc:
                return f"Error: Arguments for tool '{name}' are not valid JSON: {exc}"
        elif isinstance(arguments, dict):
            args_dict = arguments

        # Validate with pydantic arg model if registered
        kwargs = args_dict
        if name in self._arg_models:
            arg_model = self._arg_models[name]
            try:
                validated = arg_model.model_validate(args_dict)
                kwargs = validated.model_dump()
            except Exception as exc:
                return f"Error: Invalid arguments for tool '{name}': {exc}"

        try:
            # Check if handler accepts kwargs
            sig = inspect.signature(handler)
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                res = handler(**kwargs)
            else:
                accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
                res = handler(**accepted)

            if isinstance(res, BaseModel):
                return res.model_dump_json(indent=2)
            if isinstance(res, (dict, list)):
                return json.dumps(res, default=str, indent=2)
            return str(res)
        except Exception as exc:
            return f"Error executing tool '{name}': {type(exc).__name__}: {exc}"
