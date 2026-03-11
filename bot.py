import discord
from discord.ext import commands

from typing import Literal, Optional

import os
from dotenv import load_dotenv
load_dotenv()

import db

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class Bot(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)

    async def setup_hook(self):
        await db.init()
        await self.load_extension("cogs.tournament")
        await self.load_extension("cogs.registration")
        await self.load_extension("cogs.export")
        await self.load_extension("cogs.bracket")
        await self.load_extension("cogs.server")
        await self.load_extension("cogs.admin")

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        print("views synced")

    async def on_message(self, message):
        await self.process_commands(message)


bot = Bot(command_prefix='s.', intents=intents)

test_servers = [345648584907030539, 1364758407042826321, 1364774379396927518, 1364775095406694461]

ALL_COGS = [
    "cogs.tournament",
    "cogs.registration",
    "cogs.export",
    "cogs.bracket",
    "cogs.server",
    "cogs.admin",
]


@bot.command()
@commands.is_owner()
async def load(ctx: commands.Context, cog: str):
    cogs = ALL_COGS if cog == "*" else [f"cogs.{cog}"]
    results = []
    for c in cogs:
        try:
            await bot.load_extension(c)
            results.append(f"✓ {c}")
        except Exception as e:
            results.append(f"✗ {c}: {e}")
    await ctx.send("\n".join(results))


@bot.command()
@commands.is_owner()
async def unload(ctx: commands.Context, cog: str):
    cogs = ALL_COGS if cog == "*" else [f"cogs.{cog}"]
    results = []
    for c in cogs:
        try:
            await bot.unload_extension(c)
            results.append(f"✓ {c}")
        except Exception as e:
            results.append(f"✗ {c}: {e}")
    await ctx.send("\n".join(results))


@bot.command()
@commands.is_owner()
async def reload(ctx: commands.Context, cog: str):
    cogs = ALL_COGS if cog == "*" else [f"cogs.{cog}"]
    results = []
    for c in cogs:
        try:
            await bot.reload_extension(c)
            results.append(f"✓ {c}")
        except Exception as e:
            results.append(f"✗ {c}: {e}")
    await ctx.send("\n".join(results))


@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        exit(1)
    bot.run(TOKEN)
