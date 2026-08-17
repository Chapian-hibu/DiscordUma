"""
Economy system as a cog, originally economy.py

Data structure per user:
{
    "carat": int,
    "last_daily": iso timestamp or None,
    "stats": [int, int, int, int, int, int],
    "flat bonus": [int, int, int, int, int, int],
    "mult bonus": [int, int, int, int, int, int],
    "rank": str,
    "collectables": {item_id: quantity}
}
"""

import json
import os
import discord
import random
import asyncio

from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone

DATA_FILE = "economy_data.json"

STAT_INDEX = {
    "Spd": 0,
    "Stm": 1,
    "Pow": 2,
    "Gut": 3,
    "Wis": 4,
    "SP": 5,
}

DAILY_CD_HOURS = 24

E_CARAT = "<:I_Carat:1530209008814657689>"
EVENT_DURATION = 15
MAX_TRAINEES = 6



def _default_record() -> dict:
    return {
        "carat": 0,
        "last_daily": None,
        "stats": [0, 0, 0, 0, 0, 0],
        "flat bonus": [0, 0, 0, 0, 0, 0],
        "mult bonus": [0, 0, 0, 0, 0, 0],
        "rank": "Unranked",
        "collectables": {},
    }


# --------------------------- Persistence layer --------------------------- #

class UmaEcoStore:
    """Plain data store -- NOT a Cog. Instantiated once as the `economy` singleton below."""

    def __init__(self, data_file=DATA_FILE):
        self.data_file = data_file
        self.balances: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.balances, f, indent=4)

    def ensure_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.balances:
            self.balances[user_id] = _default_record()
            return

        if not isinstance(self.balances[user_id], dict):
            old_balance = self.balances[user_id]
            self.balances[user_id] = _default_record()
            self.balances[user_id]["carat"] = old_balance
            return

        default = _default_record()
        for key, default_value in default.items():
            if key not in self.balances[user_id]:
                self.balances[user_id][key] = default_value

    # --- scalar fields: carat, last_daily, rank ---------------------------------

    def set_field(self, user_id, field, value):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id][field] = value
        self.save()

    def get_field(self, user_id, field):
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id].get(field, -1)

    def increment_field(self, user_id, field, amount=0):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id][field] = self.balances[user_id].get(field, 0) + amount
        self.save()
        return self.balances[user_id][field]

    def decrement_field(self, user_id, field, amount):
        user_id = str(user_id)
        self.ensure_user(user_id)
        current_balance = self.balances[user_id][field]

        if current_balance < amount:
            return {"success": False, "message": "Insufficient amount"}

        self.balances[user_id][field] = current_balance - amount
        self.save()
        return {"success": True, "new_balance": self.balances[user_id][field]}

    def index_field(self, from_user_id, to_user_id, field, amount):
        removal = self.decrement_field(from_user_id, field, amount)
        if not removal["success"]:
            return removal
        self.increment_field(to_user_id, field, amount)
        return {"success": True, "message": "Transfer completed"}

    # --- array fields: stats, flat bonus, mult bonus -----------------------------

    def get_array_field(self, user_id, field: str, index: int):
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id][field][index]

    def get_array(self, user_id, field: str) -> list:
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id][field]

    def set_array_field(self, user_id, field: str, index: int, value):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id][field][index] = value
        self.save()
        return value

    def increment_array_field(self, user_id, field: str, index: int, amount=1):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id][field][index] += amount
        self.save()
        return self.balances[user_id][field][index]

    def decrement_array_field(self, user_id, field: str, index: int, amount=1, floor: int = 0, allow_negative: bool = False):
        user_id = str(user_id)
        self.ensure_user(user_id)
        current = self.balances[user_id][field][index]  # was reading the whole array, not the index -- fixed

        if not allow_negative and current - amount < floor:
            return {"success": False, "message": "Insufficient amount", "current": current}

        self.balances[user_id][field][index] = current - amount
        self.save()
        return {"success": True, "new_value": self.balances[user_id][field][index]}

    # --- convenience wrappers ------------------------------------------------

    def get_stats(self, user_id, stat_name: str, field: str = "stats"):
        return self.get_array_field(user_id, field, STAT_INDEX[stat_name])

    def increment_stats(self, user_id, stat_name: str, amount=1, field: str = "stats"):
        return self.increment_array_field(user_id, field, STAT_INDEX[stat_name], amount)

    def decrement_stats(self, user_id, stat_name: str, amount=1, field: str = "stats", **kwargs):
        return self.decrement_array_field(user_id, field, STAT_INDEX[stat_name], amount, **kwargs)

    # --- daily cooldown --------------------------------------------------------

    def get_last_cd(self, user_id):
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id]["last_daily"]

    def set_last_cd(self, user_id, timestamp_iso):
        user_id = str(user_id)
        self.ensure_user(user_id)
        self.balances[user_id]["last_daily"] = timestamp_iso
        self.save()

    # --- collectables ----------------------------------------------------------

    def add_collectables(self, user_id, item_id, quantity=1):
        user_id = str(user_id)
        self.ensure_user(user_id)
        current = self.balances[user_id]["collectables"].get(item_id, 0)
        self.balances[user_id]["collectables"][item_id] = current + quantity
        self.save()
        return self.balances[user_id]["collectables"][item_id]

    def remove_collectables(self, user_id, item_id, quantity=1):
        user_id = str(user_id)
        self.ensure_user(user_id)
        current = self.balances[user_id]["collectables"].get(item_id, 0)

        if current < quantity:
            return {"success": False, "message": "Not enough owned"}

        new_amount = current - quantity
        if new_amount == 0:
            del self.balances[user_id]["collectables"][item_id]
        else:
            self.balances[user_id]["collectables"][item_id] = new_amount

        self.save()
        return {"success": True}

    def get_collectables(self, user_id) -> dict:
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id]["collectables"]

    def has_collectables(self, user_id, item_id, quantity=1) -> bool:
        user_id = str(user_id)
        self.ensure_user(user_id)
        return self.balances[user_id]["collectables"].get(item_id, 0) >= quantity

    # --- leaderboard -------------------------------------------------------------

    def leaderboard(self, limit=10):
        sorted_users = sorted(
            self.balances.items(),
            key=lambda x: x[1]["carat"] if isinstance(x[1], dict) else x[1],
            reverse=True,
        )
        return sorted_users[:limit]

    # --- training RNG helpers -----------------------------------------------------

    @staticmethod
    def default_train_type():
        weighted_lobby = {
            "Spd": [0.8, 0, 0.4, 0, 0, 2],
            "Stm": [0, 0.7, 0, 0.3, 0, 2],
            "Pow": [0, 0.4, 0.6, 0, 0, 2],
            "Gut": [0.3, 0, 0.3, 0.6, 0, 2],
            "Wis": [0, 0, 0.2, 0, 0.6, 2],
        }
        t_type = random.choice(list(weighted_lobby.keys()))
        return t_type, weighted_lobby[t_type]

    @staticmethod
    def default_train_value():
        return random.randint(1, 19)

    @staticmethod
    def default_fail_value(value):
        return round(value / 2 * 10)


