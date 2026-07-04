import discord
from discord.ext import commands
from discord import app_commands

from . import config
from .logger import setup_logging, get_logger
from .breakdown import breakdown_phrase, transcribe_image, BreakdownError, TranscriptionError, BreakdownCard

setup_logging()
logger = get_logger(__name__)


def _check_allowed(source) -> bool:
    if not config.ALLOWED_USER_IDS:
        return True
    user = source.author if hasattr(source, "author") else source.user
    return user.id in config.ALLOWED_USER_IDS


def _build_embeds(cards: list[BreakdownCard], level: str = "noob") -> list[discord.Embed]:
    embeds = []
    for i, card in enumerate(cards):
        embed = discord.Embed(color=0xFA8072)
        if level == "noob" and card.words:
            lines = ["\u200b", "**Word‑by‑word:**"]
            for j, w in enumerate(card.words, 1):
                lines.append(f"{j}. {w['chinese']} → *{w['pinyin']}* → ||{w['english']}||")
            lines.append("")
            lines.append(f"**Translation:** {card.english}")
            value = "\n".join(lines)
        else:
            pinyin = card.pinyin[:1000] + "..." if len(card.pinyin) > 1024 else card.pinyin
            english = card.english[:1000] + "..." if len(card.english) > 1024 else card.english
            pinyin = pinyin.replace("||", "")
            value = f"**Pinyin:** {pinyin}\n\n**English:** {english}"
        if len(value) > 1024:
            value = value[:1000] + "..."
        embed.add_field(name=card.original, value=value, inline=False)
        embed.set_footer(text=f"Model: {config.DEEPSEEK_MODEL}")
        embed.set_image(url="https://i.pinimg.com/736x/f1/b8/a0/f1b8a068155fd8593c1834d64cf7945e.jpg")
        embeds.append(embed)
    return embeds


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

    async def on_ready(self) -> None:
        logger.info("Bot logged in as %s (ID: %s)", self.user, self.user.id)


bot = BreakdownBot()


# --- Slash command ---

@bot.tree.command(
    name="breakdown",
    description="Break down a Chinese phrase (text or image) with pinyin and English translation",
)
@app_commands.describe(
    phrase="The Chinese phrase to break down",
    image="Or upload an image containing Chinese text",
    level="Breakdown style",
)
@app_commands.choices(level=[
    app_commands.Choice(name="Beginner (word‑by‑word)", value="noob"),
    app_commands.Choice(name="Advanced (chunked spoilers)", value="advanced"),
])
@app_commands.checks.cooldown(
    rate=1,
    per=config.COOLDOWN_SECONDS,
    key=lambda i: i.user.id,
)
async def slash_breakdown(
    interaction: discord.Interaction,
    phrase: str | None = None,
    image: discord.Attachment | None = None,
    level: str = "noob",
) -> None:
    if not _check_allowed(interaction):
        logger.warning("Auth denied for user %s", interaction.user.id)
        await interaction.response.send_message(
            "You are not authorized to use this bot.", ephemeral=True
        )
        return

    if not phrase and not image:
        await interaction.response.send_message(
            "Please provide a phrase or upload an image.", ephemeral=True
        )
        return

    from_image = False
    if image and not phrase:
        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message(
                "Please upload an image file (PNG, JPEG, etc.).", ephemeral=True
            )
            return
        from_image = True
    else:
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

    logger.info("Slash breakdown from %s: phrase=%r image=%s level=%s",
                interaction.user.id, phrase, from_image, level)

    await interaction.response.defer()

    if from_image:
        try:
            image_data = await image.read()
            phrase = await transcribe_image(image_data, image.content_type)
        except TranscriptionError:
            logger.exception("Transcription failed")
            await interaction.followup.send(
                "Sorry, transcription failed. Please try again."
            )
            return
        if not phrase.strip():
            await interaction.followup.send("No text found in the image.")
            return

    try:
        cards = await breakdown_phrase(phrase, level=level)
    except BreakdownError:
        logger.exception("Breakdown failed for phrase %r", phrase)
        await interaction.followup.send(
            "Sorry, the breakdown service is temporarily unavailable. Please try again."
        )
        return

    embeds = _build_embeds(cards, level=level)
    logger.info("Sending %d embeds for %d cards", len(embeds), len(cards))

    msg = await interaction.followup.send(embed=embeds[0])
    if len(embeds) > 1:
        real_msg = await interaction.channel.fetch_message(msg.id)
        thread = await real_msg.create_thread(name=cards[0].original[:100])
        for embed in embeds[1:]:
            await thread.send(embed=embed)


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
        logger.warning("Auth denied for user %s", ctx.author.id)
        await ctx.send("You are not authorized to use this bot.", delete_after=5)
        return

    logger.info("Prefix command from %s: %r", ctx.author.id, phrase)
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
            cards = await breakdown_phrase(phrase, level="noob")
        except BreakdownError:
            logger.exception("Breakdown failed for phrase %r", phrase)
            await ctx.send(
                "Sorry, the breakdown service is temporarily unavailable. Please try again."
            )
            return

    embeds = _build_embeds(cards, level="noob")
    logger.info("Sending %d embeds for %d cards", len(embeds), len(cards))
    if len(embeds) == 1:
        await ctx.send(embed=embeds[0])
        return
    msg = await ctx.send(embed=embeds[0])
    thread = await msg.create_thread(name=cards[0].original[:100])
    for embed in embeds[1:]:
        await thread.send(embed=embed)


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
