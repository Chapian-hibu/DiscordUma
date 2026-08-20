"""
shop.py

Two systems, both spending carat and both pulling from the shared
item catalog (item_registry.py):
1. Shop -- a rotating stock of items that rerolls on a timer. Stock
   price is derived from rarity (RARITY_PRICE below) Optionally restrict the shop to a specific tag
   (see SHOP_TAG_FILTER).
2. Lootbox

Shop data is global (one shared rotating stock for the whole bot),
same as the economy data. Change SHOP_DATA_FILE's location or make
this per-guild later if you want separate shops per server.
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone

SHOP_REROLL_HOURS = 24
SHOP_STOCK_SIZE = 6
SHOP_TAG_FILTER = None

# Price per rarity tier -- tune freely, doesn't touch the catalog itself.
RARITY_PRICE = {
    "COM": 20,
    "R": 200,
    "SR": 400,
    "SSR": 800,
    "UR": 1200,
    "LEG": 4000,
}

RARITY_EMOJI = {
    "COM": "⚪",
    "R": "🟢",
    "SR": "🔵",
    "SSR": "🟣",
    "UR": "🟠",
    "LEG": "🔴",
}

E_CARAT = "<:I_Carat:1530209008814657689>"

TICKET_PRICE = 150  


# ---------------------------- Shop persistence ---------------------------- #

class ShopStore:
    DOC_ID = "stock"

    def __init__(self,db,registry):
        self.collection = db["shop"]
        self.registry = registry
        print("rarity_weights:", self.registry._rarity_weights)
        print("items loaded:", len(self.registry._items))

    async def _get_doc(self)->dict:
        doc = await self.collection.find_one({"_id": self.DOC_ID})
        if doc is None:
            doc = {"_id": self.DOC_ID,"stock":[],"last_reroll":None}
            await self.collection.insert_one(doc)
        return doc

    async def get_stock(self)->list[str]:
        doc = await self._get_doc()
        return doc["stock"]

    async def get_last_reroll(self) -> timedelta:
        doc = await self._get_doc()
        if doc["last_reroll"] is None:
            return None
        return datetime.fromisoformat(doc["last_reroll"])

    async def time_until_reroll(self)->timedelta:
        last = await self.get_last_reroll()
        if last is None:
            return timedelta(0)
        next_reroll = last + timedelta(hours=SHOP_REROLL_HOURS)
        now = datetime.now(timezone.utc)
        remaining = next_reroll - now
        return remaining if remaining > timedelta(0) else timedelta(0)

    async def is_due_for_reroll(self) ->bool:
        remaining = await self.time_until_reroll()
        return remaining <= timedelta(0)

    async def reroll(self, size: int = SHOP_STOCK_SIZE, tag: str | None = SHOP_TAG_FILTER)->list[str]:
        """
        Rerolls stock, trying to spread picks evenly across the three
        categories (skill/equipment/consumable)
        """
        categories = ["equipment", "consumable"]
        new_stock = []

        for i in range(size):
            category = categories[i % len(categories)]
            result = self.registry.roll_item(category=category)
            if result is None:
                # category+tag combo has nothing available -- fall back to any category
                result = self.registry.roll_item()
            if result is None:
                # tag itself has nothing available at all -- fall back to unrestricted
                result = self.registry.roll_item()
            if result is not None:
                item_id, _ = result
                new_stock.append(item_id)

        await self.collection.update_one(
            {"_id": self.DOC_ID},
            {"$set": {"stock": new_stock,"last_reroll":datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return new_stock

    async def ensure_current_stock(self):
        """Rerolls automatically if the stock is empty or overdue """
        stock = await self.get_stock()
        due = await self.is_due_for_reroll()
        if not stock or due:
            await self.reroll()

#---------------------------SHOPPING-------------------------------#
def item_price(item: dict) -> int:
    return RARITY_PRICE.get(item["rarity"], 0)


def format_remaining(remaining: timedelta) -> str:
    total_seconds = int(remaining.total_seconds())
    hours, rem = divmod(total_seconds, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{hours}h {minutes}m"


# ---------------------------- Cog ---------------------------- #

class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.economy = bot.economy
        self.registry = bot.item_registry
        self.shop_store = ShopStore(bot.db,self.registry)

    shop_group = app_commands.Group(name="shop", description="Mở cửa hàng")

    # -- /shop view --------------------------------------------------------------

    @shop_group.command(name="view", description="Xem cửa hàng đang bán những gì")
    async def shop_view(self, interaction: discord.Interaction):
        await self.shop_store.ensure_current_stock()
        stock = await self.shop_store.get_stock()

        embed = discord.Embed(title="🛒 Cửa hàng ", color=0xF5C542)

        if not stock:
            embed.description = "The shop is empty right now — try again later."
        else:
            lines = []
            for item_id in stock:
                item = self.registry.get_item(item_id)
                if item is None:
                    continue
                emoji = RARITY_EMOJI.get(item["rarity"], "")
                price = item_price(item)
                lines.append(f"{emoji} **{item['name']}** ({item['rarity']}) — {price} {E_CARAT}\n`{item_id}`")
            embed.description = "\n\n".join(lines)

        remaining = await self.shop_store.time_until_reroll()
        embed.set_footer(text=f"Cửa hàng sẽ đổi lại sau: {format_remaining(remaining)}")
        await interaction.response.send_message(embed=embed)

    # -- /shop buy --------------------------------------------------------------

    @shop_group.command(name="buy", description="Mua gì đó từ cửa hàng")
    @app_commands.describe(item_id="Mã đồ dùng trong shop?")
    async def shop_buy(self, interaction: discord.Interaction, item_id: str):
        await self.shop_store.ensure_current_stock()
        stock = await self.shop_store.get_stock()

        if item_id not in stock:
            await interaction.response.send_message(
                "Vật phẩm không có trong cửa hàng, hãy dùng /show view để xem có gì nhé",
                ephemeral=True,
            )
            return

        item = self.registry.get_item(item_id)
        if item is None:
            await interaction.response.send_message("Vật phẩm không tồn tại!", ephemeral=True)
            return

        price = item_price(item)
        balance = await self.economy.get_field(interaction.user.id, "carat")

        if balance < price:
            await interaction.response.send_message(
                f"Bạn cần {price} {E_CARAT} để mua mà bạn chỉ có {balance}.", ephemeral=True
            )
            return

        await self.economy.decrement_field(interaction.user.id, "carat", price)
        await self.economy.add_collectables(interaction.user.id, item_id, 1)

        emoji = RARITY_EMOJI.get(item["rarity"], "")
        await interaction.response.send_message(
            f"{interaction.user.mention} đã mua {emoji} **{item['name']}** với giá {price} {E_CARAT}!"
        )

    @shop_buy.autocomplete("item_id")
    async def shop_buy_autocomplete(self, interaction: discord.Interaction, current: str):
        await self.shop_store.ensure_current_stock()
        stock = await self.shop_store.get_stock()
        choices = []
        for iid in stock:
            item = self.registry.get_item(iid)
            if item is None:
                continue
            label = f"{item['name']} ({item['rarity']}) - {item_price(item)} {E_CARAT}"
            if current.lower() in label.lower() or current.lower() in iid.lower():
                choices.append(app_commands.Choice(name=label[:100], value=iid))
        return choices[:25]

    # -- /shop reroll (admin override) --------------------------------------------

    @shop_group.command(name="reroll", description="Xoay tua cửa hàng ngay lập tức (Mod/admin)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def shop_reroll(self, interaction: discord.Interaction):
        await self.shop_store.reroll()
        await interaction.response.send_message("Cửa hàng đã đc làm mới")

    # -- /GACHAAAA --------------------------------------------------------------

    @app_commands.command(name="gacha", description=f"Mở thẻ hỗ trợ  ({TICKET_PRICE} carat / thẻ)")
    @app_commands.describe(amount="Mở 1 hay 10?")
    @app_commands.choices(amount=[
        app_commands.Choice(name="1", value=1),
        app_commands.Choice(name="10", value=10),
    ])
    async def lootbox(self, interaction: discord.Interaction, amount: app_commands.Choice[int]):
        count = amount.value
        total_cost = TICKET_PRICE * count
        balance = await self.economy.get_field(interaction.user.id, "carat")

        if balance < total_cost:
            await interaction.response.send_message(
                f"Bạn cần {total_cost} {E_CARAT} để gacha {count} thẻ, mà có mỗi {balance} {E_CARAT}.",
                ephemeral=True,
            )
            return

        await self.economy.decrement_field(interaction.user.id, "carat", total_cost)

        results = []
        for _ in range(count):
            rolled = self.registry.roll_item()
            if rolled is None:
                continue
            item_id, item = rolled
            await self.economy.add_collectables(interaction.user.id, item_id, 1)
            results.append((item_id, item))

        embed = discord.Embed(
            title=f"🎁 Gacha {count} thẻ",
            color=0xF5C542,
        )

        # luôn xếp tốt nhất cho tệ nhất
        rarity_order = self.registry.rarity_order
        results.sort(key=lambda r: rarity_order.index(r[1]["rarity"]), reverse=True)

        lines = []
        for item_id, item in results:
            emoji = RARITY_EMOJI.get(item["rarity"], "")
            lines.append(f"{emoji} **{item['name']}** ({item['rarity']})")
        embed.description = "\n".join(lines) if lines else "Không ra gì, do admin chưa thêm đồ"

        embed.set_footer(text=f"Spent {total_cost} {E_CARAT}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))