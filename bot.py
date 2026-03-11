import discord
from discord import app_commands
import db
import tetrio as tetrio
from discord.app_commands import checks 
from discord.ext.commands import has_permissions
from discord.ext import commands

from typing import Optional

import time
import csv
import os
from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class Bot(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)

    async def on_ready(self):
        print(f'Logged in as {self.user}')

        await register_previous_views()
        print("views synced")

    async def on_message(self, message):
        await self.process_commands(message)

bot = Bot(command_prefix='s.', intents=intents)

test_servers = [345648584907030539, 1364758407042826321, 1364774379396927518, 1364775095406694461]
async def get_channel(guild_id: int, channel_id: int) -> Optional[discord.TextChannel]:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None
    channel = guild.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return None
    return channel

async def log(guild_id : int, msg : str) -> None:
    channel = await db.get_logging_channel(guild_id)
    if channel is not None:
        channel = await get_channel(guild_id, channel)
        if channel is not None:
            await channel.send(content=msg)

async def add_role(guild_id: int, user_id: int, role_id: int) -> None:
    if not (guild := bot.get_guild(guild_id)):
        return
    if not (user := guild.get_member(user_id)):
        return
    if not (role := guild.get_role(role_id)):
        return
    await user.add_roles(role)

async def remove_role(guild_id: int, user_id: int, role_id: int) -> None:
    if not (guild := bot.get_guild(guild_id)):
        return
    if not (member := guild.get_member(user_id)):
        return
    if not (role := guild.get_role(role_id)):
        return
    await member.remove_roles(role)

class ConfirmActionView(discord.ui.View):
    confirm_button = discord.ui.Button(label="Confirm",style=discord.ButtonStyle.success)
    abort_button = discord.ui.Button(label="Abort",style=discord.ButtonStyle.danger)
    async def success_callback(self, interaction : discord.Interaction):
        await interaction.response.edit_message(content="You clicked the confirm button, but no implementation was provided. This is an error message. Please report this error to the developer",view=discord.ui.View())
    confirm_button.callback = success_callback
    async def abort_callback(self, interaction : discord.Interaction):
        await interaction.response.edit_message(content="Aborted operation",view=discord.ui.View())
    abort_button.callback = abort_callback
    responded = False
    def __init__(self, interaction : discord.Interaction, confirm_callback = None, abort_callback = None, *, timeout = 180,):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        if confirm_callback is not None:
            self.confirm_button.callback = confirm_callback
        if abort_callback is not None:
            self.abort_button.callback = abort_callback
        self.add_item(self.confirm_button)
        self.add_item(self.abort_button)
    async def interaction_check(self, interaction : discord.Interaction):
        self.responded = True
        return True
    async def on_timeout(self):
        if not self.responded:
            await self.interaction.followup.send(content="This action has timed out. If you would like to try again, please enter the command again", view=discord.ui.View(),ephemeral=True)

async def register_for_tournament(interaction : discord.Interaction, tournament_name : str):
    is_registered = await db.check_if_player_registered_for_tournament(interaction.guild.id,interaction.user.id,tournament_name)
    if is_registered:
        async def remove_player(interaction : discord.Interaction, tournament_name : str, user_id : int, guild_id : int):
            await db.remove_from_tournament(guild_id,user_id,tournament_name)
            await interaction.response.edit_message(content=f"Removed registration for {tournament_name}",view=discord.ui.View())
            await update_tournament_status(interaction.guild_id)
            await log(interaction.guild.id,f"player {interaction.user.name} removed their registration for {tournament_name}")
            role = await db.get_tournament_role(interaction.guild.id, tournament_name)
            await remove_role(interaction.guild.id, interaction.user.id, role)
        async def cancel_removal(interaction : discord.Interaction):
            await interaction.response.edit_message(content="Cancelled removal of registration",view=discord.ui.View())
        async def on_confirm(interaction, tournament_name=tournament_name, itx=interaction):
            await remove_player(interaction, tournament_name, itx.user.id, itx.guild.id)

        await interaction.response.send_message(
            f"You are already registered for {tournament_name}. "
            "Would you like to remove your registration?",
            view=ConfirmActionView(
                interaction,
                on_confirm,
                cancel_removal,
            ),
            ephemeral=True,
        )
    else:
        is_tetrio = await db.is_tournament_tetrio(interaction.guild.id, tournament_name)
        await interaction.response.send_modal(RegistrationModal(interaction.guild.id,is_tetrio,tournament_name, title=f"Register for {tournament_name}"))



