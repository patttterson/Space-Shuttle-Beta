from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import db
import tetrio
import utils


class RegistrationModal(discord.ui.Modal):
    def __init__(self, bot, guild_id, is_tetrio, tournament_name, *, title="", timeout=None, custom_id="r_modal"):
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)
        self.bot = bot
        self.guild_id = guild_id
        self.is_tetrio = is_tetrio
        self.tournament_name = tournament_name

        label = "Enter your TETR.IO username" if is_tetrio else f"Enter your rating for {tournament_name}"
        self.name = discord.ui.TextInput(label=label)
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        role_id = await db.get_tournament_role(interaction.guild.id, self.tournament_name)
        if not role_id:
            await interaction.response.send_message("Error in registration: No role associated with this tournament. Please contact staff", ephemeral=True)
            return

        name_input = self.name.value
        if not self.is_tetrio:
            await db.insert_into_tournament(interaction.user.id, interaction.user.name, interaction.guild.id, self.tournament_name, float(name_input))
            await utils.add_role(interaction.guild, interaction.user.id, role_id)
            await interaction.response.send_message(f"Successfully registered for `{self.tournament_name}` with rating `{name_input}`", ephemeral=True)
            await utils.log(self.bot, interaction.guild.id, f"Player `{interaction.user.name}` registered for `{self.tournament_name}` with rating `{name_input}`")
            await utils.update_tournament_status(self.bot, interaction.guild.id)
        else:
            t_data, _ = await tetrio.get_player_tl_data(self.name.value)
            if t_data["success"] == False:
                if t_data["error"]["msg"] == "No such user! | Either you mistyped something, or the account no longer exists.":
                    await interaction.response.send_message("Registration Failed: No such user! | Either you mistyped something, or the account no longer exists.", ephemeral=True)
                else:
                    await interaction.response.send_message("Registration Failed: An unknown error occured. Please contact staff", ephemeral=True)
            elif t_data["data"]["tr"] == -1:
                await interaction.response.send_message("Registration Failed: You must have a TR on TETR.IO to register for the tournament", ephemeral=True)
            else:
                caps = await db.get_floor_and_cap(interaction.guild.id, self.tournament_name)
                if (caps[0] is not None or caps[1] is not None):
                    if t_data["data"]["rank"] == "z":
                        await interaction.response.send_message("Registration Failed: You must have a letter rank in order to play in a capped or floored tournament", ephemeral=True)
                    else:
                        peak_rank = tetrio.ranks[t_data["data"]["bestrank"]]
                        if t_data["data"]["past"] is not None:
                            for i in t_data["data"]["past"]:
                                if t_data["data"]["past"][i]["bestrank"] is not None:
                                    peak_rank = min(peak_rank, tetrio.ranks[t_data["data"]["past"][i]["bestrank"]])
                        if caps[0] is not None and peak_rank > tetrio.ranks[caps[0]]:
                            await interaction.response.send_message("Registration Failed. Your peak rank is too low to play in this tournament", ephemeral=True)
                        elif caps[1] is not None and peak_rank < tetrio.ranks[caps[1]]:
                            await interaction.response.send_message("Registration Failed. Your peak rank is too high to play in this tournament", ephemeral=True)
                        else:
                            player, _ = await tetrio.get_player(self.name.value)
                            username = player["_id"]
                            if await db.check_if_username_registered_for_tournament(interaction.guild.id, self.tournament_name, username):
                                await interaction.response.send_message("Registration Failed: That TETR.IO username is already registered for this tournament. If you believe this is an error, please contact a moderator.", ephemeral=True)
                                return
                            rating = t_data["data"]["tr"]
                            await db.insert_into_tournament(interaction.user.id, interaction.user.name, interaction.guild.id, self.tournament_name, rating, username)
                            await interaction.response.send_message(f"Successfully registered for `{self.tournament_name}` under username `{name_input}`, good luck!", ephemeral=True)
                            await utils.add_role(interaction.guild, interaction.user.id, role_id)
                            await utils.log(self.bot, interaction.guild.id, f"Player `{interaction.user.name}` registered for `{self.tournament_name}` under username `{name_input}` with rating `{rating}`")
                            await utils.update_tournament_status(self.bot, interaction.guild.id)
                else:
                    player, _ = await tetrio.get_player(self.name.value)
                    username = player["_id"]
                    if await db.check_if_username_registered_for_tournament(interaction.guild.id, self.tournament_name, username):
                        await interaction.response.send_message("Registration Failed: That TETR.IO username is already registered for this tournament. If you believe this is an error, please contact a moderator.", ephemeral=True)
                        return
                    rating = t_data["data"]["tr"]
                    await db.insert_into_tournament(interaction.user.id, interaction.user.name, interaction.guild.id, self.tournament_name, rating, username)
                    await interaction.response.send_message(f"Successfully registered for `{self.tournament_name}` under username `{name_input}`, good luck!", ephemeral=True)
                    await utils.add_role(interaction.guild, interaction.user.id, role_id)
                    await utils.log(self.bot, interaction.guild.id, f"Player `{interaction.user.name}` registered for `{self.tournament_name}` under username `{name_input}` with rating `{rating}`")
                    await utils.update_tournament_status(self.bot, interaction.guild.id)


