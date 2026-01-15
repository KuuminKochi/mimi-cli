# Mimi CLI - AI Model Developer Documentation

This document serves as a comprehensive guide for any AI models or developers working on the Mimi CLI codebase. It outlines the architecture, critical formatting logic, and safe areas for modification.

---

## 1. Core Architecture Overview

Mimi CLI is a TTY-optimized terminal chat interface designed for immersive roleplay. It features:
- **Stateful Streaming:** Live ANSI-colored output that handles split markdown tokens across network chunks.
- **Roleplay-Focused Coloring:** Speech is NORMAL (default), while Actions/Markdown are BRIGHT GREEN (`\033[92m`).
- **Cyber-TTY UI:** Large margins (35-40%), no borders, and high vertical breathing room.
- **Jan Integration:** Synchronizes session history with the Jan AI desktop app logs.

---

## 2. CRITICAL: DO NOT MODIFY (Formatting Core)

The following sections contain highly sensitive state-management and terminal-arithmetic logic. Modifying these without extreme care will result in broken colors, text cut-offs, or layout corruption.

### A. The `StreamPrinterV2` Class
**Location:** Approx. Line 960+
**Purpose:** Handles live streaming of AI responses.
- **Fragile Logic:** The `process()` method uses a character-by-character state machine to track `*bold*`, `_italic_`, and `` `code` ``. It must buffer asterisks (`pending_stars`) to distinguish between italic and bold tokens that might be split across network packets.
- **Constraint:** Never remove the `pending_stars` buffering or the transition logic between reasoning and normal output.
- **Indentation:** Uses a hardcoded 4-space indent (`{self.indent}    `).

### B. `get_layout()` & `visible_len()`
**Location:** Approx. Line 75-100
**Purpose:** Margin calculation and ANSI-aware string measurement.
- **Fragile Logic:** `visible_len()` uses regex to strip ANSI codes before measuring length. This is vital for the line-wrapping logic in `StreamPrinterV2.flush()`.
- **Margins:** TTY is set to 35% and GUI to 40% by default. Changes here affect the entire UI centering.

### C. `highlight_markdown_roleplay()`
**Location:** Approx. Line 203+
**Purpose:** Applies colors to static text (History/Sessions).
- **Fragile Logic:** It must stay perfectly synchronized with the `StreamPrinterV2` color scheme. Currently: Speech is `\033[0m`, Actions are `\033[92m`.

---

## 3. SAFE TO MODIFY (Extensions & Configuration)

### A. API Providers & Models
- **Location:** `chat_api_call()` and `main()`
- **Action:** You can add new `elif model.startswith("...")` blocks in `chat_api_call` to support new APIs.
- **Minimax Example:**
  1. Add `minimax_api_key` to `deepseek_config.json`.
  2. In `chat_api_call`, add:
     ```python
     elif model.startswith("minimax"):
         key = config.get("minimax_api_key")
         url = config.get("minimax_base_url")
         headers = {"Authorization": f"Bearer {key}"}
         # ... construct payload and request
     ```
- **Default Model:** Update `deepseek_config.json` to change the starting model.

### B. Command System
- **Location:** `InputHandler.COMMANDS` and `main()` loop command handlers.
- **Action:** Add new slash commands here. Ensure you follow the existing pattern:
  1. Add tuple to `COMMANDS`.
  2. Add `elif cmd[0] == "/yourcmd":` in the `main()` while loop.

### C. Color Definitions
- **Location:** `Colors` class.
- **Action:** You can change the hex/ANSI values for UI elements (Headers, Status Bar).
- **Warning:** If changing the main `GREEN` highlight, ensure you update the hardcoded `\033[92m` in both `StreamPrinterV2` and `highlight_markdown_roleplay`.

### D. Input Engine
- **Location:** `InputHandler.wrapped_input()`
- **Feature:** Live highlighting of user input. As you type, text inside `*asterisks*` will turn green immediately.
- **Fragile Logic:** Uses a `_redraw()` method that calculates back-steps via `visible_len()`. Modifying the prompt string (`> `) or indentation requires updating the back-step calculation.

---

## 4. Known Implementation Quirks

1. **Unreachable Code Warning:** Historically, `mimi_cli.py` had a duplicated unreachable loop at the end of `wrapped_input`. Developers should ensure only one clean input loop exists.
2. **Spacing Preservation:** `textwrap.TextWrapper` is configured with `replace_whitespace=False` to ensure that roleplay indentation and multiple spaces are not collapsed.
3. **Reasoning Blocks:** DeepSeek "Thinking" content is styled in `Colors.DIM` (gray) and the state machine handles the transition to normal speech automatically.

---

## 5. Development Checklist

- [ ] **Test Split Tokens:** Ensure `**bold**` still works if `*` and `*` arrive in different chunks.
- [ ] **Verify Margins:** Check that the 4-space indent remains consistent across all roles.
- [ ] **Sync History:** After modifying output styles, ensure `print_formatted()` still produces matching history.
- [ ] **Sync Copy:** Always update both `/home/kuumin/Script/mimi_cli.py` and the sync copy in `Projects/mimi-cli/`.

---
*Mimi CLI is a precise instrument. Buffering and State are the keys to its performance.*
