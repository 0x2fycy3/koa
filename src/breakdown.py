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
- "pinyin": the pinyin transliteration as plain text, no special formatting
- "english": the English translation as plain text, no special formatting

### SEGMENTATION RULE
Group words into MEANING CHUNKS. Punctuation (：，。、etc.) attaches to the word before it.

### LONG SENTENCE RULE
If the input contains more than one grammatical clause, split into multiple card objects — one per clause.

### EXAMPLE OUTPUT

Input: 概念：20小时法则 vs. 十年的逃避

[
  {
    "original": "概念：20小时法则 vs. 十年的逃避",
    "pinyin": "Gàiniàn: 20 xiǎoshí fǎzé vs. shí nián de táobì",
    "english": "Concept: 20-hour rule vs. ten years of avoidance"
  }
]

Input: 只需大约20小时专注且刻意的练习，就能从对某个领域一无所知达到相当胜任的程度。

[
  {
    "original": "只需大约20小时专注且刻意的练习",
    "pinyin": "Zhǐ xū dàyuē 20 xiǎoshí zhuānzhù qiě kèyì de liànxí",
    "english": "You only need about 20 hours of focused, deliberate practice"
  },
  {
    "original": "就能从对某个领域一无所知",
    "pinyin": "jiù néng cóng duì mǒu gè lǐngyù yīwú suǒzhī",
    "english": "to go from knowing absolutely nothing about a field"
  },
  {
    "original": "达到相当胜任的程度",
    "pinyin": "dádào xiāngdāng shèngrèn de chéngdù",
    "english": "to reaching a reasonably competent level"
  }
]

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
    except Exception as e:
        logger.error("API call failed: %s", e)
        raise BreakdownError(
            "Sorry, the breakdown service is temporarily unavailable. Please try again."
        ) from e
