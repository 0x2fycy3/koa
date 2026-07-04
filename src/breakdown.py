import base64
import json
from dataclasses import dataclass

from openai import AsyncOpenAI

from . import config
from .logger import get_logger

logger = get_logger(__name__)

ADVANCED_SYSTEM_PROMPT = """You are a Chinese language teaching assistant.
Your ENTIRE response must be a valid JSON array. No text before or after the JSON.

Each element of the array is one card (one grammatical clause), with exactly three keys:
- "original": the Chinese clause as-is
- "pinyin": each chunk wrapped in ||double pipes|| immediately followed by (N) — on ONE line, no line breaks
- "english": each chunk wrapped in ||double pipes|| immediately followed by (N) — on ONE line, no line breaks. Extra grammatical words get ||(–)||

CRITICAL: Every chunk MUST be wrapped in || ... ||(N). Example: ||你好||(1) ||世界||(2). Do NOT put chunks on separate lines. Do NOT omit the || pipes.

---

### SEGMENTATION RULE
Group words into MEANING CHUNKS — words that only make sense together stay in the same spoiler block. Only split when each part carries independent, learnable meaning on its own. Punctuation marks (`：`, `，`, `。`, `、` etc.) always attach to the word immediately before them — never as standalone chunks.

### MAPPING RULE
Numbers link **meaning**, not position. If English word order differs from Chinese, numbers jump in the English line — but always refer to the same Chinese chunk.

### LONG SENTENCE RULE
If the input contains more than one grammatical clause, split into multiple card objects — one per clause.

---

### EXAMPLE OUTPUT

Input: 概念：20小时法则 vs. 十年的逃避

[
  {
    "original": "概念：20小时法则 vs. 十年的逃避",
    "pinyin": "||Gàiniàn：||(1) ||20 xiǎoshí fǎzé||(2) ||vs.||(–) ||shí nián de táobì||(3)",
    "english": "||Concept:||(1) ||20-hour rule||(2) ||vs.||(–) ||ten years of avoidance||(3)"
  }
]

Input: 只需大约20小时专注且刻意的练习，就能从对某个领域一无所知达到相当胜任的程度。

[
  {
    "original": "只需大约20小时专注且刻意的练习",
    "pinyin": "||Zhǐ xū||(1) ||dàyuē 20 xiǎoshí||(2) ||zhuānzhù qiě kèyì de liànxí||(3)",
    "english": "||You only need||(1) ||about 20 hours||(2) ||of focused, deliberate practice||(3)"
  },
  {
    "original": "就能从对某个领域一无所知",
    "pinyin": "||jiù néng||(1) ||cóng||(2) ||duì mǒu gè lǐngyù yīwú suǒzhī||(3)",
    "english": "||to go||(1) ||from||(2) ||knowing absolutely nothing about a field||(3)"
  },
  {
    "original": "达到相当胜任的程度",
    "pinyin": "||dádào||(1) ||xiāngdāng shèngrèn de chéngdù||(2)",
    "english": "||to reaching||(1) ||a reasonably competent level||(2)"
  }
]

---

Return ONLY the JSON array. No explanation, no markdown fences, no commentary."""

NOOB_SYSTEM_PROMPT = """You are a Chinese teacher for complete beginners.
Return ONLY a JSON array, no other text.

Each card (one clause) has:
- "original": Chinese clause
- "pinyin": full pinyin (one line)
- "english": full English translation (one line)
- "words": array of {chinese, pinyin, english} — EVERY word broken down

Split by Chinese WORDS (not characters). 学生 stays "学生", not "学"+"生".
Particles (的/了/着/地/得) get "(particle)" as meaning.
Punctuation (。，：) gets its own entry.

Split long sentences into multiple cards (one per clause).

EXAMPLE:
Input: 只需大约20小时专注且刻意的练习
[{"original":"只需大约20小时专注且刻意的练习","pinyin":"zhǐ xū dàyuē 20 xiǎoshí zhuānzhù qiě kèyì de liànxí","english":"You only need about 20 hours of focused, deliberate practice","words":[{"chinese":"只需","pinyin":"zhǐ xū","english":"only need"},{"chinese":"大约","pinyin":"dàyuē","english":"about"},{"chinese":"20","pinyin":"20","english":"20"},{"chinese":"小时","pinyin":"xiǎoshí","english":"hours"},{"chinese":"专注","pinyin":"zhuānzhù","english":"focused"},{"chinese":"且","pinyin":"qiě","english":"and"},{"chinese":"刻意","pinyin":"kèyì","english":"deliberate"},{"chinese":"的","pinyin":"de","english":"(particle)"},{"chinese":"练习","pinyin":"liànxí","english":"practice"}]}]

Return ONLY JSON."""


@dataclass
class BreakdownCard:
    original: str
    pinyin: str
    english: str
    words: list[dict[str, str]] | None = None


class BreakdownError(Exception):
    """Raised when the breakdown API call or parsing fails."""


async def breakdown_phrase(phrase: str, level: str = "noob") -> list[BreakdownCard]:
    client = AsyncOpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
    )
    system_prompt = NOOB_SYSTEM_PROMPT if level == "noob" else ADVANCED_SYSTEM_PROMPT
    logger.info("Using level=%s prompt", level)
    try:
        response = await client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": phrase},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        logger.info("API raw response: %s", content)
        content = content.strip()
        # ponytail: strip markdown fences if the model ignores the prompt
        if content.startswith("```"):
            content = content.strip("`").strip()
            if content.lower().startswith("json"):
                content = content[4:].strip()

        cards_data = json.loads(content)
        logger.info("Parsed %d cards: %s", len(cards_data), [c.get("original", "?") for c in cards_data])

        if not isinstance(cards_data, list):
            raise BreakdownError("Expected a JSON array, got something else")

        cards = []
        for item in cards_data:
            if not all(k in item for k in ("original", "pinyin", "english")):
                raise BreakdownError(f"Card missing required keys: {item}")
            words = item.get("words")
            if not isinstance(words, list):
                words = None
            cards.append(BreakdownCard(
                original=item["original"],
                pinyin=item["pinyin"],
                english=item["english"],
                words=words,
            ))
        return cards

    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s, content: %s", e, content)
        raise BreakdownError("The model returned an unexpected response. Please try again.") from e
    except Exception as e:
        logger.error("API call failed: %s", e)
        raise BreakdownError(
            "Sorry, the breakdown service is temporarily unavailable. Please try again."
        ) from e


class TranscriptionError(Exception):
    """Raised when the image transcription fails."""


async def transcribe_image(image_data: bytes, content_type: str) -> str:
    """Transcribe Chinese text from an image using OpenAI vision model."""
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    b64 = base64.b64encode(image_data).decode()
    data_url = f"data:{content_type};base64,{b64}"

    try:
        response = await client.chat.completions.create(
            model=config.TRANSCRIPTION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                    {
                        "type": "text",
                        "text": "Please transcribe all Chinese text visible in this image. Return only the transcribed text, nothing else.",
                    },
                ],
            }],
            temperature=0,
        )
        text = response.choices[0].message.content or ""
        logger.info("Transcription result: %s", text)
        return text.strip()
    except Exception as e:
        logger.error("Transcription failed: %s", e)
        raise TranscriptionError(
            "Sorry, the transcription service is temporarily unavailable. Please try again."
        ) from e