class RegistrationModal(discord.ui.Modal):
    def __init__(self, guild_id, is_tetrio, tournament_name, *, title="", timeout=None, custom_id="r_modal"):
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)
        self.guild_id = guild_id
        self.is_tetrio = is_tetrio
        self.tournament_name = tournament_name

        label = "Enter your TETR.IO username" if is_tetrio else f"Enter your rating for {tournament_name}"
        self.name = discord.ui.TextInput(label=label)
        self.add_item(self.name)
    
    async def on_submit(self, interaction : discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        
        role_id = await db.get_tournament_role(interaction.guild.id, self.tournament_name)
        if not role_id:
            await interaction.response.send_message("Error in registration: No role associated with this tournament. Please contact staff", ephemeral=True)
            return
        
        name_input = self.name.value
        if not self.is_tetrio:
            await db.insert_into_tournament(interaction.user.id,interaction.user.name,interaction.guild.id,self.tournament_name,float(name_input))
            await add_role(interaction.guild.id, interaction.user.id, role_id)
            await interaction.response.send_message(f"Successfully registered for {self.tournament_name} with rating {name_input}",ephemeral=True)
            await log(interaction.guild.id,f"Player {interaction.user.name} registered for {self.tournament_name} with rating {name_input}")
            await update_tournament_status(interaction.guild.id)
        else: 
            t_data = await tetrio.get_player_data(self.name.value)
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
                        if(caps[0] is not None and peak_rank > tetrio.ranks[caps[0]]):
                            await interaction.response.send_message("Registration Failed. Your peak rank is too low to play in this tournament", ephemeral=True)
                        elif(caps[1] is not None and peak_rank < tetrio.ranks[caps[1]]):
                            await interaction.response.send_message("Registration Failed. Your peak rank is too high to play in this tournament", ephemeral=True)
                        else:
                            username = await tetrio.get_player_id(self.name.value)
                            rating = t_data["data"]["tr"]
                            await db.insert_into_tournament(interaction.user.id,interaction.user.name,interaction.guild.id,self.tournament_name,rating,username)
                            await interaction.response.send_message(f"Successfully registered for {self.tournament_name} under username {name_input}",ephemeral=True)
                            await add_role(interaction.guild.id, interaction.user.id, role_id)
                            await log(interaction.guild.id,f"Player {interaction.user.name} registered for {self.tournament_name} under username {name_input} with rating {rating}")
                            await update_tournament_status(interaction.guild.id)
                else: 
                    username = await tetrio.get_player_id(self.name.value)
                    rating = t_data["data"]["tr"]
                    await db.insert_into_tournament(interaction.user.id,interaction.user.name,interaction.guild.id,self.tournament_name,rating,username)
                    await interaction.response.send_message(f"Successfully registered for {self.tournament_name} under username {name_input}",ephemeral=True)
                    await add_role(interaction.guild.id, interaction.user.id, role_id)
                    await log(interaction.guild.id,f"Player {interaction.user.name} registered for {self.tournament_name} under username {name_input} with rating {rating}")
                    await update_tournament_status(interaction.guild.id)

class RegistrationView(discord.ui.View):
    def __init__(self, guild_id, tournaments, *, timeout = None):
        super().__init__(timeout=timeout)
        for i in tournaments:
            button = discord.ui.Button(label=i)
            button.custom_id = f"{guild_id}-{i}"
            button.callback = lambda interaction, i=i: register_for_tournament(interaction, i)
            self.add_item(button)

        
    


@bot.tree.command(
        name="create_tournament_generic",
        description="Create a generic tournament for your server",
)
@has_permissions(manage_roles=True)
async def create_tournament_generic(interaction : discord.Interaction, tournament_name : str, thread_channel : discord.TextChannel=None, participant_role : discord.Role=None):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    thread_id = thread_channel.id if thread_channel is not None else None
    participant_id = participant_role.id if participant_role is not None else None
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
    if(tournament_exists):
        await interaction.response.send_message(f"Error in creating tournament. Tournament with name {tournament_name} already exists for this server.")
    else: 
        await db.insert_tournament(tournament_name=tournament_name, guild_id=guild_id, thread_channel=thread_id, participant_role=participant_id)
        res_string = f"Created tournament {tournament_name}.\n"
        if thread_channel is not None:
            res_string += f"Registered thread channel for tournament as <#{thread_channel.id}>\n"
        if participant_role is not None:
            res_string += f"Registered participant role as <@&{participant_role.id}>\n"
        await interaction.response.send_message(res_string)


@bot.tree.command(
        name="create_tournament_tetrio",
        description="Create a tetrio tournament for your server",
)
@has_permissions(manage_roles=True)
@commands.guild_only()
async def create_tournament_tetrio(interaction : discord.Interaction, tournament_name : str, rank_cap : str=None, rank_floor : str=None ,thread_channel : discord.TextChannel=None, participant_role : discord.Role=None):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    thread_id = thread_channel.id if thread_channel is not None else None
    participant_id = participant_role.id if participant_role is not None else None
    rank_cap = rank_cap.lower() if rank_cap is not None else None
    rank_floor = rank_floor.lower() if rank_floor is not None else None
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
    if(tournament_exists):
        await interaction.response.send_message(f"Error in creating tournament. Tournament with name {tournament_name} already exists for this server.")
        return
    if rank_cap is not None:
        if rank_cap not in tetrio.ranks:
            await interaction.response.send_message(f"Error in creating tournament. {rank_cap} is not a valid rank")
            return
    if rank_floor is not None:
        if rank_floor not in tetrio.ranks:
            await interaction.response.send_message(f"Error in creating tournament. {rank_floor} is not a valid rank")
            return
    await db.insert_tournament(tournament_name=tournament_name, guild_id=guild_id, thread_channel=thread_id,participant_role=participant_id, is_tetrio=True, rank_cap=rank_cap ,rank_floor=rank_floor)
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

@bot.tree.command(
        name="get_tournaments",
        description="Get all of the tournaments for your server",
)
@has_permissions(manage_roles=True)
async def get_tournaments(interaction : discord.Interaction):
    tours = await db.get_tournaments_by_server(interaction.guild.id)
    if not os.path.isdir(f"{interaction.guild.id}"):
        os.mkdir(f"{interaction.guild.id}")
    with open(f"{interaction.guild.id}/tournaments.csv","w",newline='') as f:
        writer = csv.writer(f)
        writer.writerows(tours)
    await interaction.response.send_message("Tournaments in this server:", file=discord.File(f"{interaction.guild.id}/tournaments.csv"))

@bot.tree.command(
        name="delete_tournament",
        description="Remove tournament from your server",
)
@has_permissions(manage_roles=True)
async def remove_tournament(interaction : discord.Interaction, tournament_name : str):
    guild_id = interaction.guild.id
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name, guild_id=guild_id)
    if not tournament_exists:
        await interaction.response.send_message(f"Error in deleting tournament. Tournament with name {tournament_name} doos not exist for this server.")
        return
    async def delete_tour(interaction : discord.Interaction, tournament_name : str, guild_id : int):
        await db.remove_tournament(guild_id=guild_id,tournament_name=tournament_name)
        await interaction.response.edit_message(content=f"Deleted tournament {tournament_name}",view=discord.ui.View())
    await interaction.response.send_message(f"Delete tournament {tournament_name}?",view=ConfirmActionView(interaction,confirm_callback=lambda interaction,tournament_name=tournament_name,guild_id=guild_id: delete_tour(interaction=interaction,tournament_name=tournament_name, guild_id=guild_id)))
    interaction.followup
    pass

