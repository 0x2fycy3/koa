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


def _build_embeds(cards: list[BreakdownCard]) -> list[discord.Embed]:
    embeds = []
    for i, card in enumerate(cards):
        embed = discord.Embed(color=0xFA8072)
        pinyin = card.pinyin[:1000] + "..." if len(card.pinyin) > 1024 else card.pinyin
        english = card.english[:1000] + "..." if len(card.english) > 1024 else card.english
        value = f"**Pinyin:** {pinyin}\n\n**English:** {english}"
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
        logger.warning("Auth denied for user %s", interaction.user.id)
        await interaction.response.send_message(
            "You are not authorized to use this bot.", ephemeral=True
        )
        return

    logger.info("Slash command from %s: %r", interaction.user.id, phrase)
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
        logger.exception("Breakdown failed for phrase %r", phrase)
        await interaction.followup.send(
            "Sorry, the breakdown service is temporarily unavailable. Please try again."
        )
        return

    embeds = _build_embeds(cards)
    logger.info("Sending %d embeds for %d cards", len(embeds), len(cards))
    msg = await interaction.followup.send(embed=embeds[0])
    if len(embeds) > 1:
        try:
            thread = await interaction.channel.create_thread(
                name=cards[0].original[:100],
                message=msg,
            )
            for embed in embeds[1:]:
                await thread.send(embed=embed)
        except Exception as e:
            logger.error("Thread creation failed from slash: %s", e)
            for embed in embeds[1:]:
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
            cards = await breakdown_phrase(phrase)
        except BreakdownError:
            logger.exception("Breakdown failed for phrase %r", phrase)
            await ctx.send(
                "Sorry, the breakdown service is temporarily unavailable. Please try again."
            )
            return

    embeds = _build_embeds(cards)
    logger.info("Sending %d embeds for %d cards", len(embeds), len(cards))
    msg = await ctx.send(embed=embeds[0])
    if len(embeds) > 1:
        try:
            thread = await msg.create_thread(name=cards[0].original[:100])
            for embed in embeds[1:]:
                await thread.send(embed=embed)
        except Exception as e:
            logger.error("Thread creation failed: %s", e)
            for embed in embeds[1:]:
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
