import discord
from discord import app_commands
from discord.ext import commands


class BracketCog(commands.Cog):
    bracket = app_commands.Group(name="bracket", description="Bracket commands")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @bracket.command(name="link", description="link a bracket to your tournament. You can link multiple brackets to the same tournament")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def link(self, interaction: discord.Interaction, bracket_url_string: str, tournament_name: str):
        await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June", ephemeral=True)

    @bracket.command(name="unlink", description="unlink a bracket from your tournament.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def unlink(self, interaction: discord.Interaction, bracket_url_string: str, tournament_name: str):
        await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June", ephemeral=True)

    @bracket.command(name="list", description="list all of the brackets in the server")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def list(self, interaction: discord.Interaction):
        await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June", ephemeral=True)

    @bracket.command(name="activate", description="activate a bracket for challonge polling.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def activate(self, interaction: discord.Interaction, bracket_url_string: str):
        await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June", ephemeral=True)

    @bracket.command(name="deactivate", description="deactivate a bracket for challonge polling.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def deactivate(self, interaction: discord.Interaction, bracket_url_string: str):
        await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BracketCog(bot))
