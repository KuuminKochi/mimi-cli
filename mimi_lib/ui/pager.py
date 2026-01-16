import sys
import tty
import termios
from typing import List, Dict, Any
from mimi_lib.utils.text import Colors, get_layout
from mimi_lib.ui.ansi import clear_screen, save_cursor, restore_cursor
from mimi_lib.ui.markdown import MarkdownRenderer


class Pager:
    def __init__(self, history: List[Dict[str, Any]], config: Dict[str, Any]):
        self.history = history
        self.config = config
        self.renderer = MarkdownRenderer()
        self.lines: List[str] = []
        self.search_mode = False
        self.search_query = ""
        self.scroll_offset = 0
        self.highlight_indices = []

    def prepare_content(self):
        width, indent, _, _ = get_layout(self.config)
        self.lines = []

        for m in self.history:
            role = m["role"]
            if role == "system":
                continue

            # Header
            if role == "user":
                header = f"{Colors.GREEN}[Kuumin]{Colors.RESET}"
            elif role == "assistant":
                header = f"{Colors.MAGENTA}[Mimi]{Colors.RESET}"
            elif role == "tool":
                header = f"{Colors.CYAN}[TOOL: {m.get('name', '???')}]{Colors.RESET}"
            else:
                header = f"{Colors.DIM}[{role.upper()}]{Colors.RESET}"

            self.lines.append(f"{indent}{header}")

            # Content
            content = m.get("content") or ""

            # Handle tool calls without content
            if not content and role == "assistant" and "tool_calls" in m:
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
                rendered_lines = self.renderer.render(content, width - 4, indent + "  ")
                self.lines.extend(rendered_lines)

            self.lines.append("")  # Spacer

        # Scroll to bottom initially
        _, _, _, rows = get_layout(self.config)
        self.scroll_offset = max(0, len(self.lines) - (rows - 4))

    def run(self):
        self.prepare_content()
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setraw(sys.stdin.fileno())
            while True:
                self._draw()

                ch = sys.stdin.read(1)

                if self.search_mode:
                    if ch == "\r":  # Enter
                        self.search_mode = False
                        self._find_next()
                    elif ch == "\x7f":  # Backspace
                        self.search_query = self.search_query[:-1]
                    elif ch == "\x1b":  # Escape
                        self.search_mode = False
                        self.search_query = ""
                    else:
                        self.search_query += ch
                else:
                    if ch == "q":
                        break
                    elif ch == "j":  # Down
                        self._scroll(1)
                    elif ch == "k":  # Up
                        self._scroll(-1)
                    elif ch == "d":  # Half page down
                        self._scroll(10)
                    elif ch == "u":  # Half page up
                        self._scroll(-10)
                    elif ch == "G":  # Bottom
                        self.scroll_offset = max(
                            0, len(self.lines) - self._get_view_height()
                        )
                    elif ch == "g":  # Top
                        self.scroll_offset = 0
                    elif ch == "/":  # Search
                        self.search_mode = True
                        self.search_query = ""
                    elif ch == "n":  # Next match
                        self._find_next()
                    elif ch == "N":  # Prev match
                        self._find_prev()
                    elif ch == "\x1b":  # Arrow keys
                        seq = sys.stdin.read(2)
                        if seq == "[A":
                            self._scroll(-1)
                        elif seq == "[B":
                            self._scroll(1)

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            clear_screen()

    def _draw(self):
        width, indent, _, rows = get_layout(self.config)
        view_height = rows - 4  # Header + Footer

        # Clear screen hack for raw mode
        sys.stdout.write("\033[2J\033[H")

        # Header
        title = f" History ({len(self.history)} msgs) "
        border = "─" * ((width - len(title)) // 2)
        print(
            f"{indent}{Colors.CYAN}┌{border}{Colors.BOLD}{title}{Colors.RESET}{Colors.CYAN}{border}┐{Colors.RESET}\r"
        )

        # Content
        end_idx = min(self.scroll_offset + view_height, len(self.lines))
        for i in range(self.scroll_offset, end_idx):
            line = self.lines[i]
            # Simple highlight if search matches
            if self.search_query and self.search_query.lower() in line.lower():
                line = line.replace(
                    self.search_query,
                    f"{Colors.RED}{Colors.BOLD}{self.search_query}{Colors.RESET}",
                )
            print(f"{line}\r")

        # Fill empty
        for _ in range(view_height - (end_idx - self.scroll_offset)):
            print(f"\r")

        # Footer / Status Bar
        if self.search_mode:
            status = f"SEARCH: {self.search_query}█"
        else:
            pct = int(
                (self.scroll_offset / max(1, len(self.lines) - view_height)) * 100
            )
            status = f"[j/k] Scroll | [u/d] Page | [/] Search | [q] Exit | {pct}%"

        print(f"{indent}{Colors.CYAN}└{'─' * (width - 2)}┘{Colors.RESET}\r")
        print(f"{indent}{Colors.DIM}{status}{Colors.RESET}\r", end="")
        sys.stdout.flush()

    def _scroll(self, amount):
        max_offset = max(0, len(self.lines) - self._get_view_height())
        self.scroll_offset = max(0, min(max_offset, self.scroll_offset + amount))

    def _get_view_height(self):
        _, _, _, rows = get_layout(self.config)
        return rows - 4

    def _find_next(self):
        if not self.search_query:
            return
        start = self.scroll_offset + 1
        for i in range(start, len(self.lines)):
            if self.search_query.lower() in self.lines[i].lower():
                self.scroll_offset = i
                return
        # Wrap around
        for i in range(0, start):
            if self.search_query.lower() in self.lines[i].lower():
                self.scroll_offset = i
                return

    def _find_prev(self):
        if not self.search_query:
            return
        start = self.scroll_offset - 1
        for i in range(start, -1, -1):
            if self.search_query.lower() in self.lines[i].lower():
                self.scroll_offset = i
                return
