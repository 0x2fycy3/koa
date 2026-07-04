# Chinese Breakdown Discord Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Discord bot that breaks down Chinese phrases via DeepSeek API into pinyin and English cards, displayed as rich embeds with spoiler-tagged chunks.

**Architecture:** Two-layer Python package in `src/`: `breakdown.py` (API call + JSON parsing), `main.py` (Discord bot with slash and prefix commands). Config and logging centralized in `config.py` and `logger.py`.

**Tech Stack:** Python >=3.11, uv, discord.py>=2.3, openai>=1.0, python-dotenv>=1.0, just, ruff

## Global Constraints

- DeepSeek API via `openai` library pointing at `https://api.deepseek.com`
- 3-second cooldown per user for both slash and prefix commands
- User allowlist via `ALLOWED_USER_IDS` env var (comma-separated Discord user IDs)
- Output as Discord Embed with `||spoiler||` tags for pinyin/english chunks
- `.env` for all configuration; never commit secrets
- All source code in `src/` package
- `main.py` as entry point via `python -m src.main`

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `justfile`

**Interfaces:**
- Produces: Project metadata for `uv sync` and `just` task runner

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "koa"
version = "0.1.0"
description = "Chinese language breakdown Discord bot"
requires-python = ">=3.11"
dependencies = [
    "discord.py>=2.3",
    "openai>=1.0",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
    "ruff>=0.11",
]
```

- [ ] **Step 2: Create .env.example**

```
DISCORD_TOKEN=your_discord_bot_token_here
DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-chat
ALLOWED_USER_IDS=123456789012345678,987654321098765432
```

- [ ] **Step 3: Create justfile**

```makefile
run:
    uv run python -m src.main

setup:
    uv sync

lint:
    uv run ruff check src/
```

- [ ] **Step 4: Run setup and verify**

Run: `just setup`
Expected: uv syncs and creates virtualenv, no errors

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example justfile
git commit -m "feat: scaffold project with uv, just, and deps"
```

---

### Task 2: src/config.py — Centralized Settings

**Files:**
- Create: `src/__init__.py`
- Create: `src/config.py`

**Interfaces:**
- Produces: `DISCORD_TOKEN: str`, `DEEPSEEK_API_KEY: str`, `DEEPSEEK_MODEL: str`, `DEEPSEEK_BASE_URL: str`, `ALLOWED_USER_IDS: set[int]`, `COMMAND_PREFIX: str`, `COOLDOWN_SECONDS: float`

- [ ] **Step 1: Create src/__init__.py**

```python
```

- [ ] **Step 2: Create src/config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
COMMAND_PREFIX = os.environ.get("COMMAND_PREFIX", "!")
COOLDOWN_SECONDS = float(os.environ.get("COOLDOWN_SECONDS", "3.0"))

_raw_ids = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = {int(uid.strip()) for uid in _raw_ids.split(",") if uid.strip()}
```

- [ ] **Step 3: Verify config loads without env**

Run: `uv run python -c "import src.config; print('DISCORD_TOKEN present:', bool(src.config.DISCORD_TOKEN))"`
Expected: KeyError for DISCORD_TOKEN (no .env file yet — this is correct behavior)

- [ ] **Step 4: Commit**

```bash
git add src/__init__.py src/config.py
git commit -m "feat: add centralized config module"
```

---

### Task 3: src/logger.py — Structured Logging

**Files:**
- Create: `src/logger.py`

**Interfaces:**
- Produces: `setup_logging(level: int = logging.INFO) -> None`, `get_logger(name: str) -> logging.Logger`

- [ ] **Step 1: Create src/logger.py**

```python
import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

- [ ] **Step 2: Verify logger works**

Run: `uv run python -c "from src.logger import setup_logging, get_logger; setup_logging(); log = get_logger('test'); log.info('hello')"`
Expected: Prints timestamped log line with `[INFO] test: hello`

