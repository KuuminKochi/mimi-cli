from mimi_lib.tools.registry import register_tool
from mimi_lib.skills.manager import SkillManager
from pathlib import Path

# Initialize singleton with relative path
# Assuming this file is in mimi_lib/tools/, skills are in ../skills/
SKILLS_DIR = Path(__file__).parent.parent / "skills"
_manager = SkillManager(SKILLS_DIR)


@register_tool(
    "load_skill",
    "Switch to a specialized mindset or expert persona. CRITICAL: Load this FIRST when a task fits a specialized domain (Math, Git, Obsidian, etc.) to enable advanced formatting and logic.",
    {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "enum": _manager.list_skills(),
                "description": (
                    "The expert persona to load. "
                    "researcher: deep dives & source synthesis. "
                    "engineering: math, physics, chemistry. "
                    "cli_wizard: system tasks & bash. "
                    "git_master: git version control & sync handling. "
                    "obsidian_expert: vault organization. "
                    "software_architect: codebase refactoring. "
                    "academic_strategist: first principles & recall guides. "
                    "productivity_master: tactical scheduling. "
                    "telegram_curator: community post drafting. "
                    "latex_wizard: perfect obsidian mathjax."
                ),
            }
        },
        "required": ["name"],
    },
)
def load_skill(name: str) -> str:
    if _manager.load_skill(name):
        return f"Skill '{name}' loaded successfully. I am now ready!"
    return f"Error: Skill '{name}' not found. Available: {_manager.list_skills()}"


@register_tool(
    "unload_skill",
    "Deactivate the current skill and return to default persona.",
    {"type": "object", "properties": {}},
)
def unload_skill() -> str:
    _manager.unload_skill()
    return "Skill unloaded. Back to normal Mimi!"


@register_tool(
    "list_skills",
    "List all available specialized skills.",
    {"type": "object", "properties": {}},
)
def list_skills() -> str:
    skills = _manager.list_skills()
    current = _manager.active_skill
    return f"Available Skills: {', '.join(skills)}\nActive Skill: {current or 'None'}"


def get_current_skill_content():
    return _manager.get_active_skill_content()


def get_active_skill_name():
    return _manager.active_skill
