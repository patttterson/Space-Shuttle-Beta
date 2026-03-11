import discord
from discord.ext import commands

import db
import tetrio

ADMIN_GUILD_ID = 1481134598858477580
OWNER_IDS = {843230753734918154, 317475187391987713}



def is_admin():
    async def predicate(ctx: commands.Context):
        if ctx.guild is None or ctx.guild.id != ADMIN_GUILD_ID:
            return False
        return ctx.author.id in OWNER_IDS
    return commands.check(predicate)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="update_bracket_cap")
    @is_admin()
    async def admin_update_bracket_cap(self, ctx: commands.Context, server_id: int, limit: int):
        pass

    @commands.command(name="execute_dql")
    @is_admin()
    async def admin_execute_dql(self, ctx: commands.Context, *, sql: str):
        await db.execute_dql(sql)
        await ctx.send("Executed DQL Query", file=discord.File("exports/return.csv"))

    @commands.command(name="execute_dml")
    @is_admin()
    async def admin_execute_dml(self, ctx: commands.Context, *, sql: str):
        await db.execute_dml(sql)
        await ctx.send("Executed DML query")
    
    @commands.command(name="invalidate_user_cache")
    @is_admin()
    async def admin_invalidate_api_cache(self, ctx: commands.Context):
        tetrio._cache.clear()
        await ctx.send("Cleared TETR.IO API cache")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