- [ ] **Step 3: Commit**

```bash
git add src/logger.py
git commit -m "feat: add structured logging module"
```

---

### Task 4: src/breakdown.py — DeepSeek API + JSON Parsing

**Files:**
- Create: `src/breakdown.py`

**Interfaces:**
- Produces: `BreakdownCard` dataclass (`original`, `pinyin`, `english`), `BreakdownError(Exception)`, `breakdown_phrase(phrase: str) -> list[BreakdownCard]`

- [ ] **Step 1: Create src/breakdown.py**

```python
import json
from dataclasses import dataclass

from openai import AsyncOpenAI

from . import config
from .logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a Chinese language teaching assistant.
Your ENTIRE response must be a valid JSON array. No text before or after the JSON.

Each element of the array is one card (one grammatical clause), with exactly three keys:
- "original": the Chinese clause as-is
- "pinyin": spoiler-tagged chunks: ||chunk||(N)
- "english": spoiler-tagged translation mapped to the same numbers. Extra grammatical words with no direct Chinese source get ||(\u2013)||

---

### SEGMENTATION RULE
Group words into MEANING CHUNKS \u2014 words that only make sense together stay in the same spoiler block. Only split when each part carries independent, learnable meaning on its own.

### MAPPING RULE
Numbers link **meaning**, not position. If English word order differs from Chinese, numbers jump in the English line \u2014 but always refer to the same Chinese chunk.

### LONG SENTENCE RULE
If the input contains more than one grammatical clause, split into multiple card objects \u2014 one per clause.

---

### EXAMPLE OUTPUT

Input: \u6982\u5ff5\uff1a20\u5c0f\u65f6\u6cd5\u5219 vs. \u5341\u5e74\u7684\u9003\u907f

[
  {
    "original": "\u6982\u5ff5\uff1a20\u5c0f\u65f6\u6cd5\u5219 vs. \u5341\u5e74\u7684\u9003\u907f",
    "pinyin": "||G\u00e0ini\u00e0n||(1) ||\uff1a||(\u2013) ||20 xi\u01ceosh\u00ed f\u01cez\u00e9||(2) ||vs.||(3) ||sh\u00ed ni\u00e1n de t\u00e1ob\u00ec||(4)",
    "english": "||Concept||(1) ||:||(\u2013) ||20-hour rule||(2) ||vs.||(3) ||ten years of avoidance||(4)"
  }
]

Input: \u53ea\u9700\u5927\u7ea620\u5c0f\u65f6\u4e13\u6ce8\u4e14\u523b\u610f\u7684\u7ec3\u4e60\uff0c\u5c31\u80fd\u4ece\u5bf9\u67d0\u4e2a\u9886\u57df\u4e00\u65e0\u6240\u77e5\u8fbe\u5230\u76f8\u5f53\u80dc\u4efb\u7684\u7a0b\u5ea6\u3002

[
  {
    "original": "\u53ea\u9700\u5927\u7ea620\u5c0f\u65f6\u4e13\u6ce8\u4e14\u523b\u610f\u7684\u7ec3\u4e60",
    "pinyin": "||Zh\u01d0 x\u016b||(1) ||d\u00e0yu\u0113 20 xi\u01ceosh\u00ed||(2) ||zhu\u0101nzh\u00f9 qi\u011b k\u00e8y\u00ec de li\u00e0nx\u00ed||(3)",
    "english": "||You only need||(1) ||about 20 hours||(2) ||of focused, deliberate practice||(3)"
  },
  {
    "original": "\u5c31\u80fd\u4ece\u5bf9\u67d0\u4e2a\u9886\u57df\u4e00\u65e0\u6240\u77e5",
    "pinyin": "||ji\u00f9 n\u00e9ng||(1) ||c\u00f3ng||(2) ||du\u00ec m\u01d2u g\u00e8 l\u01d0ngy\u00f9 y\u012bw\u00fa su\u01d2zh\u012b||(3)",
    "english": "||to go||(1) ||from||(2) ||knowing absolutely nothing about a field||(3)"
  },
  {
    "original": "\u8fbe\u5230\u76f8\u5f53\u80dc\u4efb\u7684\u7a0b\u5ea6",
    "pinyin": "||d\u00e1d\u00e0o||(1) ||xi\u0101ngd\u0101ng sh\u00e8ngr\u00e8n de ch\u00e9ngd\u00f9||(2)",
    "english": "||to reaching||(1) ||a reasonably competent level||(2)"
  }
]

---

Return ONLY the JSON array. No explanation, no markdown fences, no commentary."""


@dataclass
class BreakdownCard:
    original: str
    pinyin: str
    english: str


class BreakdownError(Exception):
    """Raised when the breakdown API call or parsing fails."""


async def breakdown_phrase(phrase: str) -> list[BreakdownCard]:
    client = AsyncOpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
    )
    try:
        response = await client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": phrase},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        # ponytail: strip markdown fences if the model ignores the prompt
        if content.startswith("```"):
            content = content.strip("`").strip()
            if content.lower().startswith("json"):
                content = content[4:].strip()

        cards_data = json.loads(content)

        if not isinstance(cards_data, list):
            raise BreakdownError("Expected a JSON array, got something else")

        cards = []
        for item in cards_data:
            if not all(k in item for k in ("original", "pinyin", "english")):
                raise BreakdownError(f"Card missing required keys: {item}")
            cards.append(BreakdownCard(
                original=item["original"],
                pinyin=item["pinyin"],
                english=item["english"],
            ))
        return cards

    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s, content: %s", e, content)
        raise BreakdownError("The model returned an unexpected response. Please try again.") from e
