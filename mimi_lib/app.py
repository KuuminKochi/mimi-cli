import os
import re
import sys
import json
import threading
import concurrent.futures
import textwrap
from datetime import datetime

from typing import List, Dict, Any, Optional

from mimi_lib.config import SESSION_DIR, get_config
from mimi_lib.ui.ansi import clear_screen
from mimi_lib.ui.input import VimInput
from mimi_lib.ui.printer import StreamPrinter
from mimi_lib.utils.text import Colors, get_layout, visible_len, visible_wrap
from mimi_lib.memory.brain import load_system_prompt, save_memory
from mimi_lib.memory.embeddings import semantic_search
from mimi_lib.api.provider import call_api
from mimi_lib.utils.system import get_sys_info

# Import tools to trigger registration
import mimi_lib.tools.file_tools
import mimi_lib.tools.web_tools
import mimi_lib.tools.memory_tools
import mimi_lib.tools.note_tools
import mimi_lib.tools.vision_tools
from mimi_lib.tools.registry import get_tool_definitions, execute_tool

from mimi_lib.ui.session import SessionSelector


class MimiApp:
    def __init__(self):
        self.config = get_config()
        self.history: List[Dict[str, Any]] = []
        self.cur_model = "deepseek-reasoner"
        self.search_active = False
        self.thinking_mode = False
        self.autorename = True
        self.session_file = f"Session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"
        self.save_path = SESSION_DIR / self.session_file
        self.input_handler = VimInput()
        self.print_lock = threading.Lock()

    def run(self):
        clear_screen()
        print(f"\n{Colors.CYAN}Mimi Cyber-TTY Zenith v6.0 (Modular){Colors.RESET}")
        print(
            f"{Colors.DIM}Model: {self.cur_model} | File: {self.session_file}{Colors.RESET}\n"
        )

        self.history = [{"role": "system", "content": load_system_prompt()}]

        while True:
            width, indent, _, _ = get_layout(self.config)
            print(f"\n{indent}{self.get_status_bar()}")
            print(f"{indent}{Colors.GREEN}[USER: Kuumin]{Colors.RESET}")
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
                    break

            # RAG / Reminiscence
            reminiscence = self.get_reminiscence(user_input)
            self.history[0]["content"] = load_system_prompt() + "\n" + reminiscence

            self.history.append({"role": "user", "content": user_input})
            self.autosave("Kuumin", user_input)

            self.generate_response(width, indent)

    def get_status_bar(self):
        now = datetime.now().strftime("%H:%M")
        s_text = "[W:ON]" if self.search_active else "[W:OFF]"
        t_text = "[T:ON]" if self.thinking_mode else "[T:OFF]"
        sys = get_sys_info()
        return (
            f"{Colors.CYAN}[{now}]{Colors.RESET} {s_text} {t_text} | "
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
            print(f"{indent}  /search         - Toggle Web Search")
            print(f"{indent}  /thinking       - Toggle Thinking Mode")
            print(f"{indent}  /new            - Start fresh session")
            print(f"{indent}  /regen          - Regenerate last response")
            print(f"{indent}  /model [name]   - Switch AI model")
            print(f"{indent}  /autorename     - Toggle auto-renaming")
            print(f"{indent}  /vault_index    - Sync Obsidian vault knowledge")
            print(f"{indent}  /clear          - Clear screen")
            print(f"{indent}  /exit           - Quit")
        elif cmd[0] == "/autorename":
            if len(cmd) > 1:
                self.autorename = cmd[1].lower() == "on"
            else:
                self.autorename = not self.autorename
            print(f"{indent}Auto-rename: {'ON' if self.autorename else 'OFF'}")
        elif cmd[0] == "/vault_index":
            from mimi_lib.memory.vault_indexer import index_vault

            print(f"{indent}Syncing vault knowledge... (This runs in background)")
            threading.Thread(target=index_vault, daemon=True).start()
        elif cmd[0].startswith("/session"):
            selector = SessionSelector(SESSION_DIR)
            selected = selector.select_session()
            if selected:
                new_h = self.load_session_from_file(selected)
                if new_h:
                    self.history = new_h
                    self.session_file = selected
                    self.save_path = SESSION_DIR / selected
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
        elif cmd[0] == "/model":
            if len(cmd) > 1:
                self.cur_model = cmd[1]
                print(f"{indent}Switched to: {self.cur_model}")
        elif cmd[0] == "/new":
            self.session_file = (
                f"Session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"
            )
            self.save_path = SESSION_DIR / self.session_file
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
        # Implementation of the pager for history viewing
        import tty, termios

        width, indent, _, rows = get_layout(self.config)
        all_lines = []
        for m in self.history:
            role = m["role"]
            if role == "system":
                continue

            # Label based on role
            if role == "user":
                label, color = "[Kuumin]", Colors.GREEN
            elif role == "assistant":
                label, color = "[Mimi]", Colors.MAGENTA
            elif role == "tool":
                label, color = f"[TOOL: {m.get('name', '???')}]", Colors.CYAN
            else:
                label, color = f"[{role.upper()}]", Colors.DIM

            all_lines.append(f"{indent}{color}{label}{Colors.RESET}")

            # Content handling (None/Empty checks)
            content = m.get("content") or ""
            if not content and role == "assistant" and "tool_calls" in m:
                # Assistant message with no text content (just tool calls)
                tool_calls = m.get("tool_calls", [])
                t_names = ", ".join(
                    [
                        tc["function"]["name"]
                        for tc in tool_calls
                        if isinstance(tc, dict)
                    ]
                )
                content = f"*Executing: {t_names}*"

            if content:
                for wrapped in visible_wrap(content, width - 4):
                    all_lines.append(f"{indent}  {wrapped}")
            all_lines.append("")

        ptr = max(0, len(all_lines) - (rows - 6))
        while True:
            clear_screen()
            border_top = f"┌──[ History ]{'─' * (width - 13)}┐"
            print(f"{indent}{Colors.CYAN}{border_top}{Colors.RESET}")

            # Display lines
            display_count = rows - 6
            for i in range(ptr, min(ptr + display_count, len(all_lines))):
                print(all_lines[i])

            # Fill empty lines if necessary
            for _ in range(max(0, display_count - (len(all_lines) - ptr))):
                print()

            border_bot = f"└{'─' * (width - 2)}┘"
            print(f"{indent}{Colors.CYAN}{border_bot}{Colors.RESET}")
            print(f"{indent}{Colors.DIM}[UP/DOWN] scroll | [Q] exit{Colors.RESET}")

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == "q":
                    break
                elif ch == "\x1b":
                    seq = sys.stdin.read(2)
                    if seq == "[A":
                        ptr = max(0, ptr - 1)
                    elif seq == "[B":
                        ptr = min(max(0, len(all_lines) - display_count), ptr + 1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

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

                if old_path.exists() and not new_path.exists():
                    os.rename(old_path, new_path)
                    self.session_file = new_name
                    self.save_path = new_path
                    with self.print_lock:
                        print(
                            f"\n{Colors.DIM}[ RENAMED session to: {new_name} ]{Colors.RESET}"
                        )
        except Exception as e:
            pass  # Fail silently for auto-rename

    def generate_response(self, width, indent):
        while True:
            printer = StreamPrinter(width, indent, "Mimi")
            tools = get_tool_definitions()

            response = call_api(
                self.history, model=self.cur_model, stream=True, tools=tools
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
                self.history.append(
                    {
                        "role": "assistant",
                        "content": full_res or None,
                        "tool_calls": tool_calls,
                        "reasoning_content": full_reasoning if full_reasoning else None,
                    }
                )

                # Execute tools in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {
                        executor.submit(self.run_tool, tc, indent): tc
                        for tc in tool_calls
                    }
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        self.history.append(result)
                continue  # Generate follow-up response after tool results
            else:
                self.history.append({"role": "assistant", "content": full_res})
                self.autosave("Mimi", full_res)
                self.check_autorename()
                break

    def run_tool(self, tc, indent):
        name = tc["function"]["name"]
        args = tc["function"]["arguments"]
        with self.print_lock:
            print(f"{indent}{Colors.CYAN}[ TOOL: {name} ]{Colors.RESET}")

        content = execute_tool(name, args)
        return {
            "role": "tool",
            "tool_call_id": tc["id"],
            "name": name,
            "content": str(content),
        }

    def get_reminiscence(self, user_input):
        from mimi_lib.memory.brain import get_literal_matches
        from mimi_lib.memory.vault_indexer import search_vault

        rem = "\n**Reminiscence (Relevant History & Notes):**\n"
        found = False
        seen_contents = set()

        # 1. Semantic Search (Vault Knowledge)
        try:
            vault_results = search_vault(user_input, top_k=2)
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
            semantic_results = semantic_search(user_input, top_k=2)
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
            literal_results = get_literal_matches(user_input, top_k=2)
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
        with open(self.save_path, "a", encoding="utf-8") as f:
            if f.tell() == 0:
                f.write(
                    f"# Mimi Session - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                )
            f.write(f"**{role}** ({datetime.now().strftime('%H:%M')}):\n{content}\n\n")


if __name__ == "__main__":
    app = MimiApp()
    app.run()
