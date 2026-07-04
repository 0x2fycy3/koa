<div align="center">

# 可 — koa

**Chinese language breakdown Discord bot**  
Pinyin · English · Right in your server

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-API-4D6BFE?style=flat-square)](https://deepseek.com)
[![uv](https://img.shields.io/badge/uv-package-6A3C8E?style=flat-square)](https://github.com/astral-sh/uv)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)]()

</div>

---

## Overview

**koa** breaks down any Chinese phrase into clause-by-clause cards with pinyin and English translation. Just type `/breakdown` or `!breakdown` in Discord — the bot sends back a clean embed with spoiler-tagged chunks you can click to reveal.

> Powered by [DeepSeek](https://deepseek.com) via an OpenAI-compatible API. No database, no bloat.

---

## Quick Start

```bash
git clone https://github.com/yourname/koa.git
cd koa
cp .env.example .env   # fill in your keys
just setup
just run
```

---

Copy `.env.example` to `.env` and fill in your keys.

---

## Commands

| Command | Description |
|---------|-------------|
| `/breakdown <phrase>` | Slash command — ephemeral validation, public result |
| `!breakdown <phrase>` | Prefix command — typing indicator, public result |

Cooldown: 3 seconds per user. Unauthorized users get a polite rejection.

---

## Project Structure

```
koa/
├── src/
│   ├── main.py          # Discord bot (commands, cooldown, permissions)
│   ├── breakdown.py     # DeepSeek API call + JSON parsing
│   ├── config.py        # .env settings
│   └── logger.py        # Structured logging
├── .env.example
├── pyproject.toml
└── justfile
```

---

## Tech

- **uv** — package manager
- **discord.py** — bot framework
- **openai** — DeepSeek-compatible API client
- **just** — task runner

Licensed under [MIT](LICENSE).