```

- [ ] **Step 2: Verify syntax and imports**

Run: `uv run python -c "from src.breakdown import BreakdownCard, BreakdownError, breakdown_phrase; print('Imports OK')"`
Expected: `Imports OK`

- [ ] **Step 3: Commit**

```bash
git add src/breakdown.py
git commit -m "feat: add phrase breakdown API module"
```

---

### Task 5: src/main.py — Discord Bot

**Files:**
- Create: `src/main.py`

**Interfaces:**
- Consumes: `config.*`, `logger.setup_logging`, `logger.get_logger`, `breakdown.breakdown_phrase`, `breakdown.BreakdownError`
- Produces: Runnable bot with `/breakdown` slash command and `!breakdown` prefix command

- [ ] **Step 1: Create src/main.py**

```python
import discord
from discord.ext import commands
from discord import app_commands

from . import config
from .logger import setup_logging, get_logger
from .breakdown import breakdown_phrase, BreakdownError, BreakdownCard

setup_logging()
logger = get_logger(__name__)


def _check_allowed(source) -> bool:
    if not config.ALLOWED_USER_IDS:
        return True
    user = source.author if hasattr(source, "author") else source.user
    return user.id in config.ALLOWED_USER_IDS


def _build_embed(phrase: str, cards: list[BreakdownCard]) -> discord.Embed:
    embed = discord.Embed(
        title=phrase,
        color=0xE67E22,
    )
    for card in cards:
        value = f"**Pinyin:** {card.pinyin}\n**English:** {card.english}"
        embed.add_field(name=card.original, value=value, inline=False)
    embed.set_footer(text=f"Model: {config.DEEPSEEK_MODEL}")
    return embed


class BreakdownBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=intents,
        )

    async def setup_hook(self) -> None:
        await self.tree.sync()


bot = BreakdownBot()


# --- Slash command ---

