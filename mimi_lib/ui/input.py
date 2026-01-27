import sys
import tty
import termios
import select
from mimi_lib.utils.text import visible_len


class VimInput:
    def __init__(self):
        self.history_buffer = []
        self.history_index = -1
        self.last_rows = 1

    def get_input(self, prompt, indent, width, history_messages=None):
        if history_messages:
            self.history_buffer = history_messages[::-1]

        line = ""
        cursor_pos = 0
        self.history_index = -1
        self.last_rows = 1

        sys.stdout.write(prompt)
        sys.stdout.flush()

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch == "\r":
                    print()
                    return line
                elif ch in ("\x7f", "\b"):
                    if cursor_pos > 0:
                        line = line[: cursor_pos - 1] + line[cursor_pos:]
                        cursor_pos -= 1
                        self._redraw(prompt, line, cursor_pos, indent, width)
                elif ch == "\x10":  # Ctrl+P
                    if self.history_index < len(self.history_buffer) - 1:
                        self.history_index += 1
                        line = self.history_buffer[self.history_index]
                        cursor_pos = len(line)
                        self._redraw(prompt, line, cursor_pos, indent, width)
                elif ch == "\x0e":  # Ctrl+N
                    if self.history_index >= 0:
                        self.history_index -= 1
                        line = (
                            self.history_buffer[self.history_index]
                            if self.history_index >= 0
                            else ""
                        )
                        cursor_pos = len(line)
                        self._redraw(prompt, line, cursor_pos, indent, width)
                elif ch == "\x1b":
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        seq = sys.stdin.read(2)
                        if seq == "[D" and cursor_pos > 0:
                            cursor_pos -= 1
                            self._redraw(prompt, line, cursor_pos, indent, width)
                        elif seq == "[C" and cursor_pos < len(line):
                            cursor_pos += 1
                            self._redraw(prompt, line, cursor_pos, indent, width)
                elif 32 <= ord(ch) <= 126:
                    line = line[:cursor_pos] + ch + line[cursor_pos:]
                    cursor_pos += 1
                    self._redraw(prompt, line, cursor_pos, indent, width)
                elif ch == "\x03":
                    return "/exit"
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def _redraw(self, prompt, line, cursor_pos, indent, width):
        if self.last_rows > 1:
            sys.stdout.write(f"\033[{self.last_rows - 1}A")
        sys.stdout.write("\r")

        prefix_len = visible_len("> ")
        text_width = width - prefix_len
        wrapped = [
            line[i : i + text_width] for i in range(0, max(1, len(line)), text_width)
        ]
        num_lines = len(wrapped)

        for i in range(num_lines):
            sys.stdout.write("\033[2K\r")
            if i == 0:
                sys.stdout.write(prompt + wrapped[i])
            else:
                sys.stdout.write(f"{indent}{' ' * prefix_len}{wrapped[i]}")
            if i < num_lines - 1:
                if i < self.last_rows - 1:
                    sys.stdout.write("\033[1B\r")
                else:
                    sys.stdout.write("\n")

        if self.last_rows > num_lines:
            for _ in range(self.last_rows - num_lines):
                sys.stdout.write("\033[1B\033[2K")
            sys.stdout.write(f"\033[{self.last_rows - num_lines}A\r")

        # Position cursor
        crow, ccol = cursor_pos // text_width, cursor_pos % text_width
        up = num_lines - 1 - crow
        if up > 0:
            sys.stdout.write(f"\033[{up}A")
        off = visible_len(prompt) if crow == 0 else visible_len(indent) + prefix_len
        sys.stdout.write(f"\r\033[{off + ccol + 1}G")
        self.last_rows = num_lines
        sys.stdout.flush()
