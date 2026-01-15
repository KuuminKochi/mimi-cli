import re
import sys


def visible_len(s: str) -> int:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return len(ansi_escape.sub("", s))


def wrap_text_ansi_orig(s: str, max_width: int) -> list[str]:
    if not s:
        return [""]
    parts = re.split(r"(\s+|/)", s)
    refined = []
    for p in parts:
        refined.extend(p.split(" "))
    words = [w for w in refined if w]
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if visible_len(test_line) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            while visible_len(word) > max_width:
                lines.append(word[:max_width])
                word = word[max_width:]
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines if lines else [""]


def wrap_text_ansi_new(s: str, max_width: int) -> list[str]:
    if not s:
        return [""]

    parts = s.split(" ")
    lines = []
    # Initialize with the first word (empty string if s starts with space)
    current_line = parts[0]

    # Handle first word potentially being too long
    if visible_len(current_line) > max_width:
        while visible_len(current_line) > max_width:
            lines.append(current_line[:max_width])
            current_line = current_line[max_width:]

    for word in parts[1:]:
        # We always add a space before the word because we split by space
        # But we need to check if adding " " + word fits

        # Check space + word length
        val_to_add = " " + word
        if visible_len(current_line + val_to_add) <= max_width:
            current_line += val_to_add
        else:
            lines.append(current_line)
            current_line = word
            # Handle splitting long word
            while visible_len(current_line) > max_width:
                lines.append(current_line[:max_width])
                current_line = current_line[max_width:]

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


print("--- Orig ---")
print(wrap_text_ansi_orig("  Indented  text  with  spaces", 20))
print("--- New ---")
print(wrap_text_ansi_new("  Indented  text  with  spaces", 20))

print("\n--- Orig Long ---")
print(wrap_text_ansi_orig("A" * 25, 10))
print("--- New Long ---")
print(wrap_text_ansi_new("A" * 25, 10))

print("\n--- New URL split check ---")
# The new simple split doesn't split on "/" which was a feature of the orig.
# But keeping whitespace is more important?
# Maybe we can pre-split URLs?
print(wrap_text_ansi_new("Check https://example.com/very/long/url", 20))