@bot.tree.command(
        name="open_registration",
        description="open registrations for a tournament",
)
@has_permissions(manage_roles=True)
async def open_registration(interaction : discord.Interaction, tournament_name : str):
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name,guild_id=interaction.guild.id)
    if not tournament_exists:
        await interaction.response.send_message(f"Could not open registrations for tournament {tournament_name} because the tournament does not exist")
        return
    await db.set_tournament_registrations_state(interaction.guild.id, tournament_name,True)
    await interaction.response.send_message(f"Set registrations to open for tournament {tournament_name}. make sure to run /update_registrations to reflect changes")
    

@bot.tree.command(
        name="close_registration",
        description="close registrations for a tournament",
)
@has_permissions(manage_roles=True)
async def close_registration(interaction : discord.Interaction, tournament_name : str):
    tournament_exists = await db.check_if_tournament_exists(tournament_name=tournament_name,guild_id=interaction.guild.id)
    if not tournament_exists:
        await interaction.response.send_message(f"Could not close registrations for tournament {tournament_name} because the tournament does not exist")
        return
    await db.set_tournament_registrations_state(interaction.guild.id, tournament_name,False)
    await interaction.response.send_message(f"Set registrations to closed for tournament {tournament_name}. make sure to run /update_registrations to reflect changes")

