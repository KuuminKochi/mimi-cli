class SkillManager:
    def __init__(self, skills_dir):
        self.skills_dir = skills_dir
        self.active_skill = None

    def list_skills(self):
        import glob
        import os

        files = glob.glob(str(self.skills_dir / "*.md"))
        return [os.path.basename(f).replace(".md", "") for f in files]

    def load_skill(self, skill_name):
        if skill_name in self.list_skills():
            self.active_skill = skill_name
            return True
        return False

    def unload_skill(self):
        self.active_skill = None

    def get_active_skill_content(self):
        if not self.active_skill:
            return ""
        try:
            path = self.skills_dir / f"{self.active_skill}.md"
            with open(path, "r", encoding="utf-8") as f:
                return (
                    f"\n\n**[ACTIVE SKILL: {self.active_skill.upper()}]**\n{f.read()}"
                )
        except:
            return ""
