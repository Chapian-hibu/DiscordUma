import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone

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

class ThreadStore:  # was missing commands.Cog inheritance -> fixed
    def __init__(self,db):
        self.threads = db["thread"]
        self.settings = db["guild_settings"]

    #--------------------Thread entries-------------------------#
    async def get_thread(self, thread_id: int) -> dict|None:
        return await self.threads.find_one({"_id": thread_id})

    async def set_thread(self,thread_id:int,guild_id:int,entry:dict):
        doc = dict(entry)
        doc["_id"] = str(thread_id)
        doc["guild_id"] = guild_id
        await self.threads.replace_one({"_id": str(thread_id)},
                                       doc,
                                       upsert=True)

    async def delete_thread(self,thread_id:int):
        await self.threads.delete_one({"_id": str(thread_id)})

    async def all_threads(self,guild_id:int)->list[dict]:
        cursor = self.threads.find({"guild_id": guild_id})
        return await cursor.to_list(length=None)

    #----------------------Guild settings------------------------#
    async def get_setting(self,guild_id: int,key:str,default = None):
        doc = await self.settings.find_one({"_id":str(guild_id)})
        if doc is None:
            return default
        return doc.get(key,default)

    async def set_setting(self,guild_id:int,key:str,value):
        await self.settings.update_one({"_id":str(guild_id)},
                                       {"$set":{key:value}},
                                       upsert=True)

class ThreadTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = ThreadStore(bot.db)
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    thread_group = app_commands.Group(
        name="thread",
        description="Tập lệnh theo dõi bài thread"
    )

    @thread_group.command(name="track", description="Bắt đầu theo dõi bài này")
    async def track(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "Lệnh chỉ dùng cho threads", ephemeral=True
            )
            return

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

        await self.store.set_thread(thread.id,interaction.guild.id,entry)
        await interaction.response.send_message(
            f"Đang theo dõi **{thread.name}** "
            f"(Sẽ lưu trữ sau {duration} minutes of inactivity)",
            ephemeral=True,
        )

    @thread_group.command(name="untrack", description="Ngừng theo dõi bài này")
    async def untrack(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "Lệnh chỉ dùng cho threads", ephemeral=True
            )
            return
        await self.store.delete_thread(thread.id)
        await interaction.response.send_message(
            f"Đã dừng theo dõi **{thread.name}**!", ephemeral=True
        )

    @thread_group.command(name="snooze", description="Cho ngủ* bài này")
    @app_commands.describe(days="Số ngày ngủ")
    async def snooze(self, interaction: discord.Interaction, days: int):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "Lệnh chỉ dùng cho threads", ephemeral=True
            )
            return
        entry = await self.store.get_thread(thread.id)
        if entry is None:
            await interaction.response.send_message(
                "Bài chưa theo dõi, hãy dùng lệnh '/thread track' trước", ephemeral=True
            )
            return
        entry["status"] = "snoozed"
        entry["snooze_until"] = _iso(_now() + timedelta(days=days))
        await self.store.set_thread(thread.id,interaction.guild_id, entry)
        await interaction.response.send_message(
            f"Thread sẽ được nhắc lại sau **{days}** ngày", ephemeral=True
        )

    @thread_group.command(name="pause", description="Tạm dừng theo dõi bài này")
    async def pause(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "Lệnh chỉ dùng cho threads", ephemeral=True
            )
            return

        entry = await self.store.get_thread(thread.id)
        if entry is None:
            await interaction.response.send_message(
                "Bài này đang không được theo dõi", ephemeral=True
            )
            return

        entry["status"] = "paused"
        await self.store.set_thread(thread.id,interaction.guild_id, entry)
        await interaction.response.send_message("Tạm dừng theo dõi bài này", ephemeral=True)

    @thread_group.command(name="resume", description="Tiếp tục theo dõi bài này")
    async def resume(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            await interaction.response.send_message(
                "Lệnh chỉ dùng cho threads", ephemeral=True
            )
            return

        entry = await self.store.get_thread(thread.id)
        if entry is None:
            await interaction.response.send_message(
                "Bài này đang không được theo dõi", ephemeral=True
            )
            return

        entry["status"] = "active"
        entry["snooze_until"] = None
        entry["reminder_stage"] = 0
        entry["last_activity"] = _iso(_now())
        await self.store.set_thread(thread.id,interaction.guild_id, entry)
        await interaction.response.send_message("Tiếp tục theo dõi bài này", ephemeral=True)

    @thread_group.command(name="status", description="Cho xem những bài đang được theo dõi")
    @app_commands.checks.has_permissions(manage_threads=True)
    async def status(self, interaction: discord.Interaction):
        threads = await self.store.all_threads(interaction.guild_id)
        if not threads:
            await interaction.response.send_message("Chưa có bài nào được theo dõi")
            return

        embed = discord.Embed(
            title="Tracked threads",
            color=discord.Color.blurple(),
        )
        for entry in threads:
            thread_id = entry["_id"]
            icon = self._status_icon(entry)
            channel = self.bot.get_channel(int(thread_id))
            name = channel.name if channel else f"Unknown ({thread_id})"
            awaiting = ", ".join(f"<@{u}>" for u in entry.get("awaiting", [])) or "-"
            embed.add_field(
                name=f"{icon} {name}",
                value=f"Status: `{entry['status']}` — Awaiting: {awaiting}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

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

        entry = await self.store.get_thread(message.channel.id)
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

        await self.store.set_thread(message.channel.id,message.guild.id, entry)

    # --- background reminder loop -------------------------------------------

    @tasks.loop(minutes=30)
    async def reminder_loop(self):
        for guild in self.bot.guilds:
            threads = await self.store.all_threads(guild.id)
            for entry in threads:
                await self._check_thread(guild, int(entry["_id"]), entry)

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    async def _check_thread(self, guild: discord.Guild, thread_id: int, entry: dict):
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
            await self._send_reminder(thread, entry, stage=3, thread_id=thread_id)
        elif fraction >= STAGE_THRESHOLDS[2] and stage < 2:
            await self._send_reminder(thread, entry, stage=2, thread_id=thread_id)
        elif fraction >= STAGE_THRESHOLDS[1] and stage < 1:
            entry["reminder_stage"] = 1
            await self.store.set_thread(thread_id,guild.id, entry)

    async def _send_reminder(self, thread: discord.Thread, entry: dict, stage: int,thread_id: int):
        awaiting = entry.get("awaiting", [])
        mentions = " ".join(f"<@{u}>" for u in awaiting) if awaiting else "everyone"

        if stage == 2:
            msg = f"Ủa alo rep role chưa — {mentions}, nhớ rep role nhé?"
        else:  # stage 3
            msg = f"⚠️ **{mentions}** — Bài này ngâm lâu quá rồi, rep role đi ."

        try:
            await thread.send(msg)
        except discord.Forbidden:
            pass

        entry["reminder_stage"] = stage
        await self.store.set_thread(thread_id,thread.guild.id, entry)

        if stage == 3:
            gm_channel_id = await self.store.get_setting(thread.guild.id, "gm_notify_channel_id")
            if gm_channel_id:
                gm_channel = self.bot.get_channel(gm_channel_id)
                if gm_channel:
                    try:
                        await gm_channel.send(
                            f"🔴 Bài role **#{thread.name}** sắp bị sủi cảo. "
                            f"Đang chờ rep role của {mentions}"
                        )
                    except discord.Forbidden:
                        pass

    # --- auto-unarchive with recap -------------------------------------------

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if before.archived and not after.archived:
            entry = await self.store.get_thread(after.id)
            if entry is None:
                return

            entry["status"] = "active"
            entry["reminder_stage"] = 0
            await self.store.set_thread(after.id,after.guild.id, entry)

            try:
                dormant_since = _parse(entry["last_activity"])
                days_dormant = (_now() - dormant_since).days
                embed = discord.Embed(
                    title="Chào mừng",
                    description=f"Bài này đã bị sủi **{days_dormant} ngày**.",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Tổng số từ",
                    value=str(entry.get("word_count_total", 0)),
                    inline=True,
                )
                await after.send(embed=embed)
            except discord.Forbidden:
                pass

    # --- config command --------------------------------------------------------

    @thread_group.command(name="config", description="Đặt cảnh báo cho bài thread")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.store.set_setting(interaction.guild.id, "gm_notify_channel_id",channel.id)
        await interaction.response.send_message(
            f"Thông báo thread sẽ được gửi ở {channel.mention}.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ThreadTracker(bot))