import json

_registry = {}


def register_tool(name, description, parameters):
    def decorator(func):
        _registry[name] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "func": func,
        }
        return func

    return decorator


def get_tool_definitions():
    return [t["definition"] for t in _registry.values()]


def execute_tool(name, arguments_json):
    if name not in _registry:
        return f"Error: Tool '{name}' not found."
    try:
        args = json.loads(arguments_json)
        result = _registry[name]["func"](**args)
        # Ensure result is a string for safe LLM consumption and UI display
        return str(result)
    except Exception as e:
        import traceback

        error_msg = f"Error executing tool '{name}': {str(e)}"
        print(f"[DEBUG] Tool Crash Traceback:\n{traceback.format_exc()}")
        return error_msg
