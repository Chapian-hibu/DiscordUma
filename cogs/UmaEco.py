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
import discord
import random
import asyncio

from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument

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
    def __init__(self,db):
        self.collection = db["umastat"]

    async def ensure_user(self, user_id) -> dict:
        uid = str(user_id)
        doc = await self.collection.find_one({"_id": uid})

        if doc is None:
            doc = _default_record()
            doc["_id"]= uid
            await self.collection.insert_one(doc)
            return doc

        default = _default_record()
        missing = {k: v for k,v in default.items() if k not in doc}
        if missing:
            await self.collection.update_one({"_id": uid}, {"$set":  missing})
            doc.update(missing)

        return doc
    # --- scalar fields: carat, last_daily, rank ---------------------------------

    async def set_field(self, user_id, field, value):
        uid = str(user_id)
        await self.ensure_user(uid)
        await self.collection.update_one({"_id": uid}, {"$set": {field: value}})

    async def get_field(self, user_id, field):
        doc = await self.ensure_user(user_id)
        return doc.get(field,-1)

    async def increment_field(self, user_id, field, amount=0):
        uid = str(user_id)
        await self.ensure_user(uid)
        result = await self.collection.find_one_and_update(
            {"_id": uid},
            {"$inc": {field: amount}},
            return_document=ReturnDocument.AFTER,
        )
        return result[field]

    async def decrement_field(self, user_id, field, amount):
        uid = str(user_id)
        await self.ensure_user(uid)

        result = await self.collection.find_one_and_update(
            {"_id": uid},
            {"$inc": {field: -amount}},
            return_document=ReturnDocument.AFTER
        )

        if result is None:
            return {"success": False, "message": "Insufficient amount"}
        return {"success": True, "new_balance": result[field]}

    async def index_field(self, from_user_id, to_user_id, field, amount):
        removal = await self.decrement_field(from_user_id, field, amount)
        if not removal["success"]:
            return removal
        await self.increment_field(to_user_id, field, amount)
        return {"success": True, "message": "Transfer completed"}

    # --- array fields: stats, flat bonus, mult bonus -----------------------------

    async def get_array(self, user_id, field: str) -> list:
        doc = await self.ensure_user(user_id)
        return doc[field]

    async def get_array_field(self, user_id, field: str, index: int):
        arr = await self.get_array(user_id, field)
        return arr[index]

    async def set_array_field(self, user_id, field: str, index: int, value):
        uid = str(user_id)
        await self.ensure_user(uid)
        await self.collection.update_one({"_id": uid},{"$set":{f"{field}.{index}":value}})
        return value

    async def increment_array_field(self, user_id, field: str, index: int, amount=1):
        uid = str(user_id)
        await self.ensure_user(uid)
        result = await self.collection.find_one_and_update(
            {"_id": uid},
            {"$inc": {f"{field}.{index}":amount}},
             return_document=ReturnDocument.AFTER,
        )
        return result[field][index]

    async def decrement_array_field(self, user_id, field: str, index: int, amount=1, floor: int = 0, allow_negative: bool = False):
        uid = str(user_id)
        doc = await self.ensure_user(uid)
        current = doc[field][index]

        if not allow_negative and current - amount < floor:
            return {"success": False, "message": "Insufficient amount", "current": current}

        result = await self.collection.find_one_and_update(
            {"_id": uid},
            {"$inc": {f"{field}.{index}":-amount}},
            return_document=ReturnDocument.AFTER,
        )
        return {"success": True, "new_value": result[field][index]}

    # --- convenience wrappers ------------------------------------------------

    async def get_stats(self, user_id, stat_name: str, field: str = "stats"):
        return await self.get_array_field(user_id, field, STAT_INDEX[stat_name])

    async def increment_stats(self, user_id, stat_name: str, amount=1, field: str = "stats"):
        return await self.increment_array_field(user_id, field, STAT_INDEX[stat_name], amount)

    async def decrement_stats(self, user_id, stat_name: str, amount=1, field: str = "stats", **kwargs):
        return await self.decrement_array_field(user_id, field, STAT_INDEX[stat_name], amount, **kwargs)

    # --- daily cooldown --------------------------------------------------------

    async def get_last_cd(self, user_id):
        return await self.get_field(user_id,"last_daily")

    async def set_last_cd(self, user_id, timestamp_iso):
        await self.set_field(user_id,"last_daily", timestamp_iso)

    # --- collectables ----------------------------------------------------------

    async def add_collectables(self, user_id, item_id, quantity=1):
        uid = str(user_id)
        await self.ensure_user(uid)
        result = await self.collection.find_one_and_update(
            {"_id": uid},
            {"$inc": {f"collectables.{item_id}": quantity}},
            return_document=ReturnDocument.AFTER,
        )
        return result["collectables"][item_id]

    async def remove_collectables(self, user_id, item_id, quantity=1):
        uid = str(user_id)
        doc = await self.ensure_user(uid)
        current = doc["collectables"].get(item_id,0)

        if current < quantity:
            return {"success": False, "message": "Not enough owned"}

        new_amount = current - quantity
        if new_amount == 0:
            await self.collection.update_one({"_id": uid},{"$unset":{f"collectables.{item_id}":""}})
        else:
            await self.collection.update_one({"_id": uid},{"$unset":{f"collectables.{item_id}":new_amount}})

        return {"success": True}

    async def get_collectables(self, user_id) -> dict:
        doc = await self.ensure_user(user_id)
        return doc["collectables"]

    async def has_collectables(self, user_id, item_id, quantity=1) -> bool:
        doc = await self.ensure_user(user_id)
        return doc["collectables"].get(item_id, 0) >= quantity

    # --- leaderboard -------------------------------------------------------------

    async def leaderboard(self, limit=10):
        cursor = self.collection.find().sort("carat",-1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [(doc["_id"],doc)for doc in docs]

    # --- training RNG helpers -----------------------------------------------------

    @staticmethod
    def default_train_type():
        weighted_lobby = {
            "Tốc độ": [0.8, 0, 0.4, 0, 0, 2],
            "Thể lực": [0, 0.7, 0, 0.3, 0, 2],
            "Sức mạnh": [0, 0.4, 0.6, 0, 0, 2],
            "Chạy bền": [0.3, 0, 0.3, 0.6, 0, 2],
            "Lý thuyết": [0, 0, 0.2, 0, 0.6, 2],
        }
        t_type = random.choice(list(weighted_lobby.keys()))
        return t_type, weighted_lobby[t_type]

    @staticmethod
    def default_train_value():
        return random.randint(1, 19)

    @staticmethod
    def default_fail_value(value):
        return round(value / 2 * 10)



#economy = UmaEcoStore()


# --------------------------- Cog (Discord commands) --------------------------- #

class UmaEcoCog(commands.Cog):
    def __init__(self, bot: commands.Bot,economy:UmaEcoStore):
        self.bot = bot
        self.economy = economy

    # -- /statistics -----------------------------------------------------------

    @app_commands.command(name="statistics", description="Check your stats!")
    async def stats(self, interaction: discord.Interaction):
        user = interaction.user
        stats_arr = await self.economy.get_array(user.id, "stats")
        skill_p = await self.economy.get_array_field(user.id, "stats", STAT_INDEX["SP"])  # was passing `user` instead of `user.id`
        carat = await self.economy.get_field(user.id, "carat")  # was reading field "stats" instead of "carat"

        speed, stamina, power, guts, wisdom = stats_arr[0], stats_arr[1], stats_arr[2], stats_arr[3], stats_arr[4]

        embed = discord.Embed(
            title=f"Dữ liệu của {user.display_name} ",
            description="Thông số của bạn nè",
            color=0x52FF54,
        )
        embed.set_author(name="Dữ liệu của bạn")
        embed.set_thumbnail(url="https://res.cloudinary.com/haricebox/image/upload/v1784897807/i_carat.png")
        embed.add_field(
            name="<:speed:1530108148663451768> | <:stamina:1530108146519904256> | "
                 "<:power:1530108150794027009> | <:guts:1530108152677138503> | <:wisdom:1530108154526826496>",
            value=f"{speed}|{stamina}|{power}|{guts}|{wisdom}",
            inline=False,
        )
        embed.add_field(name="Điểm kỹ năng", value=f"{skill_p}", inline=True)
        embed.add_field(name="Số carat đang sở hữu", value=f"{carat}", inline=True)
        embed.set_footer(text="Taz quote")
        await interaction.response.send_message(embed=embed)

    # -- /daily ------------------------------------------------------------------

    @app_commands.command(name="daily", description="Điểm danh hàng ngày")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        now = datetime.now(timezone.utc)

        last_daily_iso = await self.economy.get_last_cd(user_id)

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
        new_balance = await self.economy.increment_field(user_id, "carat", daily_reward)
        await self.economy.set_last_cd(user_id, now.isoformat())

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

        result = await self.economy.index_field(interaction.user.id, member.id, "carat", amount)

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
        await interaction.response.send_message(f"Training phase started in {duration} seconds", ephemeral= False)

        channel = interaction.channel

        train_type, default_multiplier = self.economy.default_train_type()

        embed = discord.Embed(
            description=f"Hôm nay chúng ta sẽ tập {train_type}",
            color=0x86E6FE,
        )
        raw_train_value = self.economy.default_train_value()
        fail_check = self.economy.default_fail_value(raw_train_value)

        embed.set_thumbnail(url="https://res.cloudinary.com/haricebox/image/upload/v1784897807/i_carat.png")
        for i in range(1, 7):
            embed.add_field(name=f"Bạn tập {i}", value="Đang chờ", inline=True)
        embed.set_footer(text=f"Tỉ lệ thất bại : {fail_check}%")

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
            embed.set_field_at(slot_index, name=f"Bạn tập {slot_index + 1}", value=payload.member.mention, inline=True)
            current_reduction = len(trainee) * 10
            current_adjusted_fail = max(0, fail_check - current_reduction)
            embed.set_footer(text=f"Tỉ lệ thất bại : {current_adjusted_fail}%")

            await event_message.edit(embed=embed)
        try:
            await event_message.delete()
        except discord.NotFound:
            pass

        if not trainee:
            miss_embed = discord.Embed(description="Nhưng chả ai đến cả..")
            await channel.send(embed=miss_embed)
            return

        participant_count = min(len(trainee), 6)
        adjusted_fail_check = max(0, fail_check - participant_count * 10)
        success_rate = random.randint(0, 100)

        if success_rate < adjusted_fail_check:
            miss_embed = discord.Embed(description="Luyện tập **thất bại..**")
            await channel.send(embed=miss_embed)
            return

        mentions = ", ".join(u.mention for u in trainee)
        success_embed = discord.Embed(
            description=f"{mentions} đã luyện tập thành công!",
            color=0x86E6FE,
        )
        await channel.send(embed=success_embed)

        for user in trainee:  # was "for users in trainee:" while referencing undefined `user.id` below -- fixed
            skill_point = default_multiplier[5]
            await self.economy.increment_array_field(user.id, "stats", STAT_INDEX["SP"], skill_point)

            for i in range(4):  # was "while i in range(4):" -- infinite loop with an out-of-scope `i`, and only
                # covered 4 of the 5 stats. Fixed to a proper for-loop over all 5 stat slots (0-4).
                addition_value = round(raw_train_value * default_multiplier[i])
                await self.economy.increment_array_field(user.id, "stats", i, addition_value)

    # -- /leaderboard --------------------------------------------------------------

    @app_commands.command(name="leaderboard", description="Cho xem bảng xếp hạng (carat)")
    async def leaderboard(self, interaction: discord.Interaction):
        top_users = await self.economy.leaderboard(10)

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
    store = UmaEcoStore(bot.db)
    bot.economy = store
    await bot.add_cog(UmaEcoCog(bot,store))