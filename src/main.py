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
