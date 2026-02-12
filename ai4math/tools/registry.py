"""Tool registry system with automatic JSON Schema generation for LLM tool-calling."""

from __future__ import annotations

import inspect
import json
from typing import Any, Callable, get_type_hints

# Global registry
_REGISTRY: dict[str, dict[str, Any]] = {}


def _python_type_to_json_schema(py_type: Any) -> dict[str, str]:
    """Convert Python type annotations to JSON Schema types."""
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }
    # Handle Optional / Union with None
    origin = getattr(py_type, "__origin__", None)
    if origin is not None:
        args = getattr(py_type, "__args__", ())
        # list[X]
        if origin is list and args:
            return {"type": "array", "items": _python_type_to_json_schema(args[0])}
        # Optional[X] => Union[X, None]
        import types
        if origin is types.UnionType or (hasattr(origin, "__name__") and origin.__name__ == "Union"):
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return _python_type_to_json_schema(non_none[0])
    return type_map.get(py_type, {"type": "string"})


def _parse_docstring(docstring: str | None) -> tuple[str, dict[str, str]]:
    """Parse Google-style docstring to extract description and param descriptions.

    Returns:
        (function_description, {param_name: param_description})
    """
    if not docstring:
        return ("", {})

    lines = docstring.strip().split("\n")
    desc_lines: list[str] = []
    params: dict[str, str] = {}
    in_args = False
    current_param = ""

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("args:") or stripped.lower().startswith("parameters:"):
            in_args = True
            continue
        if stripped.lower().startswith("returns:") or stripped.lower().startswith("example"):
            in_args = False
            continue

        if in_args:
            # param line: "name (type): description" or "name: description"
            if ":" in stripped and not stripped.startswith(" ") and not stripped.startswith("\t"):
                # Could be a new param
                parts = stripped.split(":", 1)
                param_name = parts[0].strip()
                # Remove type annotations in parentheses
                if "(" in param_name:
                    param_name = param_name[: param_name.index("(")].strip()
                params[param_name] = parts[1].strip()
                current_param = param_name
            elif current_param:
                # Continuation of previous param
                params[current_param] += " " + stripped
        else:
            if stripped:
                desc_lines.append(stripped)

    return (" ".join(desc_lines), params)


def math_tool(
    name: str | None = None,
    category: str = "general",
    description: str | None = None,
):
    """Decorator to register a function as a math tool.

    Args:
        name: Tool name (defaults to function name).
        category: Tool category (analysis / algebra / probability / general).
        description: Override description (defaults to docstring).
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        doc_desc, param_docs = _parse_docstring(func.__doc__)
        tool_desc = description or doc_desc or f"Tool: {tool_name}"

        # Build JSON Schema for parameters
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_type = hints.get(param_name, str)
            schema = _python_type_to_json_schema(param_type)
            schema["description"] = param_docs.get(param_name, f"Parameter: {param_name}")
            properties[param_name] = schema

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        tool_schema = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_desc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

        _REGISTRY[tool_name] = {
            "func": func,
            "schema": tool_schema,
            "category": category,
        }
        # Attach metadata to function
        func._tool_name = tool_name
        func._tool_schema = tool_schema
        func._tool_category = category
        return func

    return decorator


class ToolRegistry:
    """Central registry for all math tools."""

    @staticmethod
    def get_all_schemas() -> list[dict]:
        """Get OpenAI-format tool schemas for all registered tools."""
        return [entry["schema"] for entry in _REGISTRY.values()]

    @staticmethod
    def get_schemas_by_category(category: str) -> list[dict]:
        """Get tool schemas filtered by category."""
        return [
            entry["schema"]
            for entry in _REGISTRY.values()
            if entry["category"] == category
        ]

    @staticmethod
    def call_tool(name: str, arguments: dict[str, Any]) -> str:
        """Call a registered tool by name with given arguments.

        Returns the result as a string.
        """
        if name not in _REGISTRY:
            return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
        try:
            func = _REGISTRY[name]["func"]
            result = func(**arguments)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @staticmethod
    def list_tools() -> list[dict[str, str]]:
        """List all registered tools with name, category, and description."""
        return [
            {
                "name": name,
                "category": entry["category"],
                "description": entry["schema"]["function"]["description"],
            }
            for name, entry in _REGISTRY.items()
        ]

    @staticmethod
    def get_tool_names() -> list[str]:
        """Get all registered tool names."""
        return list(_REGISTRY.keys())
