import discord
from discord import app_commands
from discord.ext import commands

import db


class ServerCog(commands.Cog):
    server = app_commands.Group(name="server", description="Server configuration commands")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @server.command(name="set-registration-channel", description="set registration channel for a server. This command will automatically create a registration message")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_registration_channel(self, interaction: discord.Interaction, registration_channel: discord.TextChannel):
        assert interaction.guild is not None
        await db.configure_server_if_not_setup(interaction.guild.id)
        await db.set_registration_channel(interaction.guild.id, registration_channel.id)
        c1 = await registration_channel.send("INFO TEXT")
        c2 = await registration_channel.send("Register for a tournament by clicking one of the below tournaments")
        await db.set_registration_messages(interaction.guild.id, c1.id, c2.id)
        await interaction.response.send_message(f"Configured registration channel for this server as <#{registration_channel.id}>. Make sure to run /registration update to get registration buttons")

    @server.command(name="set-logging-channel", description="set logging channel for a server.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_logging_channel(self, interaction: discord.Interaction, logging_channel: discord.TextChannel):
        assert interaction.guild is not None
        await db.configure_server_if_not_setup(interaction.guild.id)
        await db.set_logging_channel(interaction.guild.id, logging_channel.id)
        await interaction.response.send_message(f"Configured logging channel for this server as <#{logging_channel.id}>")


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerCog(bot))
