# Chinese Breakdown Discord Bot — Design Spec

## Overview

A Discord bot that takes a Chinese phrase, sends it to the DeepSeek API for morphological/grammatical breakdown, and returns a beautifully formatted embed with pinyin and English translation.

## Tech Stack

- **Python** via `uv` (package management)
- **discord.py** (Discord bot framework)
- **openai** Python SDK (OpenAI-compatible client pointing at DeepSeek's endpoint)
- **python-dotenv** (.env config loading)
- **just** (task runner)

## Project Structure

```
koa/
├── src/
│   ├── __init__.py
│   ├── main.py          # Bot client, commands, cooldown, permission check
│   └── breakdown.py     # DeepSeek call, JSON parse -> typed cards
├── .env.example
├── .gitignore
├── pyproject.toml
└── justfile
```

## Components

### `src/breakdown.py` — Breakdown Logic

- `BreakdownCard` dataclass: `original`, `pinyin`, `english` (strings)
- `breakdown_phrase(phrase: str) -> list[BreakdownCard]`:
  - Calls DeepSeek API (`deepseek-chat` model at `https://api.deepseek.com`) via async OpenAI client
  - Sends the user's Chinese-teaching prompt verbatim
  - Receives JSON array, validates each element has the three keys
  - Returns typed list of `BreakdownCard`
  - Raises custom exception on API failure or malformed response

### `src/main.py` — Bot Orchestration

- `discord.ext.commands.Bot` with `!` prefix for text commands, configured with all intents needed
- Slash command registration via `discord.app_commands.CommandTree`

**Triggers:**
| Method | Syntax |
|--------|--------|
| Slash command | `/breakdown <phrase>` |
| Message prefix | `!breakdown <phrase>` |

**Cooldown:**
- `@commands.cooldown(1, 3, BucketType.user)` — 1 use per 3 seconds per user
- Applied to both slash and prefix commands

**Permission:**
- `ALLOWED_USER_IDS` env var — comma-separated Discord user IDs
- Checked before any API call
- Unauthorized users get a private/ephemeral "not authorized" message

**Response Format:**
- Discord Embed with:
  - Title: the full original Chinese input
  - Color: a warm/academic tone (e.g., orange or teal)
  - Fields: one per card, each showing:
    - Name: the `original` clause
    - Value: `pinyin` and `english` lines, with Discord's native `||spoiler||` tags (users click to reveal each chunk)
  - Footer: model name + small credit
- If the input has only one clause → single embed with one field. Multiple clauses → one embed with multiple fields.

### `pyproject.toml`

- `dependencies`: `discord.py`, `openai`, `python-dotenv`
- `requires-python >= 3.11`

### `justfile`

- `run`: runs `python src/main.py`
- `setup`: `uv sync`
- `lint`: `uv run ruff check src/`

## Configuration (.env)

```
DISCORD_TOKEN=...
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
ALLOWED_USER_IDS=123456789,987654321
```

## Error Handling

- Invalid phrase (empty/too long) → "Please provide a Chinese phrase (1-500 characters)."
- DeepSeek API error → "Sorry, the breakdown service is temporarily unavailable."
- Malformed JSON from model → "The model returned an unexpected response. Please try again."
- Rate limited (cooldown) → handled natively by discord.py, returns seconds remaining
- Unauthorized user → ephemeral "You are not authorized to use this bot."

## Skipped (YAGNI)

- Cogs (one command)
- Database (stateless)
- Logging framework (print is fine)
- DeepSeek-side rate limiting (3s user cooldown + per-user same command is sufficient)
- i18n / multi-language support
- Admin commands for dynamic allowlist editing (.env is fine)
