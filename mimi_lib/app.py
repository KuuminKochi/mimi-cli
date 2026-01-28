import os
import re
import sys
import json
import threading
import concurrent.futures
import textwrap
from datetime import datetime

from typing import List, Dict, Any, Optional
from pathlib import Path

from mimi_lib.config import SESSION_DIR, WORKING_SET_FILE, VAULT_PATH, get_config
from mimi_lib.config_extended import MODEL_ALIASES, resolve_alias
from mimi_lib.ui.ansi import clear_screen
from mimi_lib.ui.input import VimInput
from mimi_lib.ui.printer import StreamPrinter
from mimi_lib.ui.pager import Pager
from mimi_lib.utils.text import Colors, get_layout, visible_len, visible_wrap
from mimi_lib.memory.brain import load_system_prompt, save_memory, load_json, save_json
from mimi_lib.memory.embeddings import semantic_search
from mimi_lib.api.provider import call_api
from mimi_lib.api.generic import call_generic_api
from mimi_lib.utils.system import get_sys_info

# Import tools to trigger registration
import mimi_lib.tools.file_tools
import mimi_lib.tools.web_tools
import mimi_lib.tools.memory_tools
import mimi_lib.tools.note_tools
import mimi_lib.tools.vision_tools
import mimi_lib.tools.skill_tools
import mimi_lib.tools.research_tools
import mimi_lib.tools.bash_tools
from mimi_lib.tools.registry import get_tool_definitions, execute_tool
from mimi_lib.tools.skill_tools import get_current_skill_content, get_active_skill_name

from mimi_lib.ui.session import SessionSelector

# Define Vault Session Directory here if not yet in config
VAULT_SESSION_DIR = VAULT_PATH / "Mimi/Sessions"


