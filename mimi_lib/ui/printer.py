import sys
from mimi_lib.utils.text import Colors, visible_len


class StreamPrinter:
    def __init__(self, width: int, indent: str, role: str = "Mimi"):
        self.width, self.indent = width, indent
        self.current_line_len = 0
        self.word_buf = ""
        self.is_start = True
        self.is_reasoning = False
        self.role = role
        self.in_bold = False
        self.in_italic = False
        self.in_code = False
        self.pending_stars = 0
        self.speech_color = "\033[0m"

    def process(self, text: str, reasoning: bool = False):
        if reasoning and not self.is_reasoning:
            self.flush()
            self.is_reasoning = True
        elif not reasoning and self.is_reasoning:
            self.flush()
            print(Colors.RESET, end="", flush=True)
            self.is_reasoning = False
            print(f"\n{self.indent}    ", end="", flush=True)

        if self.is_start:
            color = Colors.MAGENTA if self.role == "Mimi" else Colors.GREEN
            tag = f"[THINK: {self.role}]" if reasoning else f"[{self.role}]"
            print(f"\n\n{self.indent}{color}{tag}{Colors.RESET}")
            print(f"{self.indent}    ", end="", flush=True)
            if reasoning:
                print(Colors.DIM, end="", flush=True)
            self.is_start = False

        main_color = Colors.DIM if self.is_reasoning else self.speech_color

        for char in text:
            if char == "`":
                self.flush()
                self.in_code = not self.in_code
                print(Colors.GREEN if self.in_code else main_color, end="", flush=True)
                continue
            if self.in_code:
                self.word_buf += char
                if char == " ":
                    self.flush()
                continue

            if char == "*":
                self.pending_stars += 1
                continue

            if self.pending_stars > 0:
                if self.pending_stars >= 2:
                    self.flush()
                    self.in_bold = not self.in_bold
                    print(
                        Colors.CYAN if self.in_bold else main_color, end="", flush=True
                    )
                    self.pending_stars -= 2
                if self.pending_stars == 1:
                    self.flush()
                    self.in_italic = not self.in_italic
                    print(
                        Colors.YELLOW if self.in_italic else main_color,
                        end="",
                        flush=True,
                    )
                    self.pending_stars = 0

            if char == "\n":
                self.flush()
                print(f"\n{self.indent}    ", end="", flush=True)
                # Re-apply active color
                c = (
                    Colors.DIM
                    if self.is_reasoning
                    else Colors.GREEN
                    if self.in_code
                    else Colors.CYAN
                    if self.in_bold
                    else Colors.YELLOW
                    if self.in_italic
                    else main_color
                )
                print(c, end="", flush=True)
                self.current_line_len = 0
            else:
                self.word_buf += char
                if char == " ":
                    self.flush()

    def flush(self):
        if not self.word_buf:
            return
        vlen = visible_len(self.word_buf)
        if self.current_line_len + vlen > self.width - 4:
            print(f"\n{self.indent}    ", end="", flush=True)
            self.current_line_len = 0
        print(self.word_buf, end="", flush=True)
        self.current_line_len += vlen
        self.word_buf = ""

    def finish(self):
        self.flush()
        print(Colors.RESET, end="\n")
