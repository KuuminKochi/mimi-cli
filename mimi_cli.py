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
from typing import List, Dict, Any, Union, Optional
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


# --- Utils ---
_prompt_cache = {"mtime": 0, "content": ""}


def get_layout():
    cols, rows = shutil.get_terminal_size((80, 24))
    margin_size = int(cols * 0.15)
    width = max(cols - (margin_size * 2), 40)
    indent = " " * margin_size
    return width, indent, cols, rows


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


def ensure_thread_dir(thread_id: str) -> str:
    path = os.path.join(THREADS_DIR, thread_id)
    os.makedirs(path, exist_ok=True)
    msg_file = os.path.join(path, "messages.jsonl")
    if not os.path.exists(msg_file):
        open(msg_file, "a").close()
    return msg_file


def log_to_jan_format(msg_file: str, role: str, content: Any, model_id: str = "s4sxg"):
    log_content = (
        str(content) if not isinstance(content, list) else "[Multimodal Input]"
    )
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


def load_session_from_file(filename: str) -> Optional[List[Dict[str, Any]]]:
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


# --- UI Formatting ---
def print_formatted(role: str, text: str, compact: bool = False):
    width, indent, _, _ = get_layout()
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


def run_pager(history: List[Dict[str, Any]]):
    content = []
    for m in history:
        if m["role"] == "system":
            continue
        role = "Mimi" if m["role"] == "assistant" else "Kuumin"
        content.append(f"--- {role} ---")
        content.append(str(m["content"]))
        content.append("")

    lines = "\n".join(content).splitlines()
    _, _, _, rows = get_layout()
    page_size = rows - 4
    ptr = 0
    while True:
        os.system("clear")
        print(
            f"{Colors.CYAN}--- Mimi Pager (UP/DOWN to scroll, Q to exit) ---{Colors.RESET}"
        )
        for i in range(ptr, min(ptr + page_size, len(lines))):
            print(lines[i])
        print(
            f"\n{Colors.DIM}Line {ptr + 1}/{len(lines)} | Press Q to return to chat...{Colors.RESET}"
        )

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            key = sys.stdin.read(1)
            if key == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A" and ptr > 0:
                    ptr -= 1
                if seq == "[B" and ptr < len(lines) - page_size:
                    ptr += 1
            elif key.lower() == "q":
                break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# --- Search & Vision ---
def web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if not results:
                return "No results found."
            formatted = [
                f"[NODE::{i + 1}] {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}"
                for i, r in enumerate(results)
            ]
            return "\n\n".join(formatted)
    except Exception as e:
        return f"Search Error: {e}"