@bot.tree.command(
    name="breakdown",
    description="Break down a Chinese phrase with pinyin and English translation",
)
@app_commands.describe(phrase="The Chinese phrase to break down")
@app_commands.checks.cooldown(
    rate=1,
    per=config.COOLDOWN_SECONDS,
    key=lambda i: i.user.id,
)
async def slash_breakdown(interaction: discord.Interaction, phrase: str) -> None:
    if not _check_allowed(interaction):
        await interaction.response.send_message(
            "You are not authorized to use this bot.", ephemeral=True
        )
        return

    phrase = phrase.strip()
    if not phrase:
        await interaction.response.send_message(
            "Please provide a Chinese phrase.", ephemeral=True
        )
        return
    if len(phrase) > 500:
        await interaction.response.send_message(
            "Phrase is too long (max 500 characters).", ephemeral=True
        )
        return

    await interaction.response.defer()
    try:
        cards = await breakdown_phrase(phrase)
    except BreakdownError:
        await interaction.followup.send(
            "Sorry, the breakdown service is temporarily unavailable. Please try again."
        )
        return

    embed = _build_embed(phrase, cards)
    await interaction.followup.send(embed=embed)


@slash_breakdown.error
async def on_slash_breakdown_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"Please wait {error.retry_after:.1f}s before using this command again.",
            ephemeral=True,
        )


# --- Prefix command ---

@bot.command(name="breakdown")
@commands.cooldown(
    rate=1,
    per=config.COOLDOWN_SECONDS,
    type=commands.BucketType.user,
)
async def prefix_breakdown(ctx: commands.Context, *, phrase: str) -> None:
    if not _check_allowed(ctx):
        await ctx.send("You are not authorized to use this bot.", delete_after=5)
        return

    phrase = phrase.strip()
    if not phrase:
        await ctx.send("Please provide a Chinese phrase.", delete_after=5)
        return
    if len(phrase) > 500:
        await ctx.send(
            "Phrase is too long (max 500 characters).", delete_after=5
        )
        return

    async with ctx.typing():
        try:
            cards = await breakdown_phrase(phrase)
        except BreakdownError:
            await ctx.send(
                "Sorry, the breakdown service is temporarily unavailable. Please try again."
            )
            return

    embed = _build_embed(phrase, cards)
    await ctx.send(embed=embed)


@prefix_breakdown.error
async def on_prefix_breakdown_error(
    ctx: commands.Context, error: commands.CommandError
) -> None:
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(
            f"Please wait {error.retry_after:.1f}s before using this command again.",
            delete_after=5,
        )


# --- Entry point ---

if __name__ == "__main__":
    bot.run(config.DISCORD_TOKEN)
```

- [ ] **Step 2: Verify syntax and imports**

Run: `uv run python -c "from src.main import bot; print('Bot class loaded:', type(bot).__name__)"`
Expected: `Bot class loaded: BreakdownBot` (may show warning about no token — that's fine)

- [ ] **Step 3: Run lint**

Run: `just lint`
Expected: `All checks passed!` or no output

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat: add Discord bot with slash and prefix commands"
```

---

### Task 6: Final Verification

**Files:**
- None new

- [ ] **Step 1: Full lint check**

Run: `just lint`
Expected: zero errors, zero warnings

- [ ] **Step 2: Verify clean import chain**

Run: `uv run python -c "from src.main import bot, BreakdownBot, breakdown_phrase, config; print('All imports OK')"`
Expected: `All imports OK` (will fail on Discord token only if `bot.run()` is called — test doesn't run the bot)

- [ ] **Step 3: Create .env with real credentials and do manual smoke test**

```
DISCORD_TOKEN=<real_token>
DEEPSEEK_API_KEY=<real_key>
ALLOWED_USER_IDS=<your_discord_user_id>
```

Run: `just run`
Then in Discord:
- Type `!breakdown 你好世界` → verify embed with spoiler-tagged pinyin/english appears
- Type `/breakdown 我喜欢学中文` → verify slash command works
- Try again within 3s → verify cooldown message
- Ask an unauthorized user to try → verify "not authorized" message

- [ ] **Step 4: Commit (if .env.example updated)**

No code changes needed unless .env.example was adjusted.
