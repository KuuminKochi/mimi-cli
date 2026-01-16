import re
from typing import List
from mimi_lib.utils.text import Colors, visible_len, visible_wrap


class MarkdownRenderer:
    """
    A simple ANSI-based Markdown renderer for the CLI.
    Handles headers, bold, italic, code blocks, and basic lists.
    """

    def render(self, text: str, width: int, indent: str = "") -> List[str]:
        lines = []
        in_code_block = False
        code_lang = ""

        # Split into lines to process block elements first
        raw_lines = text.splitlines()

        for line in raw_lines:
            # Code Blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                if in_code_block:
                    code_lang = line.strip().replace("```", "")
                    lines.append(
                        f"{indent}{Colors.DIM}╭── [{code_lang if code_lang else 'CODE'}] {'─' * (width - 10 - len(code_lang))}╮{Colors.RESET}"
                    )
                else:
                    lines.append(
                        f"{indent}{Colors.DIM}╰{'─' * (width - 2)}╯{Colors.RESET}"
                    )
                continue

            if in_code_block:
                # Simple syntax highlighting heuristic (very basic)
                colored_line = self._highlight_code(line, code_lang)
                # Code blocks might need wrapping if they are too long,
                # but usually code is better kept as is or truncated.
                # For a pager, wrapping is safer to avoid horizontal scroll issues.
                wrapped = visible_wrap(colored_line, width - 4)
                for w in wrapped:
                    lines.append(f"{indent}  {w}")
                continue

            # Headers
            if line.startswith("# "):
                content = line[2:]
                lines.append("")
                lines.append(
                    f"{indent}{Colors.CYAN}{Colors.BOLD}{content.upper()}{Colors.RESET}"
                )
                lines.append(f"{indent}{Colors.CYAN}{'=' * len(content)}{Colors.RESET}")
            elif line.startswith("## "):
                content = line[3:]
                lines.append("")
                lines.append(
                    f"{indent}{Colors.GREEN}{Colors.BOLD}{content}{Colors.RESET}"
                )
                lines.append(
                    f"{indent}{Colors.GREEN}{'-' * len(content)}{Colors.RESET}"
                )
            elif line.startswith("### "):
                content = line[4:]
                lines.append(
                    f"{indent}{Colors.YELLOW}{Colors.BOLD}{content}{Colors.RESET}"
                )

            # List Items
            elif line.strip().startswith("- "):
                content = self._format_inline(line.strip()[2:])
                wrapped = visible_wrap(content, width - 4)
                for i, w in enumerate(wrapped):
                    prefix = "• " if i == 0 else "  "
                    lines.append(f"{indent}{prefix}{w}")

            # Blockquotes
            elif line.startswith("> "):
                content = self._format_inline(line[2:])
                wrapped = visible_wrap(content, width - 6)
                for w in wrapped:
                    lines.append(
                        f"{indent}{Colors.DIM}│ {Colors.ITALIC}{w}{Colors.RESET}"
                    )

            # Normal Text
            else:
                if not line.strip():
                    lines.append("")
                    continue

                content = self._format_inline(line)
                wrapped = visible_wrap(content, width)
                for w in wrapped:
                    lines.append(f"{indent}{w}")

        return lines

    def _format_inline(self, text: str) -> str:
        # Bold **text**
        text = re.sub(
            r"\*\*(.*?)\*\*", f"{Colors.BOLD}{Colors.CYAN}\\1{Colors.RESET}", text
        )
        # Italic *text*
        text = re.sub(
            r"\*(.*?)\*", f"{Colors.ITALIC}{Colors.YELLOW}\\1{Colors.RESET}", text
        )
        # Inline code `text`
        text = re.sub(r"`(.*?)`", f"{Colors.GREEN}\\1{Colors.RESET}", text)
        # Links [text](url) - Just show text for CLI
        text = re.sub(r"\[(.*?)\]\(.*?\)", f"{Colors.BLUE}\\1{Colors.RESET}", text)
        return text

    def _highlight_code(self, line: str, lang: str) -> str:
        # Extremely basic highlighting
        if lang in ["python", "py"]:
            line = re.sub(
                r"\b(def|class|import|from|return|if|else|elif|for|while|try|except)\b",
                f"{Colors.MAGENTA}\\1{Colors.RESET}",
                line,
            )
            line = re.sub(r"(#.*)", f"{Colors.DIM}\\1{Colors.RESET}", line)
            line = re.sub(r'(".*?")', f"{Colors.GREEN}\\1{Colors.RESET}", line)
        elif lang in ["json"]:
            line = re.sub(r'(".*?"):', f"{Colors.CYAN}\\1{Colors.RESET}:", line)
        return line
