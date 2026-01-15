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
                }
            },
            "func": func
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
        return _registry[name]["func"](**args)
    except Exception as e:
        return f"Error executing tool '{name}': {e}"