@bot.tree.command(
        name="set_thread_channel",
        description="set thread channel for a tournament",
)
@has_permissions(manage_roles=True)
async def set_thread_channel(interaction : discord.Interaction, tournament_name : str, thread_channel : discord.TextChannel):
    pass

@bot.tree.command(
        name="set_registration_channel",
        description="set registration channel for a server. This command will automatically create a registration message",
)
@has_permissions(manage_roles=True)
async def set_registration_channel(interaction : discord.Interaction, registration_channel : discord.TextChannel):
    await db.configure_server_if_not_setup(interaction.guild.id)
    await db.set_registration_channel(interaction.guild.id, registration_channel.id)
    c1 = await registration_channel.send("INFO TEXT")
    c2 = await registration_channel.send("Register for a tournament by clicking one of the below tournaments")
    await db.set_registration_messages(interaction.guild.id, c1.id, c2.id)
    await interaction.response.send_message(f"Configured registration channel for this server as <#{registration_channel.id}>. Make sure to run /update_registrations to get registration buttons")

@bot.tree.command(
        name="set_logging_channel",
        description="set logging channel for a server.",
)
@has_permissions(manage_roles=True)
async def set_logging_channel(interaction : discord.Interaction, logging_channel : discord.TextChannel):
    await db.configure_server_if_not_setup(interaction.guild.id)
    await db.set_logging_channel(interaction.guild.id, logging_channel.id)
    await interaction.response.send_message(f"Configured logging channel for this server as <#{logging_channel.id}>")

@bot.tree.command(
        name="update_registrations",
        description="update registration messages to show new tournaments",
)
@has_permissions(manage_roles=True)
async def update_registrations(interaction : discord.Interaction):
    ids = await db.get_registration_messages_info(interaction.guild.id)
    text_channel = interaction.guild.get_channel(ids[0])
    message = await text_channel.fetch_message(ids[1])
    tournaments = await db.get_open_tournaments(interaction.guild.id)
    bot.add_view(RegistrationView(interaction.guild.id, tournaments),message_id=ids[1])
    await message.edit(content="Register for a tournament by clicking one of the below tournaments",view=RegistrationView(interaction.guild.id, tournaments))
    await interaction.response.send_message(f"Updated the registration message at <#{ids[0]}>")
    await update_tournament_status(interaction.guild.id)

