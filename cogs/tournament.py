from __future__ import annotations
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import db
import tetrio
import utils

class TournamentCog(commands.Cog):
    tournament = app_commands.Group(name="tournament", description="Tournament commands")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def tournament_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if interaction.guild is None:
            return []
        rows = await db.get_tournaments_by_server(interaction.guild.id)
        names = [row[1] for row in rows[1:]]
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    async def open_tournament_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if interaction.guild is None:
            return []
        names = await db.get_open_tournaments(interaction.guild.id)
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    @tournament.command(name="create-generic", description="Create a generic tournament for your server")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def create_generic(self, interaction: discord.Interaction, tournament_name: str, thread_channel: discord.TextChannel | None = None, participant_role: discord.Role | None = None):
        assert interaction.guild is not None
        guild_id = interaction.guild.id
        thread_id = thread_channel.id if thread_channel is not None else None
        participant_id = participant_role.id if participant_role is not None else None
        tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
        if tournament_exists:
            await interaction.response.send_message(f"Error in creating tournament. Tournament with name {tournament_name} already exists for this server.")
        else:
            await db.insert_tournament(tournament_name=tournament_name, guild_id=guild_id, thread_channel=thread_id, participant_role=participant_id)
            res_string = f"Created tournament {tournament_name}.\n"
            if thread_channel is not None:
                res_string += f"Registered thread channel for tournament as <#{thread_channel.id}>\n"
            if participant_role is not None:
                res_string += f"Registered participant role as <@&{participant_role.id}>\n"
            await interaction.response.send_message(res_string)

    @tournament.command(name="create-tetrio", description="Create a tetrio tournament for your server")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.choices(
        rank_cap=[app_commands.Choice(name=r, value=r) for r in tetrio.ranks],
        rank_floor=[app_commands.Choice(name=r, value=r) for r in tetrio.ranks],
    )
    async def create_tetrio(self, interaction: discord.Interaction, tournament_name: str, rank_cap: str | None = None, rank_floor: str | None = None, thread_channel: discord.TextChannel | None = None, participant_role: discord.Role | None = None):
        assert interaction.guild is not None
        guild_id = interaction.guild.id
        tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
        if tournament_exists:
            await interaction.response.send_message(f"Error in creating tournament. Tournament with name {tournament_name} already exists for this server.")
            return
        await db.insert_tournament(tournament_name=tournament_name, guild_id=guild_id, thread_channel=thread_channel.id if thread_channel else None, participant_role=participant_role.id if participant_role else None, is_tetrio=True, rank_cap=rank_cap, rank_floor=rank_floor)
        res_string = f"Created tournament {tournament_name}.\n"
        if thread_channel is not None:
            res_string += f"Registered thread channel for tournament as <#{thread_channel.id}>\n"
        if participant_role is not None:
            res_string += f"Registered participant role as <@&{participant_role.id}>\n"
        if rank_cap is not None:
            res_string += f"Registered rank cap as {rank_cap}\n"
        if rank_floor is not None:
            res_string += f"Registered rank floor as {rank_floor}"
        await interaction.response.send_message(res_string)

    @tournament.command(name="delete", description="Remove tournament from your server")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def delete(self, interaction: discord.Interaction, tournament_name: str):
        assert interaction.guild is not None
        guild_id = interaction.guild.id
        tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
        if not tournament_exists:
            await interaction.response.send_message(f"Error in deleting tournament. Tournament with name {tournament_name} doos not exist for this server.")
            return

        async def delete_tour(interaction: discord.Interaction, tournament_name: str, guild_id: int):
            await db.remove_tournament(guild_id=guild_id, tournament_name=tournament_name)
            await interaction.response.edit_message(content=f"Deleted tournament {tournament_name}", view=discord.ui.View())

        await interaction.response.send_message(
            f"Delete tournament {tournament_name}?",
            view=utils.ConfirmActionView(interaction, confirm_callback=lambda interaction, tournament_name=tournament_name, guild_id=guild_id: delete_tour(interaction=interaction, tournament_name=tournament_name, guild_id=guild_id))
        )

    @tournament.command(name="list", description="Get all of the tournaments for your server")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def list(self, interaction: discord.Interaction):
        import csv
        import os
        assert interaction.guild is not None
        tours = await db.get_tournaments_by_server(interaction.guild.id)
        os.makedirs(f"exports/{interaction.guild.id}", exist_ok=True)
        with open(f"exports/{interaction.guild.id}/tournaments.csv", "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerows(tours)
        await interaction.response.send_message("Tournaments in this server:", file=discord.File(f"exports/{interaction.guild.id}/tournaments.csv"))

    @tournament.command(name="open-registration", description="open registrations for a tournament")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def open_registration(self, interaction: discord.Interaction, tournament_name: str):
        assert interaction.guild is not None
        tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=interaction.guild.id)
        if not tournament_exists:
            await interaction.response.send_message(f"Could not open registrations for tournament {tournament_name} because the tournament does not exist")
            return
        await db.set_tournament_registrations_state(interaction.guild.id, tournament_name, True)
        await interaction.response.send_message(f"Set registrations to open for tournament {tournament_name}. make sure to run /registration update to reflect changes")

    @tournament.command(name="close-registration", description="close registrations for a tournament")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=open_tournament_autocomplete)
    async def close_registration(self, interaction: discord.Interaction, tournament_name: str):
        assert interaction.guild is not None
        tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=interaction.guild.id)
        if not tournament_exists:
            await interaction.response.send_message(f"Could not close registrations for tournament {tournament_name} because the tournament does not exist")
            return
        await db.set_tournament_registrations_state(interaction.guild.id, tournament_name, False)
        await interaction.response.send_message(f"Set registrations to closed for tournament {tournament_name}. make sure to run /registration update to reflect changes")

    @tournament.command(name="set-thread-channel", description="set thread channel for a tournament")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def set_thread_channel(self, interaction: discord.Interaction, tournament_name: str, thread_channel: discord.TextChannel):
        pass

    @tournament.command(name="refresh-seeding", description="refresh seeding for TETR.IO Tournaments.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def refresh_seeding(self, interaction: discord.Interaction, tournament_name: str, remove_ineligible: bool = True):
        assert interaction.guild is not None
        participants = await db.get_game_users_from_tournament(interaction.guild.id, tournament_name)
        await interaction.response.send_message(f"Updating Player 0 of {len(participants)}")
        response = await interaction.original_response()
        caps = await db.get_floor_and_cap(interaction.guild.id, tournament_name)
        role = await db.get_tournament_role(interaction.guild.id, tournament_name)

        async def remove_player(username: str, reason: str):
            assert interaction.guild is not None
            assert role is not None
            player_data = await db.get_discord_user_from_game_username(interaction.guild.id, tournament_name, username)
            await interaction.followup.send(f"Player <@{player_data[0]}> ({player_data[0]}) was removed from the tournament due to ineligibility ({reason})")
            await utils.remove_role(interaction.guild, player_data[0], role)
            await db.remove_from_tournament(interaction.guild.id, player_data[0], tournament_name)
            await utils.update_tournament_status(self.bot, interaction.guild.id)

        for i, participant in enumerate(participants):
            await response.edit(content=f"Updating Player {i+1} of {len(participants)}")
            t_data, cached_until = await tetrio.get_player_tl_data(participant)
            if not cached_until:
                await asyncio.sleep(1)  # avoid hitting rate limits
            if not t_data["success"] or t_data["data"]["tr"] == -1:
                continue
            if not remove_ineligible or caps[0] is None and caps[1] is None:
                await db.update_rating(interaction.guild.id, tournament_name, participant, t_data["data"]["tr"])
                continue
            if t_data["data"]["rank"] == "z":
                await remove_player(participant, "unranked")
                continue
            peak_rank = tetrio.ranks[t_data["data"]["bestrank"]]
            if t_data["data"]["past"] is not None:
                for season in t_data["data"]["past"].values():
                    if season["bestrank"] is not None:
                        peak_rank = min(peak_rank, tetrio.ranks[season["bestrank"]])
            if caps[0] is not None and peak_rank > tetrio.ranks[caps[0]]:
                await remove_player(participant, "below rank floor")
            elif caps[1] is not None and peak_rank < tetrio.ranks[caps[1]]:
                await remove_player(participant, "above rank cap")
            else:
                await db.update_rating(interaction.guild.id, tournament_name, participant, t_data["data"]["tr"])
        await response.edit(content="Finished updating player ratings")


async def setup(bot: commands.Bot):
    await bot.add_cog(TournamentCog(bot))
