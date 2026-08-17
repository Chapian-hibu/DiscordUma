"""
shop.py

Two systems, both spending carat and both pulling from the shared
item catalog (item_registry.py):

1. Shop -- a rotating stock of items that rerolls on a timer. Stock
   price is derived from rarity (RARITY_PRICE below), not stored in
   the catalog itself, so pricing can be tuned without touching
   game_items.json. Optionally restrict the shop to a specific tag
   (see SHOP_TAG_FILTER).

2. Lootbox -- open 1 or 10 at a time, weighted rarity per item (reuses
   the catalog's rarity_weights via registry.roll_item()).

Shop data is global (one shared rotating stock for the whole bot),
same as the economy data. Change SHOP_DATA_FILE's location or make
this per-guild later if you want separate shops per server.
"""

import json
import os
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone

from cogs.UmaEco import economy
from item_registry import registry

SHOP_DATA_FILE = "data/shop_data.json"
os.makedirs(os.path.dirname(SHOP_DATA_FILE), exist_ok=True)

SHOP_REROLL_HOURS = 24
SHOP_STOCK_SIZE = 6
# Set to a tag string (e.g. "featured") to restrict the shop to only
# items carrying that tag. None = pull from the whole catalog.
SHOP_TAG_FILTER = None

# Price per rarity tier -- tune freely, doesn't touch the catalog itself.
RARITY_PRICE = {
    "COM": 20,
    "RAR": 60,
    "SR": 180,
    "SSR": 450,
    "UR": 1200,
    "LEG": 4000,
}

RARITY_EMOJI = {
    "COM": "⚪",
    "RAR": "🟢",
    "SR": "🔵",
    "SSR": "🟣",
    "UR": "🟠",
    "LEG": "🔴",
}

E_CARAT = "<:I_Carat:1530209008814657689>"

LOOTBOX_PRICE = 100  # per box, whether opening 1 or 10


# ---------------------------- Shop persistence ---------------------------- #

