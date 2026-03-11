from typing import Optional

import discord
import db


async def get_channel(bot, guild_id: int, channel_id: int) -> Optional[discord.TextChannel]:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None
    channel = guild.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return None
    return channel


async def log(bot, guild_id: int, msg: str) -> None:
    channel_id = await db.get_logging_channel(guild_id)
    if not channel_id:
        return

    channel = await get_channel(bot, guild_id, channel_id)
    if not channel:
        return
    await channel.send(content=msg)


async def add_role(guild: discord.Guild, user_id: int, role_id: int) -> None:
    if not (member := guild.get_member(user_id)):
        return
    if not (role := guild.get_role(role_id)):
        return
    await member.add_roles(role)


async def remove_role(guild: discord.Guild, user_id: int, role_id: int) -> None:
    if not (member := guild.get_member(user_id)):
        return
    if not (role := guild.get_role(role_id)):
        return
    await member.remove_roles(role)


async def update_tournament_status(bot, guild_id: int) -> None:
    guild = bot.get_guild(guild_id)
    assert guild is not None
    ids = await db.get_registration_messages_info(guild_id)
    text_channel = guild.get_channel(ids[0])
    assert isinstance(text_channel, discord.TextChannel)
    message = await text_channel.fetch_message(ids[2])
    tournaments = await db.get_open_tournaments(guild_id)
    content = "### Current Open Tournaments:\n"
    for i in tournaments:
        participant_count = await db.get_participant_count(guild_id, i)
        content += f"{i} - {participant_count} Registrations\n"
    await message.edit(content=content)


class ConfirmActionView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, confirm_callback=None, abort_callback=None, *, timeout=180):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.responded = False

        confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.success)
        abort_button = discord.ui.Button(label="Abort", style=discord.ButtonStyle.danger)

        confirm_button.callback = confirm_callback if confirm_callback is not None else self._default_confirm_callback
        abort_button.callback = abort_callback if abort_callback is not None else self._default_abort_callback

        self.add_item(confirm_button)
        self.add_item(abort_button)

    async def _default_confirm_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="You clicked the confirm button, but no implementation was provided. This is an error message. Please report this error to the developer",
            view=discord.ui.View()
        )

    async def _default_abort_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Aborted operation", view=discord.ui.View())

    async def interaction_check(self, interaction: discord.Interaction):
        self.responded = True
        return True

    async def on_timeout(self):
        if not self.responded:
            await self.interaction.followup.send(
                content="This action has timed out. If you would like to try again, please enter the command again",
                view=discord.ui.View(),
                ephemeral=True
            )