async def update_tournament_status(guild_id : int):
    guild = bot.get_guild(guild_id)
    ids = await db.get_registration_messages_info(guild_id)
    text_channel = guild.get_channel(ids[0])
    message = await text_channel.fetch_message(ids[2])
    tournaments = await db.get_open_tournaments(guild_id)
    content = "### Current Open Tournaments:\n"
    for i in tournaments:
        participant_count = await db.get_participant_count(guild_id,i)
        content += F"{i} - {participant_count} Registrations\n"
    await message.edit(content=content)

@bot.tree.command(
        name="link_bracket",
        description="link a bracket to your tournament. You can link multiple brackets to the same tournament",
)
@has_permissions(manage_roles=True)
async def link_bracket(interaction : discord.Interaction, bracket_url_string : str, tournament_name : str):
    await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June",ephemeral=True)

@bot.tree.command(
        name="unlink_bracket",
        description="unlink a bracket from your tournament.",
)
@has_permissions(manage_roles=True)
async def unlink_bracket(interaction : discord.Interaction, bracket_url_string : str, tournament_name : str):
    await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June",ephemeral=True)

@bot.tree.command(
        name="list_brackets",
        description="list all of the brackets in the server",
)
@has_permissions(manage_roles=True)
async def list_brackets(interaction : discord.Interaction):
    await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June",ephemeral=True)

@bot.tree.command(
        name="activate_bracket",
        description="activate a bracket for challonge polling.",
)
@has_permissions(manage_roles=True)
async def activate_bracket(interaction : discord.Interaction, bracket_url_string : str):
    await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June",ephemeral=True)

@bot.tree.command(
        name="deactivate_bracket",
        description="deactivate a bracket for challonge polling.",
)
@has_permissions(manage_roles=True)
async def deactivate_bracket(interaction : discord.Interaction, bracket_url_string : str):
    await interaction.response.send_message("This feature has not been implemented yet. The developer estimates this feature will be ready in late June",ephemeral=True)

@bot.tree.command(
        name="export_participants",
        description="Export participants from a tournament, sorted by rating.",
)
@has_permissions(manage_roles=True)
async def export_participants(interaction : discord.Interaction, tournament_name : str):
    participants = await db.export_participants_full(interaction.guild.id, tournament_name)
    if not os.path.isdir(f"{interaction.guild.id}"):
        os.mkdir(f"{interaction.guild.id}")
    with open(f"{interaction.guild.id}/participants.csv","w",newline='') as f:
        writer = csv.writer(f)
        writer.writerows(participants)
    await interaction.response.send_message(f"exporting players in {tournament_name}", file=discord.File(f"{interaction.guild.id}/participants.csv"))

@bot.tree.command(
        name="export_seeding_list",
        description="Export participants from a tournament, sorted by rating. Good for importing into a bracket website",
)
@has_permissions(manage_roles=True)
async def export_seeding(interaction : discord.Interaction, tournament_name : str):
    participants = await db.export_participants(interaction.guild.id, tournament_name)
    if not os.path.isdir(f"{interaction.guild.id}"):
        os.mkdir(f"{interaction.guild.id}")
    with open(f"{interaction.guild.id}/participants.csv","w",newline='') as f:
        writer = csv.writer(f)
        writer.writerows(participants)
    await interaction.response.send_message(f"exporting players in {tournament_name}", file=discord.File(f"{interaction.guild.id}/participants.csv"))

