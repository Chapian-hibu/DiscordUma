import json
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone


DATA_DIR = "data/thread_tracker"
os.makedirs(DATA_DIR, exist_ok=True)

# Discord archive duration in minutes
ARCHIVE_DURATION = {60, 1440, 4320, 10080}

STAGE_THRESHOLDS = {
    1: 0.50,
    2: 0.75,
    3: 0.90,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


class GuildThreadStore:
    # Handles load/save of a single guild's thread_tracker.json
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.path = os.path.join(DATA_DIR, f"{guild_id}.json")
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"threads": {}, "settings": {}}

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:  # was "r" -> fixed to "w"
            json.dump(self.data, f, indent=2)

    # Accessors
    def get_thread(self, thread_id: int) -> dict | None:
        return self.data["threads"].get(str(thread_id))

    def set_thread(self, thread_id: int, entry: dict):
        self.data["threads"][str(thread_id)] = entry
        self.save()

    def delete_thread(self, thread_id: int):
        self.data["threads"].pop(str(thread_id), None)
        self.save()

    def all_threads(self) -> dict:
        return self.data["threads"]

    def get_setting(self, key: str, default=None):
        return self.data["settings"].get(key, default)

    def set_setting(self, key: str, value):
        self.data["settings"][key] = value
        self.save()