class ShopStore:
    def __init__(self, data_file: str = SHOP_DATA_FILE):
        self.data_file = data_file
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"stock": [], "last_reroll": None}

    def save(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def get_stock(self) -> list[str]:
        return self.data["stock"]

    def get_last_reroll(self) -> datetime | None:
        if self.data["last_reroll"] is None:
            return None
        return datetime.fromisoformat(self.data["last_reroll"])

    def time_until_reroll(self) -> timedelta:
        last = self.get_last_reroll()
        if last is None:
            return timedelta(0)  # never rerolled -> due immediately
        next_reroll = last + timedelta(hours=SHOP_REROLL_HOURS)
        now = datetime.now(timezone.utc)
        remaining = next_reroll - now
        return remaining if remaining > timedelta(0) else timedelta(0)

    def is_due_for_reroll(self) -> bool:
        return self.time_until_reroll() <= timedelta(0)

    def reroll(self, size: int = SHOP_STOCK_SIZE, tag: str | None = SHOP_TAG_FILTER):
        """
        Rerolls stock, trying to spread picks evenly across the three
        categories (skill/equipment/consumable) for variety, filling
        any leftover slots with unrestricted rolls if a category runs
        out of eligible items under the tag filter.
        """
        categories = ["skill", "equipment", "consumable"]
        new_stock = []

        for i in range(size):
            category = categories[i % len(categories)]
            result = registry.roll_item(category=category, tag=tag)
            if result is None:
                # category+tag combo has nothing available -- fall back to any category
                result = registry.roll_item(tag=tag)
            if result is None:
                # tag itself has nothing available at all -- fall back to unrestricted
                result = registry.roll_item()
            if result is not None:
                item_id, _ = result
                new_stock.append(item_id)

        self.data["stock"] = new_stock
        self.data["last_reroll"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return new_stock

    def ensure_current_stock(self):
        """Rerolls automatically if the stock is empty or overdue -- call before showing/using the shop."""
        if not self.data["stock"] or self.is_due_for_reroll():
            self.reroll()


shop_store = ShopStore()


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

    shop_group = app_commands.Group(name="shop", description="Rotating item shop")

    # -- /shop view --------------------------------------------------------------

    @shop_group.command(name="view", description="See what's currently in the shop")
    async def shop_view(self, interaction: discord.Interaction):
        shop_store.ensure_current_stock()
        stock = shop_store.get_stock()

        embed = discord.Embed(title="🛒 Shop", color=0xF5C542)

        if not stock:
            embed.description = "The shop is empty right now — try again later."
        else:
            lines = []
            for item_id in stock:
                item = registry.get_item(item_id)
                if item is None:
                    continue
                emoji = RARITY_EMOJI.get(item["rarity"], "")
                price = item_price(item)
                lines.append(f"{emoji} **{item['name']}** ({item['rarity']}) — {price} {E_CARAT}\n`{item_id}`")
            embed.description = "\n\n".join(lines)

        remaining = shop_store.time_until_reroll()
        embed.set_footer(text=f"Next reroll in: {format_remaining(remaining)}")
        await interaction.response.send_message(embed=embed)

    # -- /shop buy --------------------------------------------------------------

    @shop_group.command(name="buy", description="Buy an item currently in the shop")
    @app_commands.describe(item_id="The item ID shown in /shop view")
    async def shop_buy(self, interaction: discord.Interaction, item_id: str):
        shop_store.ensure_current_stock()
        stock = shop_store.get_stock()

        if item_id not in stock:
            await interaction.response.send_message(
                "That item isn't currently in the shop. Check `/shop view` for what's available.",
                ephemeral=True,
            )
            return

        item = registry.get_item(item_id)
        if item is None:
            await interaction.response.send_message("That item doesn't exist anymore.", ephemeral=True)
            return

        price = item_price(item)
        balance = economy.get_field(interaction.user.id, "carat")

        if balance < price:
            await interaction.response.send_message(
                f"You need {price} {E_CARAT} but only have {balance}.", ephemeral=True
            )
            return

        economy.decrement_field(interaction.user.id, "carat", price)
        economy.add_collectables(interaction.user.id, item_id, 1)

        emoji = RARITY_EMOJI.get(item["rarity"], "")
        await interaction.response.send_message(
            f"{interaction.user.mention} bought {emoji} **{item['name']}** for {price} {E_CARAT}!"
        )

    @shop_buy.autocomplete("item_id")
    async def shop_buy_autocomplete(self, interaction: discord.Interaction, current: str):
        shop_store.ensure_current_stock()
        choices = []
        for iid in shop_store.get_stock():
            item = registry.get_item(iid)
            if item is None:
                continue
            label = f"{item['name']} ({item['rarity']}) - {item_price(item)} {E_CARAT}"
            if current.lower() in label.lower() or current.lower() in iid.lower():
                choices.append(app_commands.Choice(name=label[:100], value=iid))
        return choices[:25]

    # -- /shop reroll (admin override) --------------------------------------------

    @shop_group.command(name="reroll", description="Force an immediate shop reroll (admin only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def shop_reroll(self, interaction: discord.Interaction):
        shop_store.reroll()
        await interaction.response.send_message("Shop stock has been rerolled.", ephemeral=True)

    # -- /lootbox --------------------------------------------------------------

    @app_commands.command(name="lootbox", description=f"Open a lootbox ({LOOTBOX_PRICE} carat each)")
    @app_commands.describe(amount="Open 1 or 10 at a time")
    @app_commands.choices(amount=[
        app_commands.Choice(name="1", value=1),
        app_commands.Choice(name="10", value=10),
    ])
    async def lootbox(self, interaction: discord.Interaction, amount: app_commands.Choice[int]):
        count = amount.value
        total_cost = LOOTBOX_PRICE * count
        balance = economy.get_field(interaction.user.id, "carat")

        if balance < total_cost:
            await interaction.response.send_message(
                f"You need {total_cost} {E_CARAT} to open {count} lootbox(es), but only have {balance}.",
                ephemeral=True,
            )
            return

        economy.decrement_field(interaction.user.id, "carat", total_cost)

        results = []
        for _ in range(count):
            rolled = registry.roll_item()
            if rolled is None:
                continue
            item_id, item = rolled
            economy.add_collectables(interaction.user.id, item_id, 1)
            results.append((item_id, item))

        embed = discord.Embed(
            title=f"🎁 Opened {count} lootbox{'es' if count > 1 else ''}",
            color=0xF5C542,
        )

        # sort best-to-worst so pulls feel good regardless of RNG order
        rarity_order = registry._data["rarity_order"]
        results.sort(key=lambda r: rarity_order.index(r[1]["rarity"]), reverse=True)

        lines = []
        for item_id, item in results:
            emoji = RARITY_EMOJI.get(item["rarity"], "")
            lines.append(f"{emoji} **{item['name']}** ({item['rarity']})")
        embed.description = "\n".join(lines) if lines else "Nothing rolled -- catalog may be empty."

        embed.set_footer(text=f"Spent {total_cost} {E_CARAT}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))