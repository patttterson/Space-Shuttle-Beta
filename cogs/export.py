from __future__ import annotations

import csv
import os

import discord
from discord import app_commands
from discord.ext import commands

import db


class ExportCog(commands.Cog):
    export = app_commands.Group(name="export", description="Export commands")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def tournament_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if interaction.guild is None:
            return []
        rows = await db.get_tournaments_by_server(interaction.guild.id)
        names = [row[1] for row in rows[1:]]
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    @export.command(name="participants", description="Export participants from a tournament, sorted by rating.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def participants(self, interaction: discord.Interaction, tournament_name: str):
        assert interaction.guild is not None
        participants = await db.export_participants_full(interaction.guild.id, tournament_name)
        os.makedirs(f"exports/{interaction.guild.id}", exist_ok=True)
        with open(f"exports/{interaction.guild.id}/participants.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerows(participants)
        await interaction.response.send_message(f"exporting players in {tournament_name}", file=discord.File(f"exports/{interaction.guild.id}/participants.csv"))

    @export.command(name="seeding-list", description="Export participants from a tournament, sorted by rating. Good for importing into a bracket website")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def seeding_list(self, interaction: discord.Interaction, tournament_name: str):
        assert interaction.guild is not None
        participants = await db.export_participants(interaction.guild.id, tournament_name)
        os.makedirs(f"exports/{interaction.guild.id}", exist_ok=True)
        with open(f"exports/{interaction.guild.id}/participants.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerows(participants)
        await interaction.response.send_message(f"exporting players in {tournament_name}", file=discord.File(f"exports/{interaction.guild.id}/participants.csv"))

    @export.command(name="player-counts", description="Get player counts for all tournaments in the server.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def player_counts(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        counts = await db.get_participant_counts(interaction.guild.id)
        os.makedirs(f"exports/{interaction.guild.id}", exist_ok=True)
        with open(f"exports/{interaction.guild.id}/participant_counts.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerows(counts)
        await interaction.response.send_message("Player counts for tournaments in this server:", file=discord.File(f"exports/{interaction.guild.id}/participant_counts.csv"))

    @export.command(name="checkins", description="get a list of checked in players. Good for importing into a bracket website")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def checkins(self, interaction: discord.Interaction, *, tournament_name: str, checkin_channel: discord.TextChannel, checkin_message: str):
        assert interaction.guild is not None
        await interaction.response.defer()
        message = await checkin_channel.fetch_message(int(checkin_message))
        reactions = message.reactions
        checkin_ids = set()
        for i in reactions:
            users = [user async for user in i.users()]
            for ii in users:
                checkin_ids.add(ii.id)
        data = await db.export_participants_if_in_set(interaction.guild.id, tournament_name, checkin_ids)
        os.makedirs(f"exports/{interaction.guild.id}", exist_ok=True)
        with open(f"exports/{interaction.guild.id}/checkin.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data)
        await interaction.followup.send(f"exporting checked in players in {tournament_name}", file=discord.File(f"exports/{interaction.guild.id}/checkin.csv"))


async def setup(bot: commands.Bot):
    await bot.add_cog(ExportCog(bot))
