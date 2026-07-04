<div align="center">

# 可 — koa

**Chinese language breakdown Discord bot**  
Pinyin · English · Right in your server

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?style=flat-square&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-API-4D6BFE?style=flat-square)](https://deepseek.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-74AA9C?style=flat-square)](https://openai.com)
[![uv](https://img.shields.io/badge/uv-package-6A3C8E?style=flat-square)](https://github.com/astral-sh/uv)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)]()

</div>

---

## Overview

**koa** breaks down any Chinese phrase into clause-by-clause cards with pinyin and English translation. It supports two modes:

- **Beginner** (default) — word-by-word breakdown. Each word shows `Chinese → pinyin → ||hidden English||`. Click the spoiler to reveal the meaning, try to remember it next time.
- **Advanced** — meaning-chunked spoilers. Pinyin is visible, English is hidden behind `||spoiler||(N)` with matching number links.

You can also upload an image containing Chinese text — koa transcribes it first (via OpenAI `gpt-4o-mini`), then breaks it down.

> Breakdowns powered by [DeepSeek](https://deepseek.com), transcription by [OpenAI](https://openai.com). No database, no bloat.

<img src="assets/usage-sample.png" alt="Usage sample" width="100%">

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

## Commands

| Command | Description |
|---------|-------------|
| `/breakdown <phrase>` | Text mode — break down a Chinese phrase |
| `/breakdown <image>` | Image mode — transcribe an image, then break it down |
| `!breakdown <phrase>` | Prefix command — text only, beginner mode |

**Parameters** (slash command):

| Parameter | Description |
|-----------|-------------|
| `phrase` | Chinese text to break down (optional) |
| `image` | Upload an image containing Chinese text (optional) |
| `level` | `Beginner` (word-by-word, default) or `Advanced` (chunked spoilers) |

At least one of `phrase` or `image` is required. Cooldown: 3 seconds per user.

---

## Project Structure

```
koa/
├── src/
│   ├── main.py          # Discord bot (commands, cooldown, permissions)
│   ├── breakdown.py     # DeepSeek breakdown + OpenAI transcription
│   ├── config.py        # .env settings
│   └── logger.py        # Structured logging
├── .env.example
├── pyproject.toml
└── justfile
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | yes | — | Discord bot token |
| `DEEPSEEK_API_KEY` | yes | — | DeepSeek API key (breakdown) |
| `DEEPSEEK_MODEL` | no | `deepseek-chat` | Model for breakdown |
| `OPENAI_API_KEY` | no | — | OpenAI API key (image transcription) |
| `TRANSCRIPTION_MODEL` | no | `gpt-4o-mini` | Model for image transcription |
| `ALLOWED_USER_IDS` | no | — | Comma-separated user IDs (empty = anyone) |

---

## Tech

- **uv** — package manager
- **discord.py** — bot framework
- **openai** — API client (DeepSeek for breakdown, OpenAI for transcription)
- **just** — task runner

Licensed under [MIT](LICENSE).
