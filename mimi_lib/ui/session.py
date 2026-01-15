import os
import sys
import tty
import termios
from mimi_lib.utils.text import Colors, get_layout

class SessionSelector:
    def __init__(self, session_dir):
        self.session_dir = session_dir

    def select_session(self):
        files = []
        try:
            for f in os.listdir(self.session_dir):
                if f.endswith(".md"):
                    path = os.path.join(self.session_dir, f)
                    mtime = os.path.getmtime(path)
                    files.append((f, mtime))
            files.sort(key=lambda x: x[1], reverse=True)
            files = [f[0] for f in files]
        except:
            return None

        if not files:
            print(f"{Colors.RED}No sessions found.{Colors.RESET}")
            return None

        idx = 0
        window_size = 15

        while True:
            # Clear screen manually here or import clear_screen
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
            
            width, indent, _, rows = get_layout()

            print(f"{indent}{Colors.CYAN}┌──[ Select Session ]{'─' * (width - 20)}┐{Colors.RESET}")

            start_idx = max(0, idx - (window_size // 2))
            end_idx = min(len(files), start_idx + window_size)

            for i in range(start_idx, end_idx):
                f_name = files[i]
                is_selected = i == idx

                prefix = f"{Colors.GREEN}>>{Colors.RESET} " if is_selected else "   "
                name_color = Colors.BOLD if is_selected else Colors.DIM

                # Truncate filename if too long
                display_name = f_name[:width-10]
                line = f"{indent}│ {prefix}{name_color}{display_name:<40}{Colors.RESET}"
                print(line)

            print(f"{indent}{Colors.CYAN}└{'─' * (width - 2)}┘{Colors.RESET}")
            print(f"{indent}{Colors.DIM}[UP/DOWN] Select | [ENTER] Load | [Q] Cancel{Colors.RESET}")

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    seq = sys.stdin.read(2)
                    if seq == "[A":  # Up
                        idx = max(0, idx - 1)
                    elif seq == "[B":  # Down
                        idx = min(len(files) - 1, idx + 1)
                elif ch == "\r":  # Enter
                    return files[idx]
                elif ch.lower() == "q":
                    return None
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
