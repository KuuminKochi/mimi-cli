import re
import shutil
import unicodedata
from typing import List, Optional, Dict, Any


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


def strip_ansi(s: str) -> str:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", s)


def visible_len(s: str) -> int:
    clean_s = strip_ansi(s)
    width = 0
    for char in clean_s:
        if unicodedata.east_asian_width(char) in ("W", "F"):
            width += 2
        else:
            width += 1
    return width


def format_latex_math(text: str) -> str:
    subs = {
        r"\\alpha": "α",
        r"\\beta": "β",
        r"\\gamma": "γ",
        r"\\delta": "δ",
        r"\\epsilon": "ε",
        r"\\theta": "θ",
        r"\\lambda": "λ",
        r"\\mu": "μ",
        r"\\pi": "π",
        r"\\sigma": "σ",
        r"\\tau": "τ",
        r"\\phi": "φ",
        r"\\omega": "ω",
        r"\\Delta": "Δ",
        r"\\Lambda": "Λ",
        r"\\Sigma": "Σ",
        r"\\Omega": "Ω",
        r"\\infty": "∞",
        r"\\approx": "≈",
        r"\\neq": "≠",
        r"\\leq": "≤",
        r"\\geq": "≥",
        r"\\pm": "±",
        r"\\times": "×",
        r"\\cdot": "·",
        r"\\div": "÷",
        r"\\rightarrow": "→",
        r"\\leftarrow": "←",
        r"\\Rightarrow": "⇒",
        r"\\in": "∈",
        r"\\forall": "∀",
        r"\\exists": "∃",
        r"\\sum": "∑",
        r"\\prod": "∏",
        r"\\int": "∫",
        r"\\partial": "∂",
        r"\\nabla": "∇",
        r"\\sqrt": "√",
        r"\\frac{1}{2}": "½",
    }
    keys = sorted(subs.keys(), key=len, reverse=True)
    for k in keys:
        single_bs = k.replace(r"\\", "\\")
        text = text.replace(single_bs, subs[k])
        text = text.replace(k, subs[k])
    text = text.replace("^2", "²").replace("^3", "³")
    text = re.sub(r"\^(\d)", lambda m: "⁰¹²³⁴⁵⁶⁷⁸⁹"[int(m.group(1))], text)
    text = re.sub(r"_(\d)", lambda m: "₀₁₂₃₄₅₆₇₈₉"[int(m.group(1))], text)
    return text


def visible_wrap(text: str, width: int) -> List[str]:
    """Wraps text taking into account visible character length (ignoring ANSI)."""
    lines = []
    for line in text.splitlines():
        if not line:
            lines.append("")
            continue

        current_line = []
        current_len = 0
        # Split by spaces but preserve them
        words = re.split(r"(\s+)", line)

        for word in words:
            word_vlen = visible_len(word)
            if current_len + word_vlen > width:
                if current_line:
                    lines.append("".join(current_line).rstrip())
                    current_line = []
                    current_len = 0

                # If a single word is wider than the width, we must force break it
                if word_vlen > width:
                    temp_word = ""
                    temp_len = 0
                    for char in word:
                        char_vlen = visible_len(char)
                        if temp_len + char_vlen > width:
                            lines.append(temp_word)
                            temp_word = ""
                            temp_len = 0
                        temp_word += char
                        temp_len += char_vlen
                    if temp_word:
                        current_line.append(temp_word)
                        current_len = temp_len
                else:
                    if word.strip():
                        current_line.append(word)
                        current_len = word_vlen
            else:
                current_line.append(word)
                current_len += word_vlen

        if current_line:
            lines.append("".join(current_line).rstrip())

    return lines


def get_layout(config: Optional[Dict[str, Any]] = None):
    cols, rows = shutil.get_terminal_size((80, 24))
    # Using defaults from improved config
    percent = 5
    if config:
        import os

        is_tty = os.getenv("TERM", "").startswith("linux")
        percent = (
            config.get("margin_percent_tty", 2)
            if is_tty
            else config.get("margin_percent", 5)
        )

    margin_size = int(cols * (percent / 100))
    width = max(cols - (margin_size * 2), 40)
    indent = " " * margin_size
    return width, indent, cols, rows