class RegistrationView(discord.ui.View):
    def __init__(self, bot, guild_id, tournaments, *, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot
        for tournament in tournaments:
            button = discord.ui.Button(label=tournament)
            button.custom_id = f"{guild_id}-{tournament}"
            button.callback = lambda interaction, t=tournament: self.register_for_tournament(interaction, t)
            self.add_item(button)

    async def _remove_player(self, interaction: discord.Interaction, tournament_name: str):
        assert interaction.guild is not None
        await db.remove_from_tournament(interaction.guild.id, interaction.user.id, tournament_name)
        await interaction.response.edit_message(content=f"Removed registration for `{tournament_name}`", view=discord.ui.View())
        await utils.update_tournament_status(self.bot, interaction.guild.id)
        await utils.log(self.bot, interaction.guild.id, f"player `{interaction.user.name}` removed their registration for `{tournament_name}`")

        role = await db.get_tournament_role(interaction.guild.id, tournament_name)
        assert role is not None
        await utils.remove_role(interaction.guild, interaction.user.id, role)

    async def _cancel_removal(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Cancelled removal of registration", view=discord.ui.View())

    async def register_for_tournament(self, interaction: discord.Interaction, tournament_name: str):
        assert interaction.guild is not None
        is_registered = await db.check_if_player_registered_for_tournament(interaction.guild.id, interaction.user.id, tournament_name)
        if is_registered:
            await interaction.response.send_message(
                f"You are already registered for {tournament_name}. "
                "Would you like to remove your registration?",
                view=utils.ConfirmActionView(
                    interaction,
                    lambda itx, t=tournament_name: self._remove_player(itx, t),
                    self._cancel_removal,
                ),
                ephemeral=True,
            )
        else:
            is_tetrio = await db.is_tournament_tetrio(interaction.guild.id, tournament_name)
            await interaction.response.send_modal(RegistrationModal(self.bot, interaction.guild.id, is_tetrio, tournament_name, title=f"Register for {tournament_name}"))


async def register_previous_views(bot: commands.Bot):
    guilds = await db.get_guilds()
    for i in guilds:
        tours = await db.get_open_tournaments(i)
        m_id = await db.get_registration_messages_info(i)
        bot.add_view(RegistrationView(bot, i, tours), message_id=m_id[1])


class RegistrationCog(commands.Cog):
    registration = app_commands.Group(name="registration", description="Registration commands")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def tournament_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if interaction.guild is None:
            return []
        rows = await db.get_tournaments_by_server(interaction.guild.id)
        names = [row[1] for row in rows[1:]]
        return [app_commands.Choice(name=n, value=n) for n in names if current.lower() in n.lower()][:25]

    async def cog_load(self):
        await register_previous_views(self.bot)

    @registration.command(name="update", description="update registration messages to show new tournaments")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def update(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        ids = await db.get_registration_messages_info(interaction.guild.id)
        text_channel = interaction.guild.get_channel(ids[0])
        assert isinstance(text_channel, discord.TextChannel)
        message = await text_channel.fetch_message(ids[1])
        tournaments = await db.get_open_tournaments(interaction.guild.id)
        self.bot.add_view(RegistrationView(self.bot, interaction.guild.id, tournaments), message_id=ids[1])
        await message.edit(content="Register for a tournament by clicking one of the below tournaments", view=RegistrationView(self.bot, interaction.guild.id, tournaments))
        await interaction.response.send_message(f"Updated the registration message at <#{ids[0]}>")
        await utils.update_tournament_status(self.bot, interaction.guild.id)

    @registration.command(name="manual-register", description="Manually register a player to your tournament.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def manual_register(self, interaction: discord.Interaction, tournament_name: str, player: discord.User, registration_input: str, override_requirements: bool = False):
        assert interaction.guild is not None
        player_id = player.id

        if not await db.check_if_tournament_exists(tournament_name, interaction.guild.id):
            await interaction.response.send_message("Error: Tournament does not exist")
            return
        if await db.check_if_player_registered_for_tournament(interaction.guild.id, player.id, tournament_name):
            await interaction.response.send_message("Error: Player already registered for tournament")
            return

        is_tetrio = await db.is_tournament_tetrio(interaction.guild.id, tournament_name)
        role = await db.get_tournament_role(interaction.guild.id, tournament_name)
        assert role is not None

        if not is_tetrio:
            await db.insert_into_tournament(player_id, player.name, interaction.guild.id, tournament_name, float(registration_input))
            await utils.add_role(interaction.guild, player_id, role)
            await interaction.response.send_message(f"Successfully registered `{player.name}` for `{tournament_name}` with rating `{registration_input}`", ephemeral=True)
            await utils.log(self.bot, interaction.guild.id, f"Player `{player.name}` manually registered for `{tournament_name}` with rating `{registration_input}`")
            await utils.update_tournament_status(self.bot, interaction.guild.id)
            return

        t_data, _ = await tetrio.get_player_tl_data(registration_input)
        if not t_data["success"]:
            if t_data["error"]["msg"] == "No such user! | Either you mistyped something, or the account no longer exists.":
                await interaction.response.send_message("Registration Failed: No such user! | Either you mistyped something, or the account no longer exists.", ephemeral=True)
            else:
                await interaction.response.send_message("Registration Failed: An unknown error occured. Please contact staff", ephemeral=True)
            return

        if t_data["data"]["tr"] == -1:
            await interaction.response.send_message("Registration Failed: They must have a TR on TETR.IO to register for the tournament", ephemeral=True)
            return

        if not override_requirements:
            caps = await db.get_floor_and_cap(interaction.guild.id, tournament_name)
            if caps[0] is not None or caps[1] is not None:
                if t_data["data"]["rank"] == "z":
                    await interaction.response.send_message("Registration Failed: They must have a letter rank in order to play in a capped or floored tournament", ephemeral=True)
                    return
                peak_rank = tetrio.ranks[t_data["data"]["bestrank"]]
                if t_data["data"]["past"] is not None:
                    for season in t_data["data"]["past"].values():
                        if season["bestrank"] is not None:
                            peak_rank = min(peak_rank, tetrio.ranks[season["bestrank"]])
                if caps[0] is not None and peak_rank > tetrio.ranks[caps[0]]:
                    await interaction.response.send_message("Registration Failed. Their peak rank is too low to play in this tournament")
                    return
                if caps[1] is not None and peak_rank < tetrio.ranks[caps[1]]:
                    await interaction.response.send_message("Registration Failed. Their peak rank is too high to play in this tournament")
                    return

        user_data, _ = await tetrio.get_player(registration_input)
        tetrio_username = user_data["_id"]
        if await db.check_if_username_registered_for_tournament(interaction.guild.id, tournament_name, tetrio_username):
            await interaction.response.send_message("Registration Failed: That TETR.IO username is already registered for this tournament", ephemeral=True)
            return
        rating = t_data["data"]["tr"]
        await db.insert_into_tournament(player_id, user_data["username"], interaction.guild.id, tournament_name, rating, tetrio_username)
        await interaction.response.send_message(f"Successfully manually registered `{user_data['username']}` for `{tournament_name}` under username `{registration_input}`")
        await utils.add_role(interaction.guild, player_id, role)
        await utils.log(self.bot, interaction.guild.id, f"Player `{user_data['username']}` manually registered for `{tournament_name}` by {interaction.user.mention} under username `{registration_input}` with rating `{rating}`")
        await utils.update_tournament_status(self.bot, interaction.guild.id)

    @registration.command(name="manual-unregister", description="Manually unregister a player to your tournament.")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.autocomplete(tournament_name=tournament_autocomplete)
    async def manual_unregister(self, interaction: discord.Interaction, tournament_name: str, player: discord.Member):
        assert interaction.guild is not None
        await db.remove_from_tournament(interaction.guild.id, player.id, tournament_name)
        await interaction.response.send_message(content=f"Removed registration from `{tournament_name}` from {player.mention} if they were registered")
        await utils.update_tournament_status(self.bot, interaction.guild.id)
        role = await db.get_tournament_role(interaction.guild.id, tournament_name)
        assert role is not None
        await utils.remove_role(interaction.guild, interaction.user.id, role)


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot))