@bot.tree.command(
        name="refresh_seeding_tetrio",
        description="refresh seeding for TETR.IO Tournaments.",
)
@has_permissions(manage_roles=True)
async def update_seeding_tetrio(interaction : discord.Interaction, tournament_name : str, remove_ineligible : bool=True):
    participants = await db.get_game_users_from_tournament(interaction.guild.id,tournament_name)
    response = await interaction.response.send_message(f"Updating Player 0 of {len(participants)}")
    for i in range(len(participants)):
        time.sleep(1)
        await interaction.followup.edit_message(response.message_id,content=f"Updating Player {i+1} of {len(participants)}")
        t_data = await tetrio.get_player_data(participants[i])
        if t_data["success"] == False:
            if t_data["error"]["msg"] == "No such user! | Either you mistyped something, or the account no longer exists.":
                continue
            else:
                continue
        elif t_data["data"]["tr"] == -1:
            continue
        elif not remove_ineligible:
            await db.update_rating(interaction.guild.id, tournament_name, participants[i], t_data["data"]["tr"])
            continue
        else:
            caps = await db.get_floor_and_cap(interaction.guild.id, tournament_name)
            if (caps[0] is not None or caps[1] is not None):
                if t_data["data"]["rank"] == "z":
                    player_data = await db.get_discord_user_from_game_username(interaction.guild.id, tournament_name,participants[i])
                    await interaction.followup.send(f"Player <@{player_data[0]}> ({player_data[0]}) was removed from the tournament due to ineligibility (unranked)")
                    role = await db.get_tournament_role(interaction.guild.id, tournament_name)
                    await remove_role(interaction.guild.id, interaction.user.id, role)
                    await db.remove_from_tournament(interaction.guild.id, player_data[0], tournament_name)
                    await update_tournament_status(interaction.guild.id)
                else:
                    peak_rank = tetrio.ranks[t_data["data"]["bestrank"]]
                    if t_data["data"]["past"] is not None:
                        for ii in t_data["data"]["past"]:
                            if t_data["data"]["past"][ii]["bestrank"] is not None:
                                peak_rank = min(peak_rank, tetrio.ranks[t_data["data"]["past"][ii]["bestrank"]])
                    if(caps[0] is not None and peak_rank > tetrio.ranks[caps[0]]):
                        player_data = await db.get_discord_user_from_game_username(interaction.guild.id, tournament_name,participants[i])
                        await interaction.followup.send(f"Player <@{player_data[0]}> ({player_data[0]}) was removed from the tournament due to ineligibility (below rank floor)")
                        role = await db.get_tournament_role(interaction.guild.id, tournament_name)
                        await remove_role(interaction.guild.id, interaction.user.id, role)
                        await db.remove_from_tournament(interaction.guild.id, player_data[0], tournament_name)
                        await update_tournament_status(interaction.guild.id)
                    elif(caps[1] is not None and peak_rank < tetrio.ranks[caps[1]]):
                        player_data = await db.get_discord_user_from_game_username(interaction.guild.id, tournament_name,participants[i])
                        await interaction.followup.send(f"Player <@{player_data[0]}> ({player_data[0]}) was removed from the tournament due to ineligibility (above rank cap)")
                        role = await db.get_tournament_role(interaction.guild.id, tournament_name)
                        await remove_role(interaction.guild.id, interaction.user.id, role)
                        await db.remove_from_tournament(interaction.guild.id, player_data[0], tournament_name)
                        await update_tournament_status(interaction.guild.id)
                    else:
                        await db.update_rating(interaction.guild.id, tournament_name, participants[i], t_data["data"]["tr"])
    await interaction.followup.edit_message(response.message_id,content=f"Finished updating player ratings")
                    