class ThreadTracker(commands.Cog):  # was missing commands.Cog inheritance -> fixed

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stores: dict[int, GuildThreadStore] = {}
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    # Store helper
    def get_store(self, guild_id: int) -> GuildThreadStore:
        if guild_id not in self.stores:
            self.stores[guild_id] = GuildThreadStore(guild_id)
        return self.stores[guild_id]

    # Slash command group
    thread_group = app_commands.Group(
        name="thread", description="Threads tracking and reminders"
    )

    @thread_group.command(name="track", description="Start tracking this thread for archive reminders")
    async def track(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "This command only works inside a thread", ephemeral=True
            )
            return

        store = self.get_store(interaction.guild_id)
        duration = thread.auto_archive_duration or 1440

        entry = {
            "channel_id": thread.parent_id,
            "created_at": _iso(_now()),
            "last_activity": _iso(_now()),
            "archive_duration_minutes": duration,
            "participants": [],
            "last_poster": None,
            "awaiting": [],
            "reminder_stage": 0,
            "status": "active",
            "snooze_until": None,
            "word_count_total": 0,
        }

        store.set_thread(thread.id, entry)
        await interaction.response.send_message(
            f"Now tracking **{thread.name}** "
            f"(archives after {duration} minutes of inactivity)",
            ephemeral=True,  # was "empheral" -> fixed
        )

    @thread_group.command(name="untrack", description="Stop tracking this thread")
    async def untrack(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "This command only works inside a thread", ephemeral=True
            )
            return
        store = self.get_store(interaction.guild_id)
        store.delete_thread(thread.id)
        await interaction.response.send_message(
            f"Stopped tracking **{thread.name}**", ephemeral=True
        )

    @thread_group.command(name="snooze", description="Snooze reminders for this thread")
    @app_commands.describe(days="Number of days to snooze")  # was "reason" -> fixed to match param name
    async def snooze(self, interaction: discord.Interaction, days: int):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "This command only works inside a thread", ephemeral=True
            )
            return
        store = self.get_store(interaction.guild_id)
        entry = store.get_thread(thread.id)
        if entry is None:
            await interaction.response.send_message(
                "Thread isn't being tracked. Use /thread track first", ephemeral=True
            )
            return
        entry["status"] = "snoozed"
        entry["snooze_until"] = _iso(_now() + timedelta(days=days))
        store.set_thread(thread.id, entry)
        await interaction.response.send_message(
            f"Reminders snoozed for **{days}** day(s)", ephemeral=True
        )

    @thread_group.command(name="pause", description="Pause reminders for this thread")  # was "Pause" (uppercase) -> fixed
    async def pause(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "This command only works inside a thread.", ephemeral=True
            )
            return

        store = self.get_store(interaction.guild_id)
        entry = store.get_thread(thread.id)
        if entry is None:
            await interaction.response.send_message(
                "This thread isn't being tracked.", ephemeral=True
            )
            return

        entry["status"] = "paused"
        store.set_thread(thread.id, entry)
        await interaction.response.send_message("Reminders paused for this thread.", ephemeral=True)

    @thread_group.command(name="resume", description="Resume reminders for a paused/snoozed thread")
    async def resume(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "This command only works inside a thread.", ephemeral=True
            )
            return

        store = self.get_store(interaction.guild_id)
        entry = store.get_thread(thread.id)
        if entry is None:
            await interaction.response.send_message(
                "This thread isn't being tracked.", ephemeral=True
            )
            return

        entry["status"] = "active"
        entry["snooze_until"] = None
        entry["reminder_stage"] = 0
        entry["last_activity"] = _iso(_now())
        store.set_thread(thread.id, entry)
        await interaction.response.send_message("Reminders resumed for this thread.", ephemeral=True)

    @thread_group.command(name="status", description="Show all tracked threads and their urgency (GM/mod)")
    @app_commands.checks.has_permissions(manage_threads=True)
    async def status(self, interaction: discord.Interaction):
        store = self.get_store(interaction.guild_id)
        threads = store.all_threads()
        if not threads:
            await interaction.response.send_message("No threads are currently tracked.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Tracked threads",
            color=discord.Color.blurple(),
        )
        # Build the full embed across ALL threads first, THEN send once.
        # (previously this sent/returned inside the loop after the first thread)
        for thread_id, entry in threads.items():
            icon = self._status_icon(entry)
            channel = self.bot.get_channel(int(thread_id))
            name = channel.name if channel else f"Unknown ({thread_id})"
            awaiting = ", ".join(f"<@{u}>" for u in entry.get("awaiting", [])) or "-"
            embed.add_field(
                name=f"{icon} {name}",
                value=f"Status: `{entry['status']}` — Awaiting: {awaiting}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    def _status_icon(entry: dict) -> str:
        if entry["status"] in ("paused", "snoozed"):
            return "⏸️"
        stage = entry.get("reminder_stage", 0)
        if stage >= 3:
            return "🔴"
        if stage >= 2:
            return "🟡"
        return "🟢"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not isinstance(message.channel, discord.Thread):
            return

        store = self.get_store(message.guild.id)
        entry = store.get_thread(message.channel.id)
        if entry is None:
            return

        uid = str(message.author.id)
        if uid not in entry["participants"]:
            entry["participants"].append(uid)

        entry["last_activity"] = _iso(_now())
        entry["last_poster"] = uid
        entry["awaiting"] = [p for p in entry["participants"] if p != uid]
        entry["reminder_stage"] = 0
        entry["status"] = "active"
        entry["word_count_total"] = entry.get("word_count_total", 0) + len(message.content.split())

        store.set_thread(message.channel.id, entry)

    # --- background reminder loop -------------------------------------------

    @tasks.loop(minutes=30)
    async def reminder_loop(self):
        for guild in self.bot.guilds:
            store = self.get_store(guild.id)
            threads = store.all_threads()
            for thread_id_str, entry in list(threads.items()):
                await self._check_thread(guild, store, int(thread_id_str), entry)

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    async def _check_thread(self, guild: discord.Guild, store: GuildThreadStore, thread_id: int, entry: dict):
        if entry["status"] == "paused":
            return

        if entry["status"] == "snoozed":
            if entry["snooze_until"] and _now() < _parse(entry["snooze_until"]):
                return
            entry["status"] = "active"

        thread = guild.get_thread(thread_id)
        if thread is None:
            return  # deleted or inaccessible

        duration_min = entry["archive_duration_minutes"]
        last_activity = _parse(entry["last_activity"])
        elapsed_min = (_now() - last_activity).total_seconds() / 60
        fraction = elapsed_min / duration_min if duration_min else 0

        stage = entry.get("reminder_stage", 0)

        if fraction >= STAGE_THRESHOLDS[3] and stage < 3:
            await self._send_reminder(thread, entry, stage=3, store=store, thread_id=thread_id)
        elif fraction >= STAGE_THRESHOLDS[2] and stage < 2:
            await self._send_reminder(thread, entry, stage=2, store=store, thread_id=thread_id)
        elif fraction >= STAGE_THRESHOLDS[1] and stage < 1:
            entry["reminder_stage"] = 1
            store.set_thread(thread_id, entry)

    async def _send_reminder(self, thread: discord.Thread, entry: dict, stage: int, store: GuildThreadStore,
                              thread_id: int):
        awaiting = entry.get("awaiting", [])
        mentions = " ".join(f"<@{u}>" for u in awaiting) if awaiting else "everyone"

        if stage == 2:
            msg = f"This scene's been quiet for a bit — {mentions}, still in it?"
        else:  # stage 3
            msg = f"⚠️ **{mentions}** — this thread is close to archiving. Reply to keep it active."

        try:
            await thread.send(msg)
        except discord.Forbidden:
            pass

        entry["reminder_stage"] = stage
        store.set_thread(thread_id, entry)

        if stage == 3:
            gm_channel_id = store.get_setting("gm_notify_channel_id")
            if gm_channel_id:
                gm_channel = self.bot.get_channel(gm_channel_id)
                if gm_channel:
                    try:
                        await gm_channel.send(
                            f"🔴 Thread **#{thread.name}** is about to archive. "
                            f"Still waiting on: {mentions}"
                        )
                    except discord.Forbidden:
                        pass

    # --- auto-unarchive with recap -------------------------------------------

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if before.archived and not after.archived:
            store = self.get_store(after.guild.id)
            entry = store.get_thread(after.id)
            if entry is None:
                return

            entry["status"] = "active"
            entry["reminder_stage"] = 0
            store.set_thread(after.id, entry)

            try:
                dormant_since = _parse(entry["last_activity"])
                days_dormant = (_now() - dormant_since).days
                embed = discord.Embed(
                    title="Welcome back",
                    description=f"This thread was dormant for **{days_dormant} day(s)**.",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Total words so far",
                    value=str(entry.get("word_count_total", 0)),
                    inline=True,
                )
                await after.send(embed=embed)
            except discord.Forbidden:
                pass

    # --- config command --------------------------------------------------------

    @thread_group.command(name="config", description="Set the GM notification channel for archive warnings")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config(self, interaction: discord.Interaction, channel: discord.TextChannel):
        store = self.get_store(interaction.guild_id)
        store.set_setting("gm_notify_channel_id", channel.id)
        await interaction.response.send_message(
            f"GM notifications will be sent to {channel.mention}.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ThreadTracker(bot))