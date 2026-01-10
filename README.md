# Mimi Cyber-TTY ❖

A high-performance, battery-optimized Cyberpunk TTY interface for Mimi.

## Features
- **Multi-Provider Routing**: Seamlessly switch between DeepSeek, xAI (Grok), and OpenRouter (Mimo).
- **Cyberpunk HUD**: Integrated real-time Battery, CPU, and Memory monitoring.
- **Thinking Blocks**: Support for native reasoning tokens (DeepSeek R1) and OpenRouter reasoning.
- **Zero-Poll Optimization**: System stats only refresh on interaction to conserve battery.
- **Auto-Session Management**: Dynamic file naming and automatic cleanup of empty chats.

## Installation

1. Clone the repo:
   ```bash
   git clone https://github.com/kuumin/mimi-cli
   cd mimi-cli
   ```

2. Setup your keys:
   Copy `config.json.example` to `deepseek_config.json` and fill in your API keys.

3. Run:
   ```bash
   ./mimi
   ```

## Commands
- `/model [name]`: Switch models (deepseek-reasoner, grok, mimo, etc.)
- `/thinking [on|off]`: Toggle reasoning for Mimo.
- `/history`: View formatted session history.
- `exit`: Leave the session.

---
*Created for Kuumin.*
