#!/usr/bin/env python3
import os
import sys
import json
import time
import uuid
import argparse
import requests
import shutil
import textwrap
import tty
import termios
import re
import base64
from datetime import datetime
from typing import List, Dict, Any, Union
from duckduckgo_search import DDGS

# --- Configuration ---
JAN_DATA_DIR = "/home/kuumin/.var/app/ai.jan.Jan/data/Jan/data"
THREADS_DIR = os.path.join(JAN_DATA_DIR, "threads")
ASSISTANT_FILE = os.path.join(JAN_DATA_DIR, "assistants/s4sxg/assistant.json")
SESSION_DIR = "/home/kuumin/Documents/kuumin/Mimi/Sessions"
DEFAULT_THREAD_ID = "mimi-cli-session"
DEFAULT_CONFIG_FILE = "/home/kuumin/Script/deepseek_config.json"


# --- Colors ---
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    MAGENTA = "\033[95m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[90m"
    ITALIC = "\033[3m"
    HEADER_MIMI = f"{BOLD}{MAGENTA}"
    HEADER_USER = f"{BOLD}{GREEN}"
    SYSTEM = f"{CYAN}"


# --- Utils ---
_prompt_cache = {"mtime": 0, "content": ""}


def get_terminal_size():
    return shutil.get_terminal_size((80, 24))


def strip_ansi(s: str) -> str:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", s)


def load_config(config_path: str) -> Dict[str, Any]:
    if not os.path.exists(config_path):
        print(f"{Colors.RED}Error: Config not found at {config_path}{Colors.RESET}")
        sys.exit(1)
    with open(config_path, "r") as f:
        return json.load(f)


def load_system_prompt() -> str:
    global _prompt_cache
    if not os.path.exists(ASSISTANT_FILE):
        return "You are Mimi, a helpful AI assistant."
    try:
        mtime = os.path.getmtime(ASSISTANT_FILE)
        if mtime > _prompt_cache["mtime"]:
            with open(ASSISTANT_FILE, "r") as f:
                data = json.load(f)
                _prompt_cache["content"] = data.get("instructions", "")
                _prompt_cache["mtime"] = mtime
        return _prompt_cache["content"]
    except:
        return _prompt_cache["content"] or "You are Mimi."


def print_formatted(role: str, text: str, compact: bool = False):
    width = min(get_terminal_size().columns - 20, 80)
    indent_size = int((get_terminal_size().columns - width) / 2)
    indent = " " * indent_size
    if compact:
        print(f"{indent}{Colors.BOLD}{role}:{Colors.RESET} {text}")
    else:
        color = Colors.MAGENTA if role == "Mimi" else Colors.GREEN
        print(f"\n{indent}{color}╭── {role}{Colors.RESET}")
        wrapper = textwrap.TextWrapper(
            width=width,
            initial_indent=f"{indent}{color}│ {Colors.RESET}",
            subsequent_indent=f"{indent}{color}│ {Colors.RESET}",
        )
        for line in text.splitlines():
            if not line.strip():
                print(f"{indent}{color}│{Colors.RESET}")
                continue
            print(wrapper.fill(line))
        print(
            f"{indent}{color}╰──────────────────────────────────────────{Colors.RESET}"
        )


def ensure_thread_dir(thread_id: str) -> str:
    path = os.path.join(THREADS_DIR, thread_id)
    os.makedirs(path, exist_ok=True)
    msg_file = os.path.join(path, "messages.jsonl")
    if not os.path.exists(msg_file):
        open(msg_file, "a").close()
    return msg_file


def log_to_jan_format(msg_file: str, role: str, content: Any, model_id: str = "s4sxg"):
    log_content = str(content) if not isinstance(content, list) else "[Multimodal Data]"
    msg_data = {
        "id": str(uuid.uuid4()).replace("-", "").upper()[:26],
        "created_at": int(time.time() * 1000),
        "completed_at": int(time.time() * 1000) if role == "assistant" else 0,
        "role": role,
        "content": [
            {"type": "text", "text": {"value": log_content, "annotations": []}}
        ],
        "metadata": {"assistant": {"id": model_id, "name": "Mimi", "avatar": "🎂"}}
        if role == "assistant"
        else {},
    }
    try:
        with open(msg_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg_data) + "\n")
    except:
        pass


def autosave_turn(filepath: str, role: str, content: Any):
    if not filepath:
        return
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    mode = "a" if os.path.exists(filepath) else "w"
    save_content = (
        str(content) if not isinstance(content, list) else "[Multimodal Input]"
    )
    with open(filepath, mode, encoding="utf-8") as f:
        if mode == "w":
            f.write(f"# Mimi Session - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**{role}** ({datetime.now().strftime('%H:%M')}):\n{save_content}\n\n")


