import sys
from mimi_lib.utils.text import Colors


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def save_cursor():
    sys.stdout.write("\033[s")
    sys.stdout.flush()


def restore_cursor():
    sys.stdout.write("\033[u")
    sys.stdout.flush()


def erase_current_line():
    sys.stdout.write("\033[2K\r")
    sys.stdout.flush()