class MimiApp:
    def __init__(self):
        self.config = get_config()
        self.history: List[Dict[str, Any]] = []
        self.cur_model = "chat"
        self.smart_mode = True  # Default to Intelligent Routing
        self.active_turn_model = self.cur_model  # Track resolved model for UI
        self.search_active = False
        self.thinking_mode = False
        self.autorename = True
        self.session_file = f"Session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"
        self.save_path = SESSION_DIR / self.session_file

        # Vault Sync setup
        if not VAULT_SESSION_DIR.exists():
            VAULT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
        self.vault_save_path = VAULT_SESSION_DIR / self.session_file

        self.input_handler = VimInput()
        self.print_lock = threading.Lock()
        self.session_chronicle = ""
        self.pending_summary_update = None  # (summary, count)
        self.is_summarizing = False  # Lock to prevent storms
        self.working_set = self._load_working_set()

        # Git Sync Logic
        self.msg_counter = 0
        self.sync_interval = 10

        # Populate working set with initial task if empty
        if not self.working_set:
            self._update_working_set(
                [
                    "mimi_lib/app.py",
                    "mimi_lib/memory/brain.py",
                    "data/system_prompt.md",
                ],
                context="Implementing Zenith Working Memory & Toolcall Pruning",
            )

    def _load_working_set(self) -> Dict[str, Any]:
        return load_json(WORKING_SET_FILE, default={})

    def _save_working_set(self):
        save_json(WORKING_SET_FILE, self.working_set)

    def _update_working_set(self, paths: List[str] = None, context: str = None):
        """Updates the working set with new paths or task context."""
        changed = False
        if context:
            self.working_set["current_task"] = context
            changed = True

        if paths:
            if "files" not in self.working_set:
                self.working_set["files"] = {}

            for p in paths:
                # Normalize path
                p_str = (
                    str(p)
                    .replace(
                        str(
                            self.config["PROJECT_ROOT"]
                            if "PROJECT_ROOT" in self.config
                            else ""
                        ),
                        "",
                    )
                    .strip("/")
                )
                # Simple timestamp for LRU-like behavior
                self.working_set["files"][p_str] = int(datetime.now().timestamp())
                changed = True

        if changed:
            self._save_working_set()

    def _get_working_set_context(self) -> str:
        """Formats the working set for the system prompt."""
        ws = self.working_set
        if not ws:
            return ""

        ctx = "\n\n**Active Context (Working Set):**\n"
        if "current_task" in ws:
            ctx += f"Current Task: {ws['current_task']}\n"

        if "files" in ws and ws["files"]:
            # Sort by recent access
            sorted_files = sorted(
                ws["files"].items(), key=lambda x: x[1], reverse=True
            )[:10]
            ctx += "Active Files:\n"
            for f, _ in sorted_files:
                ctx += f"- {f}\n"

        return ctx

    def _resolve_model(self, user_input: str) -> str:
        """Intelligently routes between Instant (chat) and Reasoning models."""
        if not self.smart_mode:
            return self.cur_model

        active_skill = get_active_skill_name()

        # 1. Skill-Based Routing
        instant_skills = [
            "counsellor",
            "companion",
            "telegram_curator",
            "productivity_master",
            "cli_wizard",
        ]
        reasoning_skills = [
            "engineering",
            "software_architect",
            "researcher",
            "academic_strategist",
            "latex_wizard",
        ]

        if active_skill in instant_skills:
            return "chat"
        if active_skill in reasoning_skills:
            return "reasoner"

        # 2. Heuristic Fallback (No Skill)
        text = user_input.lower()

        # Explicit Reasoning Triggers - Very Strict
        # Only triggers on explicit reasoning requests
        explicit_reasoning_phrases = [
            "step by step",
            "think through",
            "reason about",
            "work out",
            "carefully analyze",
            "explain your reasoning",
            "show your work",
        ]

        if any(phrase in text for phrase in explicit_reasoning_phrases):
            return "reasoner"

        # Explicit Instant Triggers
        instant_keywords = [
            "hi",
            "hello",
            "hey",
            "thanks",
            "ok",
            "cool",
            "list",
            "what is",
            "who is",
            "help",
        ]
        if any(text.startswith(w) for w in instant_keywords):
            return "chat"

        # Default to Chat for speed and efficiency
        return "chat"

    def run(self):
        clear_screen()
        print(f"\n{Colors.CYAN}Mimi Cyber-TTY Zenith v6.1 (Intelligent){Colors.RESET}")
        print(
            f"{Colors.DIM}Router: {'ON' if self.smart_mode else 'OFF'} | File: {self.session_file}{Colors.RESET}\n"
        )

        self.history = [{"role": "system", "content": load_system_prompt()}]

        # Trigger initial vault index in background
        from mimi_lib.memory.vault_indexer import trigger_background_index

        trigger_background_index()

        while True:
            width, indent, _, _ = get_layout(self.config)
            print(f"\n{indent}{self.get_status_bar()}")
            print(f"{indent}{Colors.GREEN}[USER: Kuumin]{Colors.RESET}")

            # Apply pending summary updates safely in main thread
            if self.pending_summary_update:
                summary, count = self.pending_summary_update
                self.session_chronicle += f"\n- {summary}"
                # Prune history safely (Keep system [0], remove [1:count+1], keep rest)
                self.history = [self.history[0]] + self.history[count + 1 :]
                self.pending_summary_update = None
                with self.print_lock:
                    print(f"{indent}{Colors.DIM}[Memory Compacted]{Colors.RESET}")

            user_input = self.input_handler.get_input(
                f"{indent}> ",
                indent,
                width,
                [m["content"] for m in self.history if m["role"] == "user"],
            )

            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                if self.handle_command(user_input, indent):
                    continue
                else:
                    self._check_sync_trigger(force=True)
                    break

            # RAG / Reminiscence
            reminiscence = self.get_reminiscence(user_input)

            # Context Composition
            system_msg = load_system_prompt()

            # Inject Working Set (Dynamic Context)
            ws_context = self._get_working_set_context()
            if ws_context:
                system_msg += ws_context

            # Inject Skill
            skill_content = get_current_skill_content()
            if skill_content:
                system_msg += skill_content

            if self.session_chronicle:
                system_msg += (
                    f"\n\n**Chronicle (Previous Context):**\n{self.session_chronicle}"
                )

            if reminiscence:
                system_msg += f"\n{reminiscence}"

            self.history[0]["content"] = system_msg

            self.history.append({"role": "user", "content": user_input})
            self.autosave("Kuumin", user_input)

            # Recursive Summary Check
            if len(self.history) > 80 and not self.is_summarizing:
                threading.Thread(target=self._summarize_history, daemon=True).start()

            self.generate_response(width, indent)

            # Check for Git Sync Trigger
            self.msg_counter += 1
            self._check_sync_trigger()

    def _check_sync_trigger(self, force: bool = False):
        if force or (
            self.msg_counter > 0 and self.msg_counter % self.sync_interval == 0
        ):
            threading.Thread(
                target=self._run_background_sync,
                args=(f"Auto-sync session {self.session_file}",),
                daemon=True,
            ).start()

    def _run_background_sync(self, msg: str):
        # Git sync disabled
        pass

    def _summarize_history(self):
        """Compresses old history into the session chronicle."""
        if self.is_summarizing:
            return
        self.is_summarizing = True
        try:
            # Select messages to compress (Skip system [0], take next 40)
            to_compress = self.history[1:41]
            if not to_compress:
                return

            # Format for LLM
            block = ""
            for m in to_compress:
                role = m["role"]
                content = m.get("content", "") or "[Tool Output]"
                block += f"{role}: {content[:500]}\n"

            # Notify User
            width, indent, _, _ = get_layout(self.config)
            with self.print_lock:
                print(
                    f"{indent}{Colors.MAGENTA}✿ I'm compressing my memory to stay fast! 🧠{Colors.RESET}"
                )

            # Call Fast LLM
            prompt = f"Summarize these early conversation turns into a concise narrative paragraph. Preserve key facts and decisions.\n\n{block}"
            res = call_api(
                [{"role": "user", "content": prompt}],
                model="deepseek-chat",
                stream=False,
            )

            if res and res.status_code == 200:
                summary = res.json()["choices"][0]["message"]["content"]
                # Store update for main thread
                self.pending_summary_update = (summary, len(to_compress))

        except Exception as e:
            # Print error for debugging
            with self.print_lock:
                print(
                    f"{Colors.RED}[DEBUG] Memory Compression Failed: {e}{Colors.RESET}"
                )
        finally:
            self.is_summarizing = False

    def get_status_bar(self):
        now = datetime.now().strftime("%H:%M")
        s_text = "[W:ON]" if self.search_active else "[W:OFF]"
        # t_text = "[T:ON]" if self.thinking_mode else "[T:OFF]"

        # Model Indicator
        model_short = "THINK" if "reasoner" in self.active_turn_model else "FAST"
        m_text = f"[M:{model_short}]"

        # Skill Indicator
        active_skill = get_active_skill_name()
        skill_text = f"[SKILL: {active_skill.upper()}]" if active_skill else ""

        sys = get_sys_info()
        return (
            f"{Colors.CYAN}[{now}]{Colors.RESET} {m_text} {s_text} {Colors.YELLOW}{skill_text}{Colors.RESET} | "
            f"BAT: {sys['bat']} | CPU: {sys['cpu']} | MEM: {sys['mem']} | WIFI: {sys['wifi']} | "
            f"{Colors.GREEN}SYS: ONLINE{Colors.RESET}"
        )

    def load_session_from_file(self, filename: str):
        filepath = SESSION_DIR / filename
        if not filepath.exists():
            return None

        history = [{"role": "system", "content": load_system_prompt()}]
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            current_role = None
            current_content = []

            for line in lines:
                line = line.strip()
                if line.startswith("**Kuumin**"):
                    if current_role and current_content:
                        history.append(
                            {
                                "role": current_role,
                                "content": "\n".join(current_content),
                            }
                        )
                    current_role = "user"
                    current_content = []
                elif line.startswith("**Mimi**"):
                    if current_role and current_content:
                        history.append(
                            {
                                "role": current_role,
                                "content": "\n".join(current_content),
                            }
                        )
                    current_role = "assistant"
                    current_content = []
                elif line:
                    current_content.append(line)

            if current_role and current_content:
                history.append(
                    {"role": current_role, "content": "\n".join(current_content)}
                )

            return history
        except:
            return None

    def handle_command(self, cmd_str, indent):
        cmd = cmd_str.split()
        if cmd[0] == "/exit":
            return False
        elif cmd[0] == "/clear":
            clear_screen()
        elif cmd[0] == "/help":
            print(f"{indent}Available Commands:")
            print(f"{indent}  /session [list] - Manage sessions")
            print(f"{indent}  /history        - View conversation history")
            print(f"{indent}  /smart          - Toggle Intelligent Routing")
            print(f"{indent}  /thinking       - Toggle Thinking Mode")
            print(f"{indent}  /new            - Start fresh session")
            print(f"{indent}  /regen          - Regenerate last response")
            print(f"{indent}  /model [name]   - List or switch AI model")
            print(f"{indent}  /autorename     - Toggle auto-renaming")
            print(f"{indent}  /prep           - Run 'git_pull_lecture_guides' routine")
            print(f"{indent}  /clear          - Clear screen")
            print(f"{indent}  /exit           - Quit")
        elif cmd[0] == "/prep":
            self.history.append(
                {
                    "role": "user",
                    "content": (
                        "Execute the 'git_pull_lecture_guides' routine as defined in "
                        "[[Mimi/Sessions/git_pull_lecture_guides.md]].\n\n"
                        "CRITICAL: Start by using 'load_skill' for 'git_master' to sync. "
                        "Follow the steps exactly:\n"
                        "1. Load 'git_master' -> 'sync_vault' (pull).\n"
                        "2. Identify the new lecture folder and read raw materials.\n"
                        "3. Load 'academic_strategist' and 'latex_wizard' -> Create first principles guides with Obsidian-perfect LaTeX.\n"
                        "4. Load 'productivity_master' -> Setup tomorrow's daily note based on today's note and tutorial deadlines in memory.\n"
                        "5. Load 'telegram_curator' -> Prepare community posts if applicable.\n"
                        "6. Sync back."
                    ),
                }
            )
            self.generate_response(get_layout(self.config)[0], indent)
        elif cmd[0] == "/autorename":
            if len(cmd) > 1:
                self.autorename = cmd[1].lower() == "on"
            else:
                self.autorename = not self.autorename
            print(f"{indent}Auto-rename: {'ON' if self.autorename else 'OFF'}")
        elif cmd[0].startswith("/session"):
            selector = SessionSelector(SESSION_DIR)
            selected = selector.select_session()
            if selected:
                new_h = self.load_session_from_file(selected)
                if new_h:
                    self.history = new_h
                    self.session_file = selected
                    self.save_path = SESSION_DIR / selected
                    self.vault_save_path = VAULT_SESSION_DIR / selected
                    self.run_pager()
            clear_screen()
        elif cmd[0] == "/history":
            self.run_pager()
        elif cmd[0] == "/search":
            self.search_active = not self.search_active
            print(f"{indent}Search: {'ON' if self.search_active else 'OFF'}")
        elif cmd[0] == "/thinking":
            self.thinking_mode = not self.thinking_mode
            print(f"{indent}Thinking Mode: {'ON' if self.thinking_mode else 'OFF'}")
        elif cmd[0] == "/smart":
            self.smart_mode = not self.smart_mode
            print(f"{indent}Smart Routing: {'ON' if self.smart_mode else 'OFF'}")
        elif cmd[0] == "/model":
            if len(cmd) == 1:
                self._list_models(indent)
            else:
                self._switch_model(cmd[1], indent)
        elif cmd[0] == "/new":
            self.session_file = (
                f"Session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"
            )
            self.save_path = SESSION_DIR / self.session_file
            self.vault_save_path = VAULT_SESSION_DIR / self.session_file
            self.history = [{"role": "system", "content": load_system_prompt()}]
            clear_screen()
            print(
                f"\n{Colors.CYAN}[ NEW SESSION: {self.session_file} ]{Colors.RESET}\n"
            )
        elif cmd[0] == "/regen":
            if len(self.history) > 1:
                for i in range(len(self.history) - 1, -1, -1):
                    if self.history[i]["role"] == "user":
                        user_input = self.history[i]["content"]
                        self.history = self.history[: i + 1]
                        print(f"{indent}Regenerating last turn...")
                        self.generate_response(get_layout(self.config)[0], indent)
                        break
        return True

    def run_pager(self):
        # Implementation of the new interactive pager
        pager = Pager(self.history, self.config)
        pager.run()

    def check_autorename(self):
        if not self.autorename:
            return
        if not self.session_file.startswith("Session_"):
            return
        # Check if we have enough context (System + User + Assistant)
        if len(self.history) >= 3:
            # Check if we haven't renamed it yet (double check pattern)
            if "Session_" not in self.session_file:
                return

            # Start background rename
            threading.Thread(target=self._perform_autorename, daemon=True).start()

    def _perform_autorename(self):
        try:
            # Construct context from first exchange
            context = ""
            for m in self.history[1:3]:  # Skip system, get User + First Response
                role = m["role"]
                content = m.get("content") or ""
                if not content and role == "assistant" and "tool_calls" in m:
                    content = "[Tool Calls]"
                context += f"{role}: {content[:200]}\n"

            prompt = "Summarize this conversation into a concise 3-5 word filename (snake_case, no extension). Output ONLY the filename, no other text or code blocks."
            messages = [
                {
                    "role": "system",
                    "content": "You are a filename generator. Output ONLY the filename.",
                },
                {"role": "user", "content": f"{prompt}\n\nContext:\n{context}"},
            ]

            res = call_api(messages, model="deepseek-chat", stream=False)
            if res and res.status_code == 200:
                raw_content = res.json()["choices"][0]["message"]["content"].strip()
                # Remove markdown code blocks if present
                new_name = (
                    re.sub(r"```[a-z]*\n?", "", raw_content).replace("```", "").strip()
                )

                # Sanitize
                valid_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                new_name = (
                    "".join(c for c in new_name if c in valid_chars)
                    .replace(" ", "_")
                    .lower()
                )
                if not new_name.endswith(".md"):
                    new_name += ".md"
                if len(new_name) > 50:
                    new_name = new_name[:46] + ".md"  # Cap length

                # Perform rename
                old_path = self.save_path
                new_path = SESSION_DIR / new_name

                old_vault_path = self.vault_save_path
                new_vault_path = VAULT_SESSION_DIR / new_name

                if old_path.exists() and not new_path.exists():
                    os.rename(old_path, new_path)
                    self.session_file = new_name
                    self.save_path = new_path
                    self.vault_save_path = new_vault_path  # Update vault path reference

                    # Also rename vault file if it exists
                    if old_vault_path.exists():
                        os.rename(old_vault_path, new_vault_path)

                    with self.print_lock:
                        print(
                            f"\n{Colors.DIM}[ RENAMED session to: {new_name} ]{Colors.RESET}"
                        )

                    # Trigger a sync after rename
                    self._check_sync_trigger(force=True)

        except Exception as e:
            pass  # Fail silently for auto-rename

    def _list_models(self, indent):
        """Display available models with aliases."""
        print(f"{indent}Available Models:")
        print(f"{indent}{'─' * 50}")

        for alias, info in MODEL_ALIASES.items():
            marker = (
                f"{Colors.GREEN}[ACTIVE]{Colors.RESET}"
                if alias == self.cur_model
                else "       "
            )
            provider = info["provider"].upper()
            desc = info["description"]
            full_id = info["id"]
            print(f"{indent}  {marker} {alias}")
            print(
                f"{indent}          {Colors.DIM}ID: {full_id} | Provider: {provider} | {desc}{Colors.RESET}"
            )

    def _switch_model(self, model_arg, indent):
        """Switch to specified model by alias or full ID."""
        if self.smart_mode:
            self.smart_mode = False
            print(
                f"{indent}{Colors.YELLOW}Smart routing disabled for manual model selection{Colors.RESET}\n"
            )

        model_config = resolve_alias(model_arg)

        if model_config:
            self.cur_model = model_arg
            print(
                f"{indent}Switched base model to: {Colors.CYAN}{model_arg}{Colors.RESET}"
            )
            print(
                f"{indent}  {Colors.DIM}({model_config['description']}){Colors.RESET}"
            )
        else:
            self.cur_model = model_arg
            print(
                f"{indent}Switched base model to: {Colors.CYAN}{model_arg}{Colors.RESET}"
            )

    def generate_response(self, width, indent):
        # Skill Heuristic Check
        messages_to_send = list(self.history)
        active_skill = get_active_skill_name()

        content = ""
        if self.history and self.history[-1]["role"] == "user":
            content = self.history[-1]["content"].lower()

        # Update Router State
        self.active_turn_model = self._resolve_model(content)

        triggers = {
            "software_architect": [
                "refactor",
                "code",
                "class",
                "function",
                "api",
                "impl",
                "bug",
                "fix",
            ],
            "researcher": ["research", "find", "search", "investigate", "summary"],
            "cli_wizard": ["bash", "linux", "terminal", "script", "install", "env"],
            "git_master": [
                "git",
                "sync",
                "push",
                "pull",
                "commit",
                "branch",
                "conflict",
            ],
            "obsidian_expert": ["vault", "note", "obsidian", "link", "markdown"],
            "engineering": [
                "math",
                "physics",
                "chemistry",
                "stem",
                "tutorial",
                "latex",
            ],
            "academic_strategist": [
                "anki",
                "flashcard",
                "recall",
                "exam",
                "quiz",
                "strategy",
                "lecture guide",
            ],
            "productivity_master": [
                "schedule",
                "deadline",
                "priority",
                "todo",
                "tutorial",
                "daily note",
            ],
            "telegram_curator": [
                "telegram",
                "channel",
                "post",
                "share",
                "community",
                "pasum notes",
            ],
            "latex_wizard": [
                "equation",
                "formula",
                "derivation",
                "align",
                "typeset",
                "mathjax",
            ],
            "counsellor": [
                "sad",
                "depressed",
                "anxious",
                "stress",
                "tired",
                "burnout",
                "vent",
                "cry",
                "feel",
                "worry",
                "hopeless",
            ],
            "companion": [
                "let's play",
                "roleplay",
                "pretend",
                "hang out",
                "bored",
                "coffee",
                "gossip",
                "movie",
                "game",
            ],
        }

        relevant_skills = [
            s for s, kws in triggers.items() if any(kw in content for kw in kws)
        ]

        if relevant_skills:
            if not active_skill:
                # Special prompt for Soft Skills
                if "counsellor" in relevant_skills:
                    hint = (
                        f"** SKILL ADVISORY **\n"
                        f"It seems you are expressing strong emotions. "
                        f"Mimi has a 'counsellor' skill designed for supportive listening. "
                        f"Consider using `load_skill(name='counsellor')`."
                    )
                elif "companion" in relevant_skills:
                    hint = (
                        f"** SKILL ADVISORY **\n"
                        f"Sounds like fun! "
                        f"Mimi has a 'companion' skill for casual chats and roleplay. "
                        f"Consider using `load_skill(name='companion')` to vibe."
                    )
                else:
                    hint = (
                        f"** MANDATORY SKILL PROTOCOL **\n"
                        f"Task detected: {', '.join(relevant_skills)}.\n"
                        f"You MUST use 'load_skill' to activate the corresponding expert mindset "
                        f"BEFORE executing any other tools. This ensures project standards are met."
                    )
                messages_to_send.append({"role": "system", "content": hint})
            elif active_skill not in relevant_skills:
                # Don't nag if compatible (e.g. companion and counsellor are both soft)
                soft_skills = ["companion", "counsellor"]
                if not (
                    active_skill in soft_skills
                    and any(s in soft_skills for s in relevant_skills)
                ):
                    hint = (
                        f"** SKILL ADVISORY **\n"
                        f"You are currently using '{active_skill}', but the task seems to involve '{', '.join(relevant_skills)}'. "
                        f"Consider if you should 'unload_skill' and 'load_skill' for the new domain."
                    )
                    messages_to_send.append({"role": "system", "content": hint})

        while True:
            printer = StreamPrinter(width, indent, "Mimi")

            # --- TOOL FILTERING FOR SOFT SKILLS ---
            all_tools = get_tool_definitions()
            tools_to_use = all_tools

            soft_skills = ["counsellor", "companion"]

            if active_skill in soft_skills:
                # Allowed: Memory, Vault, Notes, Skill management + Web (for companion)
                allowed_tools = [
                    "load_skill",
                    "unload_skill",
                    "list_skills",
                    "add_memory",
                    "search_memory",
                    "vault_search",
                    "vault_query",
                    "add_note",
                    "delete_note",
                ]
                if active_skill == "companion":
                    allowed_tools.extend(
                        ["web_search", "describe_image"]
                    )  # Companion can look up memes/images

                tools_to_use = [
                    t for t in all_tools if t["function"]["name"] in allowed_tools
                ]

            # Resolve alias to full model ID and route to appropriate handler
            alias = self.active_turn_model
            model_config = resolve_alias(alias)
            full_model_id = model_config["id"] if model_config else alias

            if full_model_id.startswith("deepseek"):
                response = call_api(
                    messages_to_send,
                    model=full_model_id,
                    stream=True,
                    tools=tools_to_use,
                )
            else:
                response = call_generic_api(
                    messages_to_send,
                    model=full_model_id,
                    stream=True,
                    tools=tools_to_use,
                )
            if not response:
                break

            full_res, full_reasoning, tool_calls = "", "", []

            try:
                for line in response.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                    if line == "[DONE]":
                        break

                    try:
                        delta = json.loads(line)["choices"][0]["delta"]

                        # Reasoning
                        reason = delta.get("reasoning_content") or delta.get(
                            "reasoning"
                        )
                        if reason:
                            full_reasoning += reason
                            printer.process(reason, reasoning=True)

                        # Content
                        content = delta.get("content")
                        if content:
                            full_res += content
                            printer.process(content)

                        # Tool Calls
                        if "tool_calls" in delta:
                            for tc in delta["tool_calls"]:
                                idx = tc["index"]
                                while len(tool_calls) <= idx:
                                    tool_calls.append(
                                        {
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    )
                                if "id" in tc:
                                    tool_calls[idx]["id"] += tc["id"]
                                if "function" in tc:
                                    if "name" in tc["function"]:
                                        tool_calls[idx]["function"]["name"] += tc[
                                            "function"
                                        ]["name"]
                                    if "arguments" in tc["function"]:
                                        tool_calls[idx]["function"]["arguments"] += tc[
                                            "function"
                                        ]["arguments"]
                    except:
                        pass
            except KeyboardInterrupt:
                print("\n[Interrupted]")
            finally:
                printer.finish()

            if tool_calls:
                # Add assistant tool call to history
                # NOTE: We must add to both self.history (persistence) and messages_to_send (loop context)
                assistant_msg = {
                    "role": "assistant",
                    "content": full_res or None,
                    "tool_calls": tool_calls,
                    "reasoning_content": full_reasoning if full_reasoning else None,
                }
                self.history.append(assistant_msg)
                messages_to_send.append(assistant_msg)

                # Execute tools in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {
                        executor.submit(self.run_tool, tc, indent): tc
                        for tc in tool_calls
                    }
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        self.history.append(result)
                        messages_to_send.append(result)
                continue  # Generate follow-up response after tool results
            else:
                self.history.append({"role": "assistant", "content": full_res})
                self.autosave("Mimi", full_res)
                self.check_autorename()
                break

    def run_tool(self, tc, indent):
        name = tc["function"]["name"]
        args = tc["function"]["arguments"]

        # Sniff paths for Working Set
        try:
            arg_data = json.loads(args)
            paths_found = []
            for key in ["path", "filePath", "file_path"]:
                if key in arg_data:
                    paths_found.append(arg_data[key])
            if "paths" in arg_data and isinstance(arg_data["paths"], list):
                paths_found.extend(arg_data["paths"])

            if paths_found:
                self._update_working_set(paths_found)
        except:
            pass

        # Mimi Personality Mapping for Tools
        personality_map = {
            "web_search": "I'm going online to find some answers for us! 🌐",
            "web_batch_search": "Searching a few places at once to be extra thorough! 🚀",
            "web_fetch": "Reading this page carefully to see what I can find! 📖",
            "vault_search": "Let me look through my memories for a second... 🔍",
            "vault_query": "Digging through our notes for you! 📂",
            "add_memory": "I'll make sure to remember this! ✿",
            "delete_memory": "Removing that from my memory bank... ⌫",
            "search_memory": "Thinking back to our past conversations... 💭",
            "add_note": "Writing a quick note so we don't forget! ✍️",
            "delete_note": "Ticking that off our list! ✅",
            "read_file": "Let me take a look at this file... 📄",
            "write_file": "Writing this down for you! 🖊️",
            "edit_file": "Just making a quick adjustment here! 🛠️",
            "list_directory": "Checking what's inside this folder... 📁",
            "search_files": "Looking for that specific file... 🔎",
            "get_codebase_index": "Getting a bird's eye view of the code! 🗺️",
            "describe_image": "Taking a look at this image... 👁️",
            "load_skill": "Putting on my expert hat! 🧢",
            "unload_skill": "Taking off the expert hat, just being me again! 🎀",
            "list_skills": "Checking what skills I can learn... 📚",
            "deep_research": "Putting on my detective coat! 🕵️‍♀️",
            "list_signed_files": "Let me see which files I've worked on... ✿",
            "bash": "Executing a command in the terminal! 💻",
            "memory_search_nodes": "Searching my Knowledge Graph for you! 🧠",
            "memory_open_nodes": "Opening up specific memory nodes! 📂",
            "memory_add_observations": "Adding some new observations to my memory! 📝",
        }

        cute_msg = personality_map.get(name, "Using a tool to help you out! ✿")

        with self.print_lock:
            print(
                f"{indent}{Colors.MAGENTA}✿ {cute_msg}{Colors.RESET} {Colors.DIM}[{name}]{Colors.RESET}"
            )

        try:
            content = execute_tool(name, args)

            # Show error in red if tool execution failed
            if str(content).startswith("Error"):
                with self.print_lock:
                    print(f"{indent}{Colors.RED}!! Oh no! {content}{Colors.RESET}")

            return {
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": str(content),
            }
        except Exception as e:
            # Absolute fallback to prevent thread crash
            err_msg = f"Error: Unexpected crash in tool runner: {e}"
            with self.print_lock:
                print(f"{indent}{Colors.RED}!! Critical Error: {err_msg}{Colors.RESET}")
            return {
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": err_msg,
            }

    def get_reminiscence(self, user_input):
        # Intent Detection: Skip RAG for short/trivial inputs
        if len(user_input.split()) < 3 and user_input.lower() in [
            "hi",
            "hello",
            "ok",
            "okay",
            "thanks",
            "yes",
            "no",
        ]:
            return ""

        from mimi_lib.memory.brain import get_literal_matches
        from mimi_lib.memory.vault_indexer import search_vault
        from mimi_lib.memory.embeddings import semantic_search

        rem = "\n**Reminiscence (Relevant History & Notes):**\n"
        found = False
        seen_contents = set()

        # TURBO: Parallel RAG Execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Launch searches in parallel
            f_vault = executor.submit(search_vault, user_input, top_k=2)
            f_semantic = executor.submit(semantic_search, user_input, top_k=2)
            f_literal = executor.submit(get_literal_matches, user_input, top_k=2)

            # 1. Vault Search Results
            try:
                vault_results = f_vault.result()
                for r in vault_results:
                    content = f"[{r['path']}] {r['text']}"
                    if content not in seen_contents:
                        rem += f"- [Vault] {content}\n"
                        seen_contents.add(content)
                        found = True
            except:
                pass

            # 2. Semantic Search (Session Memory)
            try:
                semantic_results = f_semantic.result()
                for r in semantic_results:
                    content = r["content"]
                    if content not in seen_contents:
                        rem += f"- [Intuition] {content}\n"
                        seen_contents.add(content)
                        found = True
            except:
                pass

            # 3. Literal Search (Keyword)
            try:
                literal_results = f_literal.result()
                for r in literal_results:
                    content = r["content"]
                    if content not in seen_contents:
                        rem += f"- [Recall] {content}\n"
                        seen_contents.add(content)
                        found = True
            except:
                pass

        return rem if found else ""

    def autosave(self, role, content):
        # 1. Save to Local Session Dir
        with open(self.save_path, "a", encoding="utf-8") as f:
            if f.tell() == 0:
                f.write(
                    f"# Mimi Session - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                )
            f.write(f"**{role}** ({datetime.now().strftime('%H:%M')}):\n{content}\n\n")

        # 2. Save to Obsidian Vault
        try:
            with open(self.vault_save_path, "a", encoding="utf-8") as f:
                if f.tell() == 0:
                    f.write(
                        f"# Mimi Session - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    )
                f.write(
                    f"**{role}** ({datetime.now().strftime('%H:%M')}):\n{content}\n\n"
                )
        except Exception:
            pass  # Fail silently for vault sync if path invalid

        # Trigger background re-index to catch new session context
        from mimi_lib.memory.vault_indexer import trigger_background_index

        trigger_background_index()


if __name__ == "__main__":
    app = MimiApp()
    app.run()