def load_session_from_file(filename: str) -> Union[List[Dict[str, Any]], None]:
    filepath = os.path.join(SESSION_DIR, filename)
    if not os.path.exists(filepath):
        return None
    history: List[Dict[str, Any]] = [
        {"role": "system", "content": load_system_prompt()}
    ]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        curr_role, curr_text = None, []
        for line in lines:
            if line.startswith("**") and "** (" in line:
                if curr_role and curr_text:
                    history.append(
                        {"role": curr_role, "content": "\n".join(curr_text).strip()}
                    )
                header = line.split("** (")[0].replace("**", "").strip()
                curr_role = "assistant" if header == "Mimi" else "user"
                curr_text = []
            elif not line.startswith("# "):
                curr_text.append(line)
        if curr_role and curr_text:
            history.append({"role": curr_role, "content": "\n".join(curr_text).strip()})
        return history
    except:
        return None


# --- Search Tool ---
def web_search(query: str, flash: bool = True) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3 if flash else 8))
            if not results:
                return "No results found."
            formatted = []
            for i, r in enumerate(results):
                formatted.append(
                    f"[NODE::{i + 1}] {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}"
                )
            return "\n\n".join(formatted)
    except Exception as e:
        return f"Search Error: {e}"


# --- Vision Tool ---
def encode_image(image_path: str) -> Union[str, None]:
    try:
        path = os.path.expanduser(image_path)
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except:
        return None


def detect_paths(text: str) -> List[str]:
    return re.findall(r"(?:/[^/\s\n]+)+|~/[^/\s\n]+", text)