def encode_image(path: str) -> Optional[str]:
    try:
        with open(os.path.expanduser(path), "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except:
        return None


def detect_paths(text: str) -> List[str]:
    return re.findall(r"(?:/[^/\s\n]+)+|~/[^/\s\n]+", text)


# --- Input Engine v2 ---
class InputHandler:
    COMMANDS = [
        "/model",
        "/search",
        "/thinking",
        "/history",
        "/rename",
        "/session list",
        "/session load",
        "/clear",
        "/help",
        "/exit",
        "/pager",
    ]

    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        self.history: List[str] = []
        self.hist_ptr = -1

    def get_key(self):
        try:
            tty.setraw(self.fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def wrapped_input(self, prompt_header: str, indent: str, width: int) -> str:
        buffer: List[str] = []
        cursor_pos = 0
        p_len = len(strip_ansi(prompt_header))
        print(prompt_header, end="", flush=True)

        prev_lines = 0
        while True:
            key = self.get_key()
            ghost = ""

            if key == "\x03":
                raise KeyboardInterrupt
            elif key == "\x04":
                raise EOFError
            elif key in ("\r", "\n"):
                if prev_lines > 0:
                    sys.stdout.write(f"\033[{prev_lines}A")
                sys.stdout.write("\r\033[J" + prompt_header + "".join(buffer) + "\n")
                res = "".join(buffer)
                if res.strip():
                    self.history.append(res)
                self.hist_ptr = -1
                return res
            elif key == "\t":
                current_str = "".join(buffer)
                for cmd in self.COMMANDS:
                    if current_str.startswith("/") and cmd.startswith(current_str):
                        buffer = list(cmd)
                        cursor_pos = len(buffer)
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
                elif seq == "[A":  # Up
                    if self.history and self.hist_ptr < len(self.history) - 1:
                        self.hist_ptr += 1
                        buffer = list(self.history[-(self.hist_ptr + 1)])
                        cursor_pos = len(buffer)
                elif seq == "[B":  # Down
                    if self.hist_ptr > 0:
                        self.hist_ptr -= 1
                        buffer = list(self.history[-(self.hist_ptr + 1)])
                        cursor_pos = len(buffer)
                    else:
                        self.hist_ptr = -1
                        buffer = []
                        cursor_pos = 0
                continue
            elif ord(key) >= 32:
                buffer.insert(cursor_pos, key)
                cursor_pos += 1

            # Autocomplete Ghosting
            current_str = "".join(buffer)
            if current_str.startswith("/") and len(current_str) > 1:
                for cmd in self.COMMANDS:
                    if cmd.startswith(current_str):
                        ghost = cmd[len(current_str) :]
                        break

            # Redraw
            if prev_lines > 0:
                sys.stdout.write(f"\033[{prev_lines}A")
            sys.stdout.write("\r\033[J" + prompt_header)

            cl, lines, cur_l, cur_c = p_len, 0, 0, p_len
            for i, char in enumerate(buffer):
                if i == cursor_pos:
                    cur_l, cur_c = lines, cl
                sys.stdout.write(char)
                cl += 1
                if cl >= width:
                    sys.stdout.write(f"\n{indent}")
                    cl, lines = 0, lines + 1

            if ghost:
                sys.stdout.write(f"{Colors.DIM}{ghost}{Colors.RESET}")

            if cursor_pos == len(buffer):
                cur_l, cur_c = lines, cl
            up = lines - cur_l
            if up > 0:
                sys.stdout.write(f"\033[{up}A")
            sys.stdout.write(f"\r\033[{cur_c}C")
            prev_lines = lines
            sys.stdout.flush()


# --- System Stats ---
class SystemMonitor:
    def __init__(self):
        self.last_cpu = None

    def get_stats(self):
        try:
            with open("/sys/class/power_supply/BAT0/capacity") as f:
                b = int(f.read())
            with open("/sys/class/power_supply/BAT0/status") as f:
                s = f.read().strip()
            with open("/proc/stat") as f:
                line = f.readline()
            parts = [int(x) for x in line.split()[1:]]
            idle, total = parts[3] + parts[4], sum(parts)
            c = 0
            if self.last_cpu:
                pi, pt = self.last_cpu
                if total > pt:
                    c = int(100 * (1 - (idle - pi) / (total - pt)))
            self.last_cpu = (idle, total)
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            mt, ma = int(lines[0].split()[1]), int(lines[2].split()[1])
            m = int(100 * (mt - ma) / mt)
            return f"{'⚡' if s == 'Charging' else '🔋'}{b}%", f"CPU:{c}%", f"MEM:{m}%"
        except:
            return "Bat:?", "CPU:?", "MEM:?"

    def get_status(self):
        b, c, m = self.get_stats()
        return f"{Colors.DIM}┌──[{Colors.RESET} {b} {Colors.DIM}]──[{Colors.RESET} {c} {Colors.DIM}]──[{Colors.RESET} {m} {Colors.DIM}]──┐{Colors.RESET}"


# --- API & Engine ---
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

    clean = []
    for m in messages:
        if isinstance(m.get("content"), list):
            clean.append({"role": m["role"], "content": m["content"]})
        else:
            clean.append({"role": m["role"], "content": str(m["content"])})

    payload = {"model": m_name, "messages": clean, "stream": True}
    if search_enabled and "reasoner" not in m_name:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
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


class StreamPrinterV2:
    def __init__(self, width: int, indent: str):
        self.width, self.indent = width, indent
        self.current_line_len = 0
        self.word_buf = ""
        self.is_start = True
        self.is_reasoning = False

    def process(self, text: str, reasoning: bool = False):
        if reasoning and not self.is_reasoning:
            self.is_reasoning = True
            print(
                f"{self.indent}{Colors.MAGENTA}│{Colors.RESET} {Colors.DIM}Thinking...{Colors.RESET}"
            )
            print(
                f"{self.indent}{Colors.MAGENTA}│{Colors.RESET} {Colors.DIM}",
                end="",
                flush=True,
            )
            self.current_line_len = 0
        elif not reasoning and self.is_reasoning:
            self.flush()
            print(f"{Colors.RESET}\n{self.indent}{Colors.MAGENTA}│{Colors.RESET} ")
            self.is_reasoning, self.is_start, self.current_line_len = False, True, 0

        if self.is_start:
            prefix = f"{self.indent}{Colors.MAGENTA}│{Colors.RESET} "
            if reasoning:
                prefix += Colors.DIM
            print(prefix, end="", flush=True)
            self.is_start = False

        for char in text:
            if char == "\n":
                self.flush()
                prefix = f"\n{self.indent}{Colors.MAGENTA}│{Colors.RESET} "
                if reasoning:
                    prefix += Colors.DIM
                print(prefix, end="", flush=True)
                self.current_line_len = 0
                continue
            self.word_buf += char
            if char == " ":
                self.flush()

    def flush(self):
        if not self.word_buf:
            return
        if self.current_line_len + len(self.word_buf) > self.width - 2:
            prefix = f"\n{self.indent}{Colors.MAGENTA}│{Colors.RESET} "
            if self.is_reasoning:
                prefix += Colors.DIM
            print(prefix, end="", flush=True)
            word = self.word_buf.lstrip()
            print(word, end="", flush=True)
            self.current_line_len = len(word)
        else:
            print(self.word_buf, end="", flush=True)
            self.current_line_len += len(self.word_buf)
        self.word_buf = ""

    def finish(self):
        self.flush()
        print(
            f"{Colors.RESET}\n{self.indent}{Colors.MAGENTA}╰──────────────────────────────────────────{Colors.RESET}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--model")
    args = parser.parse_args()
    config = load_config(args.config)
    cur_model = str(args.model or config.get("default_model", "deepseek-reasoner"))
    mimo_thinking, search_active, pager_active = (
        config.get("mimo_thinking_enabled", True),
        False,
        False,
    )

    # Startup Cleanup
    if os.path.exists(SESSION_DIR):
        for f in os.listdir(SESSION_DIR):
            p = os.path.join(SESSION_DIR, f)
            if os.path.isfile(p) and os.path.getsize(p) < 200:
                try:
                    with open(p) as f_obj:
                        if "**Kuumin**" not in f_obj.read():
                            os.remove(p)
                except:
                    pass

    history: List[Dict[str, Any]] = [
        {"role": "system", "content": load_system_prompt()}
    ]
    session_file = f"Session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"
    save_path = os.path.join(SESSION_DIR, session_file)
    monitor, input_h = SystemMonitor(), InputHandler()
    os.system("clear")
    print(f"\n{Colors.CYAN}Mimi Cyber-TTY Zenith v5.0{Colors.RESET}")
    print(f"{Colors.DIM}Model: {cur_model} | File: {session_file}{Colors.RESET}\n")

    while True:
        try:
            width, indent, _, _ = get_layout()
            print(f"{indent}{monitor.get_status()}")
            print(f"{indent}{Colors.HEADER_USER}KUUMIN ⚡{Colors.RESET}")
            user_input = input_h.wrapped_input(f"{indent}> ", indent, width)

            if not user_input.strip():
                continue
            if user_input.lower() in ("exit", "quit", "/exit"):
                break

            if user_input.startswith("/"):
                cmd = user_input.split()
                if cmd[0] == "/model":
                    if len(cmd) > 1:
                        cur_model = cmd[1]
                        print(f"{indent}Model -> {cur_model}\n")
                    else:
                        print(
                            f"{indent}Models: deepseek-reasoner, deepseek-chat, grok, mimo\n"
                        )
                elif cmd[0] == "/search":
                    search_active = "on" in user_input
                    print(
                        f"{indent}Search Uplink: {'ON' if search_active else 'OFF'}\n"
                    )
                elif cmd[0] == "/thinking":
                    mimo_thinking = "on" in user_input
                    print(f"{indent}Mimo Thinking: {mimo_thinking}\n")
                elif cmd[0] == "/pager":
                    pager_active = "on" in user_input
                    print(f"{indent}Interactive Pager: {pager_active}\n")
                elif cmd[0] == "/clear":
                    os.system("clear")
                elif cmd[0] == "/session":
                    if len(cmd) > 1 and cmd[1] == "list":
                        files = sorted(
                            [f for f in os.listdir(SESSION_DIR) if f.endswith(".md")],
                            reverse=True,
                        )
                        for i, f in enumerate(files[:15]):
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
                                if pager_active:
                                    run_pager(history)
                                else:
                                    os.system("clear")
                                    for m in history:
                                        if m["role"] != "system":
                                            print_formatted(
                                                "Mimi"
                                                if m["role"] == "assistant"
                                                else "Kuumin",
                                                str(m.get("content", "")),
                                            )
                elif cmd[0] == "/history":
                    if pager_active:
                        run_pager(history)
                    else:
                        for m in history:
                            if m["role"] != "system":
                                print_formatted(
                                    "Mimi" if m["role"] == "assistant" else "Kuumin",
                                    str(m.get("content", "")),
                                )
                continue

            # Process Images
            paths = detect_paths(user_input)
            images = [
                p
                for p in paths
                if os.path.exists(os.path.expanduser(p))
                and p.lower().endswith((".png", ".jpg", ".jpeg"))
            ]
            p_load: List[Dict[str, Any]] = [{"type": "text", "text": user_input}]
            if images:
                print(
                    f"{indent}{Colors.YELLOW}[ SCANNING OPTICAL BUFFER... ]{Colors.RESET}"
                )
                for img in images:
                    b64 = encode_image(img)
                    if b64:
                        p_load.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            }
                        )
                if "reasoner" in cur_model or "grok" in cur_model:
                    cur_model = "nvidia/llama-3.1-nemotron-51b-instruct"

            history[0]["content"] = load_system_prompt()
            history.append(
                {"role": "user", "content": p_load if images else user_input}
            )
            autosave_turn(save_path, "Kuumin", user_input)
            log_to_jan_format(ensure_thread_dir(DEFAULT_THREAD_ID), "user", user_input)

            while True:
                print(f"\n{indent}{Colors.MAGENTA}╭── MIMI ❖{Colors.RESET}")
                printer = StreamPrinterV2(width, indent)
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
                                printer.process(reason, reasoning=True)
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
                            res = web_search(q)
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
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")


if __name__ == "__main__":
    main()
