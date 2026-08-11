from __future__ import annotations

import json
import os
from datetime import datetime,timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

DATA_PATH = os.path.join("data","name_tracker.json")


#---------------------------Persistence Layer---------------------------#

def _default_guild_data() -> dict:
    return {
        "names": {},
        "allowed_roles" : [],
        "monitor_channel" : None,
    }

class NameTrackerStore:

    def __init__(self,path: str = DATA_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._data: dict[str,dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, "r",encoding="utf-8") as f:
                try:
                    self._data = json.load(f)
                except json.decoder.JSONDecodeError:
                    self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        with open(self.path, "w",encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def guild(self,guild_id : int) -> dict:
        key = str(guild_id)
        if key not in self.data:
            self._data[key] = _default_guild_data()
            self._save()
        return self._data[key]

#---------------------------Listing---------------------------#

    def record_name(self, guild_id: int,name : str, user_id: int) -> tuple[dict,bool]:
        g = self.guild(guild_id)
        key = name.strip().lower()
        was_new = key not in g["names"]
        entry = g["names"].get(key, {"count":0,"display_name":name.strip()})
        entry["count"] += 1
        entry["display_name"] = name.strip()
        entry["last_recorded"] = datetime.now(timezone.utc).isoformat()
        entry["recorded_by"] = user_id
        g["names"][key] = entry
        self._save()
        return entry,was_new

    def remove_name(self, guild_id: int,name : str) -> bool:
        g = self.guild(guild_id)
        key = name.strip().lower()
        if key in g["names"]:
            del g["names"][key]
            self._save()
            return True
        return False

    def list_names(self,guild_id: int) -> dict:
        g = self.guild(guild_id)["names"]


#---------------------------Settings---------------------------#

    def set_monitor_channel(self, guild_id: int, channel_id: Optional[int]) -> None:
        g = self.guild(guild_id)
        g["monitor_channel"] = channel_id
        self._save()

    def get_monitor_channel(self,guild_id: int, role_id: int) -> bool:
        g = self.guild(guild_id)
        if role_id in g["allowed_roles"]:
            return False
        g["allowed_roles"].append(role_id)
        self._save()
        return True

    def get_allowed_roles(self,guild_id: int) -> list[int]:
        return self.guild(guild_id)["allowed_roles"]

store = NameTrackerStore()

#---------------------------Permission---------------------------#
def has_tracker_access(interaction: discord.Interaction) -> bool:
    if interaction.guild is None or not isinstance(interaction.user,discord.Member):
        return False

    member = interaction.user
    if member.guild_permissions.administrator:
        return True

    allowed_role_ids = store.get_allowed_roles(interaction.guild.id)
    if not allowed_role_ids:
        return False

    member_role_ids = {r.id for r in member.roles}
    return not member_role_ids.isdisjoint(allowed_role_ids)

def tracker_access_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not has_tracker_access(interaction):
            raise app_commands.CheckFailure(
                "Don't have role, don't use this"
            )
        return True
    return app_commands.check(predicate)

def in_monitor_channel(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return True
    monitor_id = store.get_monitor_channel(interaction.guild.id)
    if monitor_id is None:
        return True
    return interaction.channel_id == monitor_id

def monitor_channel_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not in_monitor_channel(interaction):
            channel_id = store.get_monitor_channel(interaction.guild.id)
            raise app_commands.CheckFailure(
                f"This command only works in <#{channel_id}>>"
            )

        return True
    return app_commands.check(predicate)
#---------------------------Configurations---------------------------#
class NameTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self,message:discord.Message):

        if message.author.bot or message.guild is None:
            return
        monitor_id = store.get_monitor_channel(message.guild.id)
        if monitor_id is not None and message.channel.id != monitor_id:
            return #dont read outside chat
        #More passive commands (future)

#---------------------------Configurations---------------------------#
    @app_commands.command(name='record',description='Record a channel to the checklist')
    @app_commands.describe(name='The channel Name?')
    @tracker_access_check()
    @monitor_channel_check()
    async def record(self,interaction:discord.Interaction,name:str):
        entry, was_new = store.record_name(interaction.guild.id, interaction.user.id)
        ts = datetime.fromisoformat(entry["last_recorded"])

        embed = discord.Embed(
            title="Room assigned" if was_new else "Room assigned already",
            description=f"{entry['display_name']}",
            color = discord.Color.green() if was_new else discord.Color.purple()
        )
        embed.add_field(name="Times recorded",value =str(entry["count"]),inline=True)
        embed.add_field(
            name = "Last recorded",
            value= discord.utils.format_dt(ts, style="R"),
            inline = True
        )
        embed.set_footer(text=f"Recorded by {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed)

#---------------------------Reemoval---------------------------#
    @app_commands.command(name="remove", description="Remove a name from the checklist.")
    @app_commands.describe(name="The name to remove")
    @tracker_access_check()
    @monitor_channel_check()
    async def remove(self, interaction: discord.Interaction, name: str):
        removed = store.remove_name(interaction.guild.id, name)
        if removed:
            await interaction.response.send_message(f"🗑️ Removed **{name}** from the checklist.")
        else:
            await interaction.response.send_message(
                f"⚠️ Couldn't find **{name}** on the checklist.", ephemeral=True
            )


    @remove.autocomplete("name")
    async def remove_autocomplete(self, interaction: discord.Interaction, current: str):
        names = store.list_names(interaction.guild.id) if interaction.guild else {}
        matches = [
            entry["display_name"]
            for key, entry in names.items()
            if current.lower() in key
        ]
        return [app_commands.Choice(name=n, value=n) for n in matches[:25]]


# -- /checklist --------------------------------------------------------------

    @app_commands.command(name="checklist", description="View the recorded names checklist.")
    @monitor_channel_check()
    async def checklist(self, interaction: discord.Interaction):
        names = store.list_names(interaction.guild.id)
        if not names:
            await interaction.response.send_message("The checklist is empty.")
            return

        # Sort by most recently recorded first
        sorted_entries = sorted(
            names.values(), key=lambda e: e["last_recorded"], reverse=True
        )

        embed = discord.Embed(title="📋 Name Checklist", color=discord.Color.gold())
        lines = []
        for entry in sorted_entries[:25]:
            ts = datetime.fromisoformat(entry["last_recorded"])
            lines.append(
                f"**{entry['display_name']}** — x{entry['count']} "
                f"(last: {discord.utils.format_dt(ts, style='R')})"
            )
        embed.description = "\n".join(lines)
        if len(sorted_entries) > 25:
            embed.set_footer(text=f"Showing 25 of {len(sorted_entries)} names.")
        await interaction.response.send_message(embed=embed)


# -- /settings (hybrid: works as slash AND normal prefix command) -------------

    settings_group = app_commands.Group(
        name="settings", description="Admin settings for the name tracker."
    )


    @settings_group.command(name="channel", description="Set which channel the bot reads/responds in.")
    @app_commands.describe(channel="Leave empty to clear the restriction (bot works everywhere).")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings_channel_slash(
            self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None
    ):
        store.set_monitor_channel(interaction.guild.id, channel.id if channel else None)
        if channel:
            await interaction.response.send_message(f"✅ Bot is now restricted to {channel.mention}.")
        else:
            await interaction.response.send_message("✅ Channel restriction cleared — bot works in all channels.")


    @settings_group.command(name="view", description="View current name-tracker settings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings_view(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        channel_id = store.get_monitor_channel(guild_id)
        role_ids = store.get_allowed_roles(guild_id)

        channel_txt = f"<#{channel_id}>" if channel_id else "Any channel"
        roles_txt = ", ".join(f"<@&{r}>" for r in role_ids) if role_ids else "Admins only"

        embed = discord.Embed(title="⚙️ Name Tracker Settings", color=discord.Color.blurple())
        embed.add_field(name="Monitored channel", value=channel_txt, inline=False)
        embed.add_field(name="Roles with access", value=roles_txt, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


    role_group = app_commands.Group(
        name="role", description="Manage which roles can use /record and /remove.", parent=settings_group
    )


    @role_group.command(name="add", description="Allow a role to use /record and /remove.")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings_role_add(self, interaction: discord.Interaction, role: discord.Role):
        added = store.add_allowed_role(interaction.guild.id, role.id)
        if added:
            await interaction.response.send_message(f"✅ {role.mention} can now use /record and /remove.")
        else:
            await interaction.response.send_message(f"{role.mention} already has access.", ephemeral=True)


    @role_group.command(name="remove", description="Revoke a role's access to /record and /remove.")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings_role_remove(self, interaction: discord.Interaction, role: discord.Role):
        removed = store.remove_allowed_role(interaction.guild.id, role.id)
        if removed:
            await interaction.response.send_message(f"🗑️ Removed access for {role.mention}.")
        else:
            await interaction.response.send_message(f"{role.mention} didn't have access.", ephemeral=True)


# -- Normal (prefix) version of the settings-channel command -----------------
# e.g. "!settings-channel #general" typed as plain text. Requires
# commands.Bot(..., command_prefix="!") and message_content intent enabled.

    @commands.command(name="settings-channel")
    @commands.has_permissions(administrator=True)
    async def settings_channel_prefix(
            self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ):
        store.set_monitor_channel(ctx.guild.id, channel.id if channel else None)
        if channel:
            await ctx.send(f"✅ Bot is now restricted to {channel.mention}.")
        else:
            await ctx.send("✅ Channel restriction cleared — bot works in all channels.")


# -- Error handling ------------------------------------------------------

    @record.error
    @remove.error
    @checklist.error
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        if not interaction.response.is_done():
            await interaction.response.send_message(str(error) or "You can't use this here.", ephemeral=True)
        return
    raise error


    @settings_channel_prefix.error
    async def on_prefix_settings_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⚠️ You need Administrator permission to use this.")
            return
    raise error


async def setup(bot: commands.Bot):
    cog = NameTracker(bot)
    bot.tree.add_command(cog.settings_group)
    await bot.add_cog(cog)