def is_image(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


# --- UI Components ---
class StreamPrinter:
    def __init__(self, width: int, indent: str, line_color: str = Colors.MAGENTA):
        self.width, self.indent, self.line_color = width, indent, line_color
        self.current_line_len = 0
        self.word_buffer = ""
        self.is_start = True
        self.in_thought = False
        self.in_reasoning_block = False
        self.glyphs = ["▰▱▱▱▱▱", "▰▰▱▱▱▱", "▰▰▰▱▱▱", "▰▰▰▰▱▱", "▰▰▰▰▰▱", "▰▰▰▰▰▰"]
        self.glyph_idx = 0

    def process_reasoning(self, text: str, status: str = "Thinking..."):
        if not self.in_reasoning_block:
            self.in_reasoning_block = True
            glyph = self.glyphs[self.glyph_idx % len(self.glyphs)]
            print(
                f"{self.indent}{self.line_color}│{Colors.RESET} {Colors.DIM}{glyph} {status}{Colors.RESET}"
            )
            print(
                f"{self.indent}{self.line_color}│{Colors.RESET} {Colors.DIM}",
                end="",
                flush=True,
            )
            self.current_line_len = 0
            self.glyph_idx += 1

        for char in text:
            if char == "\n":
                self.flush_word()
                print(
                    f"\n{self.indent}{self.line_color}│{Colors.RESET} {Colors.DIM}",
                    end="",
                    flush=True,
                )
                self.current_line_len = 0
            else:
                self.word_buffer += char
                if char == " ":
                    self.flush_word()

    def process(self, text: str):
        if self.in_reasoning_block:
            self.flush_word()
            print(f"{Colors.RESET}\n{self.indent}{self.line_color}│{Colors.RESET} ")
            self.in_reasoning_block = False
            self.current_line_len = 0
        if self.is_start:
            print(f"{self.indent}{self.line_color}│{Colors.RESET} ", end="", flush=True)
            self.is_start = False
        for char in text:
            if char == "\n":
                self.flush_word()
                style = f"{Colors.DIM}{Colors.ITALIC}" if self.in_thought else ""
                print(
                    f"\n{self.indent}{self.line_color}│{Colors.RESET} {style}",
                    end="",
                    flush=True,
                )
                self.current_line_len = 0
                continue
            if char == "*":
                self.flush_word()
                if not self.in_thought:
                    self.in_thought = True
                    sys.stdout.write(f"{Colors.DIM}{Colors.ITALIC}*")
                else:
                    sys.stdout.write(f"*{Colors.RESET}")
                    self.in_thought = False
                self.current_line_len += 1
                continue
            self.word_buffer += char
            if char == " ":
                self.flush_word()

    def flush_word(self):
        if not self.word_buffer:
            return
        if self.current_line_len + len(self.word_buffer) > self.width - 2:
            style = (
                f"{Colors.DIM}{Colors.ITALIC}"
                if (self.in_thought or self.in_reasoning_block)
                else ""
            )
            print(
                f"\n{self.indent}{self.line_color}│{Colors.RESET} {style}",
                end="",
                flush=True,
            )
            word = self.word_buffer.lstrip()
            print(word, end="", flush=True)
            self.current_line_len = len(word)
        else:
            print(self.word_buffer, end="", flush=True)
            self.current_line_len += len(self.word_buffer)
        self.word_buffer = ""

    def finish(self):
        self.flush_word()
        print(
            f"{Colors.RESET}\n{self.indent}{self.line_color}╰──────────────────────────────────────────{Colors.RESET}"
        )


class InputHandler:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)

    def get_key(self):
        try:
            tty.setraw(self.fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def wrapped_input(
        self, prompt: str, indent: str, width: int, padding: int = 0
    ) -> str:
        buffer, cursor_pos, prev_lines = [], 0, 0
        stripped_prompt = strip_ansi(prompt)
        p_len = len(stripped_prompt)

        # Lift UI
        print("\n" * padding, end="")
        sys.stdout.write(f"\033[{padding}A")
        print(prompt, end="", flush=True)

        while True:
            key = self.get_key()
            if key == "\x03":
                raise KeyboardInterrupt
            elif key == "\x04":
                if not buffer:
                    raise EOFError
                break
            elif key in ("\r", "\n"):
                if prev_lines > 0:
                    sys.stdout.write(f"\033[{prev_lines}A")
                sys.stdout.write("\r\033[J")
                print(prompt + "".join(buffer))
                break
            elif key == "\x7f":
                if cursor_pos > 0:
                    buffer.pop(cursor_pos - 1)
                    cursor_pos -= 1
            elif key == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[D" and cursor_pos > 0:
                    cursor_pos -= 1
                elif seq == "[C" and cursor_pos < len(buffer):
                    cursor_pos += 1
                continue
            elif ord(key) >= 32:
                buffer.insert(cursor_pos, key)
                cursor_pos += 1

            if prev_lines > 0:
                sys.stdout.write(f"\033[{prev_lines}A")
            sys.stdout.write("\r\033[J" + prompt)
            cl, lines, cur_cl, cur_col = p_len, 0, 0, p_len
            for i, char in enumerate(buffer):
                if i == cursor_pos:
                    cur_cl, cur_col = lines, cl
                sys.stdout.write(char)
                cl += 1
                if cl >= width:
                    sys.stdout.write(f"\n{indent}")
                    cl, lines = 0, lines + 1
            if cursor_pos == len(buffer):
                cur_cl, cur_col = lines, cl
            up = lines - cur_cl
            if up > 0:
                sys.stdout.write(f"\033[{up}A")
            sys.stdout.write(f"\r\033[{cur_col}C")
            prev_lines = lines
            sys.stdout.flush()
        return "".join(buffer)


# --- System & API ---
class SystemMonitor:
    def __init__(self):
        self.last_cpu = None
        self.history = {"bat": [], "cpu": [], "mem": []}

    def get_trend(self, key, val):
        if not self.history[key]:
            self.history[key].append(val)
            return ""
        prev = self.history[key][-1]
        self.history[key].append(val)
        if len(self.history[key]) > 5:
            self.history[key].pop(0)
        return "↑" if val > prev else ("↓" if val < prev else "")

    def get_stats(self):
        try:
            with open("/sys/class/power_supply/BAT0/capacity") as f:
                b_val = int(f.read().strip())
            with open("/sys/class/power_supply/BAT0/status") as f:
                b_stat = f.read().strip()
            with open("/proc/stat") as f:
                line = f.readline()
            parts = [int(x) for x in line.split()[1:]]
            idle, total = parts[3] + parts[4], sum(parts)
            c_val = 0
            if self.last_cpu:
                pi, pt = self.last_cpu
                if total > pt:
                    c_val = int(100 * (1 - (idle - pi) / (total - pt)))
            self.last_cpu = (idle, total)
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            m_total, m_avail = int(lines[0].split()[1]), int(lines[2].split()[1])
            m_val = int(100 * (m_total - m_avail) / m_total)
            b_icon = "⚡" if b_stat == "Charging" else "🔋"
            return (
                f"{b_icon}{b_val}%{self.get_trend('bat', b_val)}",
                f"CPU:{c_val}%{self.get_trend('cpu', c_val)}",
                f"MEM:{m_val}%{self.get_trend('mem', m_val)}",
            )
        except:
            return ("Bat:?", "CPU:?", "MEM:?")

    def get_status_string(self):
        b, c, m = self.get_stats()
        return f"{Colors.DIM}┌──[{Colors.RESET} {b} {Colors.DIM}]──[{Colors.RESET} {c} {Colors.DIM}]──[{Colors.RESET} {m} {Colors.DIM}]──┐{Colors.RESET}"


def chat_api_call(
    messages: List[Dict[str, Any]],
    config: Dict[str, Any],
    model: str,
    mimo_thinking: bool = True,
    search_enabled: bool = False,
):
    if model == "mimo" or "/" in model:
        key, url = config.get("openrouter_api_key"), config.get("openrouter_base_url")
        m_name = "xiaomi/mimo-v2-flash:free" if model == "mimo" else model
        headers = {
            "Authorization": f"Bearer {key}",
            "X-Title": "Mimi CLI",
            "HTTP-Referer": "https://github.com/kuumin/mimi-cli",
        }
    elif model.startswith("grok"):
        key, url = config.get("xai_api_key"), config.get("xai_base_url")
        m_name = "grok-4-1-fast" if model == "grok" else model
        headers = {"Authorization": f"Bearer {key}"}
    else:
        key, url = config.get("api_key"), config.get("base_url")
        m_name = model
        headers = {"Authorization": f"Bearer {key}"}

    clean_msgs = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            clean_msgs.append({"role": role, "content": content})
        else:
            clean_msgs.append({"role": role, "content": str(content)})

    payload = {"model": m_name, "messages": clean_msgs, "stream": True}
    if search_enabled and "reasoner" not in m_name:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query",
                            },
                            "flash": {
                                "type": "boolean",
                                "description": "If true, returns top 3 results fast. If false, returns 8 results.",
                            },
                        },
                        "required": ["query"],
                    },
                },
            }
        ]
    if "reasoner" in m_name:
        pass
    elif "mimo-v2-flash" in m_name and mimo_thinking:
        payload["include_reasoning"] = True
    elif "grok" not in m_name:
        payload["temperature"] = 1.2
    try:
        res = requests.post(
            str(url).rstrip("/") + "/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=120,
        )
        res.raise_for_status()
        return res
    except Exception as e:
        print(f"\n{Colors.RED}API Error: {e}{Colors.RESET}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--model")
    args = parser.parse_args()
    config = load_config(args.config)
    cur_model = str(args.model or config.get("default_model", "deepseek-reasoner"))
    mimo_thinking, search_active = config.get("mimo_thinking_enabled", True), False
    history: List[Dict[str, Any]] = []
    history.append({"role": "system", "content": load_system_prompt()})
    session_file = f"Session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"
    save_path = os.path.join(SESSION_DIR, session_file)
    monitor, input_h = SystemMonitor(), InputHandler()
    os.system("clear")
    print(
        f"\n{Colors.CYAN}Mimi Cyber-TTY v4.0 (Optical & Search Uplink Enabled){Colors.RESET}"
    )
    print(f"{Colors.DIM}Model: {cur_model} | File: {session_file}{Colors.RESET}\n")

    while True:
        try:
            width = min(get_terminal_size().columns - 20, 80)
            indent_size = int((get_terminal_size().columns - width) / 2)
            indent = " " * indent_size
            print(f"{indent}{monitor.get_status_string()}")
            prompt = f"{indent}{Colors.DIM}└─> {Colors.RESET}{Colors.HEADER_USER}KUUMIN_ {Colors.RESET}"
            user_input = input_h.wrapped_input(prompt, indent, width, padding=5)
            if not user_input.strip():
                continue
            if user_input.lower() in ("exit", "quit"):
                break

            if user_input.startswith("/"):
                cmd = user_input.split()
                if cmd[0] == "/model":
                    if len(cmd) > 1:
                        cur_model = cmd[1]
                        print(f"{indent}Model -> {cur_model}\n")
                    else:
                        print(
                            f"{indent}Models: deepseek-reasoner, grok, mimo, vision\n"
                        )
                elif cmd[0] == "/search":
                    search_active = "on" in user_input
                    print(
                        f"{indent}Search Uplink: {'ENABLED' if search_active else 'DISABLED'}\n"
                    )
                elif cmd[0] == "/thinking":
                    mimo_thinking = "on" in user_input
                    print(f"{indent}Mimo Thinking: {mimo_thinking}\n")
                elif cmd[0] == "/history":
                    for m in history:
                        if m["role"] != "system":
                            print_formatted(
                                "Mimi" if m["role"] == "assistant" else "Kuumin",
                                str(m.get("content", "")),
                                compact=True,
                            )
                elif cmd[0] == "/session":
                    if len(cmd) > 1 and cmd[1] == "list":
                        files = sorted(
                            [f for f in os.listdir(SESSION_DIR) if f.endswith(".md")],
                            reverse=True,
                        )
                        for i, f in enumerate(files[:10]):
                            print(f"{indent}[{i + 1}] {f}")
                    elif len(cmd) > 1 and cmd[1] == "load":
                        files = sorted(
                            [f for f in os.listdir(SESSION_DIR) if f.endswith(".md")],
                            reverse=True,
                        )
                        idx = (
                            int(cmd[2]) - 1 if len(cmd) > 2 and cmd[2].isdigit() else -1
                        )
                        target = (
                            files[idx]
                            if 0 <= idx < len(files)
                            else (cmd[2] if len(cmd) > 2 else None)
                        )
                        if target:
                            if not target.endswith(".md"):
                                target += ".md"
                            new_h = load_session_from_file(target)
                            if new_h:
                                history = new_h
                                save_path = os.path.join(SESSION_DIR, target)
                                session_file = target
                                print(f"{indent}Loaded {target}\n")
                continue

            # Optical Scan
            paths = detect_paths(user_input)
            images = [
                p
                for p in paths
                if is_image(p) and os.path.exists(os.path.expanduser(p))
            ]
            c_payload: List[Dict[str, Any]] = [{"type": "text", "text": user_input}]
            if images:
                print(
                    f"{indent}{Colors.YELLOW}[ SCANNING OPTICAL BUFFER... ]{Colors.RESET}"
                )
                for img in images:
                    b64 = encode_image(img)
                    if b64:
                        c_payload.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            }
                        )
                if "reasoner" in cur_model or "grok" in cur_model:
                    cur_model = "nvidia/llama-3.1-nemotron-51b-instruct"

            history[0]["content"] = load_system_prompt()
            history.append(
                {"role": "user", "content": c_payload if images else user_input}
            )
            autosave_turn(save_path, "Kuumin", user_input)
            log_to_jan_format(ensure_thread_dir(DEFAULT_THREAD_ID), "user", user_input)

            while True:
                print(f"\n{indent}{Colors.MAGENTA}╭── MIMI ❖{Colors.RESET}")
                printer = StreamPrinter(width, indent)
                response = chat_api_call(
                    history, config, cur_model, mimo_thinking, search_active
                )
                full_res, tool_calls = "", []
                if response:
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
                            reason = delta.get("reasoning_content") or delta.get(
                                "reasoning"
                            )
                            if reason:
                                printer.process_reasoning(reason)
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    while len(tool_calls) <= tc["index"]:
                                        tool_calls.append(
                                            {
                                                "id": "",
                                                "function": {
                                                    "name": "",
                                                    "arguments": "",
                                                },
                                            }
                                        )
                                    if "id" in tc:
                                        tool_calls[tc["index"]]["id"] += tc["id"]
                                    if "function" in tc:
                                        if "name" in tc.function:
                                            tool_calls[tc["index"]]["function"][
                                                "name"
                                            ] += tc.function.name
                                        if "arguments" in tc.function:
                                            tool_calls[tc["index"]]["function"][
                                                "arguments"
                                            ] += tc.function.arguments
                            content = delta.get("content")
                            if content:
                                full_res += content
                                printer.process(content)
                        except:
                            pass
                    printer.finish()

                if tool_calls:
                    history.append(
                        {
                            "role": "assistant",
                            "content": full_res or None,
                            "tool_calls": tool_calls,
                        }
                    )
                    for tc in tool_calls:
                        if tc["function"]["name"] == "web_search":
                            args_d = json.loads(tc["function"]["arguments"])
                            q = args_d.get("query")
                            print(
                                f"{indent}{Colors.CYAN}[ ACQUIRING UPLINK: {q} ]{Colors.RESET}"
                            )
                            res = web_search(q, args_d.get("flash", True))
                            history.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "name": "web_search",
                                    "content": res,
                                }
                            )
                    continue
                else:
                    history.append({"role": "assistant", "content": full_res})
                    autosave_turn(save_path, "Mimi", full_res)
                    log_to_jan_format(
                        ensure_thread_dir(DEFAULT_THREAD_ID), "assistant", full_res
                    )
                    break
            # Visual lift after Mimi speaks
            print("\n" * 3)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")


if __name__ == "__main__":
    main()