# Shared singleton other cogs can import: from cogs.UmaEco import economy
economy = UmaEcoStore()


# --------------------------- Cog (Discord commands) --------------------------- #

class UmaEcoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -- /statistics -----------------------------------------------------------

    @app_commands.command(name="statistics", description="Check your stats!")
    async def stats(self, interaction: discord.Interaction):
        user = interaction.user
        stats_arr = economy.get_array(user.id, "stats")
        skill_p = economy.get_array_field(user.id, "stats", STAT_INDEX["SP"])  # was passing `user` instead of `user.id`
        carat = economy.get_field(user.id, "carat")  # was reading field "stats" instead of "carat"

        speed, stamina, power, guts, wisdom = stats_arr[0], stats_arr[1], stats_arr[2], stats_arr[3], stats_arr[4]

        embed = discord.Embed(
            title=f"{user.display_name}'s Statistic",
            description="This is your stats",
            color=0x52FF54,
        )
        embed.set_author(name="Your Character Stat's")
        embed.set_thumbnail(url="https://res.cloudinary.com/haricebox/image/upload/v1784897807/i_carat.png")
        embed.add_field(
            name="<:speed:1530108148663451768> | <:stamina:1530108146519904256> | "
                 "<:power:1530108150794027009> | <:guts:1530108152677138503> | <:wisdom:1530108154526826496>",
            value=f"{speed}|{stamina}|{power}|{guts}|{wisdom}",
            inline=False,
        )
        embed.add_field(name="Skill Points", value=f"{skill_p}", inline=True)
        embed.add_field(name="Your Carats", value=f"{carat}", inline=True)
        embed.set_footer(text="Tazuna quote here")
        await interaction.response.send_message(embed=embed)

    # -- /daily ------------------------------------------------------------------

    @app_commands.command(name="daily", description="Collect your daily reward!")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        now = datetime.now(timezone.utc)

        last_daily_iso = economy.get_last_cd(user_id)

        if last_daily_iso is not None:
            last_claim = datetime.fromisoformat(last_daily_iso)
            next_available = last_claim + timedelta(hours=DAILY_CD_HOURS)

            if now < next_available:
                remaining = next_available - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)

                await interaction.response.send_message(
                    f"{interaction.user.mention} Nhận thưởng hôm nay rồi mà? "
                    f"Nhận lại sau **{hours} giờ {minutes} phút và {seconds} giây** nhé!"
                )
                return

        daily_reward = 30
        new_balance = economy.increment_field(user_id, "carat", daily_reward)
        economy.set_last_cd(user_id, now.isoformat())

        await interaction.response.send_message(
            f"{interaction.user.mention} đã nhận thưởng hàng ngày {daily_reward}{E_CARAT} "
            f"Giờ bạn có {new_balance}{E_CARAT}"
        )

    # -- /transfer -----------------------------------------------------------------

    @app_commands.command(name="transfer", description="Chuyển tiền đi nơi khác")
    @app_commands.describe(
        member="Chuyển cho ai đó?",
        amount="Chuyển bao nhiêu?",
    )
    async def transfer(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Tiền không có chuyển chi?", ephemeral=True)
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message("Chuyển cho bản thân làm gì z..", ephemeral=True)
            return

        result = economy.index_field(interaction.user.id, member.id, "carat", amount)

        if result["success"]:
            await interaction.response.send_message(
                f"{interaction.user.mention} đã chuyển {member.mention} {amount} {E_CARAT}"
            )
        else:
            await interaction.response.send_message(
                f"{interaction.user.mention}, {result['message']}", ephemeral=True
            )

    # -- /training -----------------------------------------------------------------

    @app_commands.command(name="training", description="Tạo một event tập luyện.")
    @app_commands.describe(duration="Thời gian chuẩn bị tập luyện?")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def training(self, interaction: discord.Interaction, duration: int = EVENT_DURATION):
        await interaction.response.send_message(f"Training phase started in {duration} seconds", ephemeral=True)

        channel = interaction.channel

        train_type, default_multiplier = economy.default_train_type()

        embed = discord.Embed(
            description=f"Today training regime will be {train_type}",
            color=0x86E6FE,
        )
        raw_train_value = economy.default_train_value()
        fail_check = economy.default_fail_value(raw_train_value)

        embed.set_thumbnail(url="https://res.cloudinary.com/haricebox/image/upload/v1784897807/i_carat.png")
        for i in range(1, 7):
            embed.add_field(name=f"Friend {i}", value="Pending", inline=True)
        embed.set_footer(text=f"Failure rate : {fail_check}%")

        event_message = await channel.send(embed=embed)
        await event_message.add_reaction(E_CARAT)

        trainee = set()
        end_time = asyncio.get_event_loop().time() + duration

        def check(paid):
            return (
                paid.message_id == event_message.id
                and str(paid.emoji) == E_CARAT
                and paid.member is not None
                and not paid.member.bot
            )

        while len(trainee) < MAX_TRAINEES:
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                payload = await self.bot.wait_for("raw_reaction_add", timeout=remaining, check=check)
            except asyncio.TimeoutError:
                break

            if payload.member in trainee:
                continue
            trainee.add(payload.member)

            slot_index = len(trainee) - 1
            embed.set_field_at(slot_index, name=f"Friend {slot_index + 1}", value=payload.member.mention, inline=True)
            current_reduction = len(trainee) * 10
            current_adjusted_fail = max(0, fail_check - current_reduction)
            embed.set_footer(text=f"Failure rate : {current_adjusted_fail}%")

            await event_message.edit(embed=embed)
        try:
            await event_message.delete()
        except discord.NotFound:
            pass

        if not trainee:
            miss_embed = discord.Embed(description="Nhưng chả ai đến cả..")
            event_response = await channel.send(embed=miss_embed)
            await asyncio.sleep(10)
            await event_response.delete()
            return

        participant_count = min(len(trainee), 6)
        adjusted_fail_check = max(0, fail_check - participant_count * 10)
        success_rate = random.randint(0, 100)

        if success_rate < adjusted_fail_check:
            miss_embed = discord.Embed(description="Luyện tập **thất bại..**")
            event_response = await channel.send(embed=miss_embed)
            await asyncio.sleep(15)
            await event_response.delete()
            return

        mentions = ", ".join(u.mention for u in trainee)
        success_embed = discord.Embed(
            description=f"{mentions} đã luyện thành công!",
            color=0x86E6FE,
        )
        embed_result = await channel.send(embed=success_embed)

        for user in trainee:  # was "for users in trainee:" while referencing undefined `user.id` below -- fixed
            skill_point = default_multiplier[5]
            economy.increment_array_field(user.id, "stats", STAT_INDEX["SP"], skill_point)

            for i in range(4):  # was "while i in range(4):" -- infinite loop with an out-of-scope `i`, and only
                # covered 4 of the 5 stats. Fixed to a proper for-loop over all 5 stat slots (0-4).
                addition_value = round(raw_train_value * default_multiplier[i])
                economy.increment_array_field(user.id, "stats", i, addition_value)

        await asyncio.sleep(30)
        await embed_result.delete()

    # -- /leaderboard --------------------------------------------------------------

    @app_commands.command(name="leaderboard", description="Cho xem bảng xếp hạng (carat)")
    async def leaderboard(self, interaction: discord.Interaction):
        top_users = economy.leaderboard(10)

        if not top_users:
            await interaction.response.send_message("Chưa có ai cả..")
            return

        embed = discord.Embed(title=f"{E_CARAT}BẢNG XẾP HẠNG{E_CARAT}", color=discord.Color.gold())

        description = ""
        for index, (user_id, record) in enumerate(top_users, 1):
            # was printing the whole user record dict instead of just their carat total -- fixed
            carat_amount = record["carat"] if isinstance(record, dict) else record
            user = await self.bot.fetch_user(int(user_id))
            description += f"**{index}.** {user.name} - {carat_amount} {E_CARAT}\n"

        embed.description = description
        await interaction.response.send_message(embed=embed)



#------------------------------Bot config----------------------------------#
async def setup(bot: commands.Bot):
    await bot.add_cog(UmaEcoCog(bot))