@bot.tree.command(
        name="get_checkins",
        description="get a list of checked in players. Good for importing into a bracket website ",
)
@has_permissions(manage_roles=True)
async def get_checkins(interaction : discord.Interaction, tournament_name : str, checkin_channel : discord.TextChannel, checkin_message : str):
    checkin_message = int(checkin_message)
    message = await checkin_channel.fetch_message(checkin_message)
    if message is None:
        await interaction.response.send_message("Error in finding message, checkin message appears to be invalid")
        return
    reactions = message.reactions
    checkin_ids = set()
    for i in reactions:
        users = [ user async for user in i.users() ]
        for ii in users:
            print(ii.id)
            checkin_ids.add(ii.id)
    data = await db.export_participants_if_in_set(interaction.guild.id, tournament_name, checkin_ids)
    if not os.path.isdir(f"{interaction.guild.id}"):
        os.mkdir(f"{interaction.guild.id}")
    with open(f"{interaction.guild.id}/checkin.csv","w",newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    await interaction.response.send_message(f"exporting checked in players in {tournament_name}", file=discord.File(f"{interaction.guild.id}/checkin.csv"))


@bot.tree.command(
        name="view_player_counts",
        description="Get player counts for all tournaments in the server.",
)
@has_permissions(manage_roles=True)
async def get_player_counts(interaction : discord.Interaction):
    counts = await db.get_participant_counts(interaction.guild.id)
    if not os.path.isdir(f"{interaction.guild.id}"):
        os.mkdir(f"{interaction.guild.id}")
    with open(f"{interaction.guild.id}/participant_counts.csv","w",newline='') as f:
        writer = csv.writer(f)
        writer.writerows(counts)
    await interaction.response.send_message("Player counts for tournaments in this server:", file=discord.File(f"{interaction.guild.id}/participant_counts.csv"))

@bot.tree.command(
        name="manual_register",
        description="Manually register a player to your tournament.",
)
@has_permissions(manage_roles=True)
async def manual_register(interaction : discord.Interaction, tournament_name : str, player : discord.User, registration_input : str, override_requirements : bool=False):
    player_id = player.id
    input = registration_input
    is_tetrio = await db.is_tournament_tetrio(interaction.guild.id, tournament_name)
    username = player.name
    
    if username is None:
        interaction.response.send_message("Error: invalid player ID set")
        return
    truth = await db.check_if_tournament_exists(tournament_name,interaction.guild.id)
    if not truth: 
        await interaction.response.send_message("Error: Tournament does not exist")
        return
    truth = await db.check_if_player_registered_for_tournament(interaction.guild.id,player.id,tournament_name)
    if truth: 
        await interaction.response.send_message("Error: Player already registered for tournament")
        return
    if not is_tetrio:
        await db.insert_into_tournament(player_id,username,interaction.guild.id,tournament_name,input)
        role = await db.get_tournament_role(interaction.guild.id, tournament_name)
        await add_role(interaction.guild.id, player_id, role)
        await interaction.response.send_message(f"Successfully registered {player.name} for {tournament_name} with rating {input}",ephemeral=True)
        await log(interaction.guild.id,f"Player {player.name} manually registered for {tournament_name} with rating {input}")
        await update_tournament_status(interaction.guild_id)
    else: 
        t_data = await tetrio.get_player_data(input)
        if t_data["success"] == False:
            if t_data["error"]["msg"] == "No such user! | Either you mistyped something, or the account no longer exists.":
                await interaction.response.send_message("Registration Failed: No such user! | Either you mistyped something, or the account no longer exists.", ephemeral=True)
            else:
                await interaction.response.send_message("Registration Failed: An unknown error occured. Please contact staff", ephemeral=True)
        elif override_requirements:
            username = await tetrio.get_player_id(input)
            rating = t_data["data"]["tr"]
            await db.insert_into_tournament(player_id,username,interaction.guild.id,tournament_name,rating,username)
            await interaction.response.send_message(f"Successfully manually registered {player.name} for {tournament_name} under username {input}")
            role = await db.get_tournament_role(interaction.guild.id, tournament_name)
            await add_role(interaction.guild.id, player_id, role)
            await log(interaction.guild.id,f"Player {player.name} registered for {tournament_name} under username {input} with rating {rating}")
            await update_tournament_status(interaction.guild_id)
        elif t_data["data"]["tr"] == -1:
            await interaction.response.send_message("Registration Failed: They must have a TR on TETR.IO to register for the tournament", ephemeral=True)
        else:
            caps = await db.get_floor_and_cap(interaction.guild.id, tournament_name)
            if (caps[0] is not None or caps[1] is not None):
                if t_data["data"]["rank"] == "z":
                    await interaction.response.send_message("Registration Failed: They must have a letter rank in order to play in a capped or floored tournament", ephemeral=True)
                else:
                    peak_rank = tetrio.ranks[t_data["data"]["bestrank"]]
                    if t_data["data"]["past"] is not None:
                        for i in t_data["data"]["past"]:
                            if t_data["data"]["past"][i]["bestrank"] is not None:
                                peak_rank = min(peak_rank, tetrio.ranks[t_data["data"]["past"][i]["bestrank"]])
                    if(caps[0] is not None and peak_rank > tetrio.ranks[caps[0]]):
                        await interaction.response.send_message("Registration Failed. Their peak rank is too low to play in this tournament")
                    elif(caps[1] is not None and peak_rank < tetrio.ranks[caps[1]]):
                        await interaction.response.send_message("Registration Failed. Their peak rank is too high to play in this tournament")
                    else:
                        username = await tetrio.get_player_id(input)
                        rating = t_data["data"]["tr"]
                        print(player)
                        await db.insert_into_tournament(player_id,player.name,interaction.guild.id,tournament_name,rating,username)
                        await interaction.response.send_message(f"Successfully manually registered {player.name} for {tournament_name} under username {input}")
                        role = await db.get_tournament_role(interaction.guild.id, tournament_name)
                        await add_role(interaction.guild.id, player_id, role)
                        await log(interaction.guild.id,f"Player {player.name} registered for {tournament_name} under username {input} with rating {rating}")
                        await update_tournament_status(interaction.guild_id)


@bot.tree.command(
        name="manual_unregister",
        description="Manually unregister a player to your tournament.",
)
@has_permissions(manage_roles=True)
async def manual_unregister(interaction : discord.Interaction, tournament_name : str, player : discord.User):
    player_id = player.id
    await db.remove_from_tournament(interaction.guild.id,player_id,tournament_name)
    await interaction.response.send_message(content=f"Removed registration from {tournament_name} from <@{player_id}> if they were registered")
    await update_tournament_status(interaction.guild_id)
    role = await db.get_tournament_role(interaction.guild.id, tournament_name)
    await remove_role(interaction.guild.id, interaction.user.id, role)




#TODO: Implement routine to check all open brackets and see if they are able to be closed. If so, send a warning to the server's logging channel reminding them to close tournaments once they are finished.
#TODO: Implement routine to add new updated threads to the queue
#TODO: Implement routine to publish threads from the queue


@bot.tree.command(
        name="admin_update_bracket_cap",
        description="ADMIN ONLY",
        guild=discord.Object(id=345648584907030539),
)
@checks.has_role(350379931978432513)
async def update_bracket_cap(interaction : discord.Interaction,server_id:int, limit : int):
    if(interaction.user.id == 317475187391987713):
        pass
@bot.tree.command(
        name="admin_execute_dql",
        description="ADMIN ONLY",
        guild=discord.Object(id=345648584907030539),
)
@checks.has_role(350379931978432513)
async def execute_dql(interaction : discord.Interaction,sql:str):
    if(interaction.user.id == 317475187391987713):
        await db.execute_dql(sql)
        await interaction.response.send_message("Executed DQL Query",file=discord.File("return.csv"))
@bot.tree.command(
        name="admin_execute_dml",
        description="ADMIN ONLY",
        guild=discord.Object(id=345648584907030539),
)
@checks.has_role(350379931978432513)
async def execute_dml(interaction : discord.Interaction,sql:str):
    if(interaction.user.id == 317475187391987713):
        await db.execute_dml(sql)
        await interaction.response.send_message("Executed DML query")

async def register_previous_views():
    guilds = await db.get_guilds()
    for i in guilds:
        tours = await db.get_open_tournaments(i)
        m_id = await db.get_registration_messages_info(i)
        bot.add_view(RegistrationView(i,tours),message_id=m_id[1])


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        exit(1)
    bot.run(TOKEN)