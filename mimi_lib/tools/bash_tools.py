import subprocess
from mimi_lib.tools.registry import register_tool
from mimi_lib.config import PROJECT_ROOT


@register_tool(
    "bash",
    "Execute a bash command in the terminal. Use with caution.",
    {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The bash command to execute."}
        },
        "required": ["command"],
    },
)
def run_bash(command: str) -> str:
    """Executes a shell command and returns stdout/stderr."""
    try:
        # Run command in the project root by default
        result = subprocess.run(
            command,
            shell=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout safety
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[Stderr]:\n{result.stderr}"

        return (
            output.strip()
            if output.strip()
            else "[Command executed successfully with no output]"
        )
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 120 seconds."
    except Exception as e:
        return f"Error executing bash: {e}"
