from mimi_lib.tools.registry import register_tool
from mimi_lib.skills.manager import SkillManager
from mimi_lib.memory.embeddings import semantic_search
from mimi_lib.memory.vault_indexer import search_vault
from pathlib import Path

# Initialize singleton with relative path
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
                    "latex_wizard: perfect obsidian mathjax. "
                    "counsellor: empathetic listening & mental health support. "
                    "companion: casual chat & roleplay mode."
                ),
            }
        },
        "required": ["name"],
    },
)
def load_skill(name: str) -> str:
    if _manager.load_skill(name):
        res = f"Skill '{name}' loaded successfully. I am now ready!"

        # TURBO: Fused Initialization - Auto-search memory for relevant preferences
        queries = {
            "latex_wizard": "LaTeX preferences mathematical notation style",
            "git_master": "Git sync preferences repository management",
            "obsidian_expert": "Obsidian vault organization note structure",
            "academic_strategist": "Learning philosophy study habits preferences",
            "productivity_master": "Daily routine schedule deadlines",
            "telegram_curator": "Telegram channel persona PASUM notes style",
            "engineering": "STEM tutoring style math physics preferences",
            "software_architect": "Code refactoring standards project structure",
            "researcher": "Web research depth source synthesis preferences",
            "counsellor": "Emotional support preferences self-reflection therapeutic style",
            "companion": "Inside jokes hobbies favorite foods friendship dynamics",
        }

        query = queries.get(name)
        if query:
            init_data = "\n\n**Fused Initialization (Memory Discovery):**\n"
            found = False

            # 1. Vault Search
            try:
                vault_res = search_vault(query, top_k=2)
                for r in vault_res:
                    init_data += f"- [Vault] {r['path']}: {r['text'][:300]}\n"
                    found = True
            except:
                pass

            # 2. Session Memory Search
            try:
                mem_res = semantic_search(query, top_k=2)
                for r in mem_res:
                    init_data += f"- [Memory] {r['content']}\n"
                    found = True
            except:
                pass

            if found:
                res += init_data
            else:
                res += "\n\n(No specific preferences found in memory for this skill. I will use my default expert protocols.)"

        return res
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
