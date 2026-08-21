"""
WIP gamb system not irl

"""

import random
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone

BET_CAP = 150
COOLDOWN_MINUTES = 10
SHARE_COOLDOWN = False  # False = coinflip and blackjack track separate cooldowns

E_CARAT = "<:I_Carat:1530209008814657689>"

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

# Coinflip result <-> Vietnamese display label. Using the SAME two-letter
# codes as the slash command choices means `result == choice.value` is a
# real comparison instead of comparing two disjoint vocabularies.
COIN_LABELS = {"hh": "Ngửa", "tt": "Sấp"}


# ---------------------------- Card / hand helpers ---------------------------- #

def new_deck() -> list[str]:
    deck = [f"{rank}{suit}" for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    return deck

def card_value(card: str) -> int:
    rank = card[:-1]
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)

def hand_value(hand: list[str]) -> int:
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c.startswith("A"))
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def is_blackjack(hand: list[str]) -> bool:
    return len(hand) == 2 and hand_value(hand) == 21

def format_hand(hand: list[str]) -> str:
    return " ".join(hand)

# ---------------------------- Cooldown helper ---------------------------- #

def _cooldown_field(game: str) -> str:
    return "last_gamble" if SHARE_COOLDOWN else f"last_gamble_{game}"

async def check_cooldown(economy, user_id: int, game: str) -> timedelta | None:
    """Returns remaining cooldown as a timedelta if still on cooldown, else None."""
    field = _cooldown_field(game)
    last_iso = await economy.get_field(user_id, field)
    if last_iso in (None, -1):
        return None

    last_played = datetime.fromisoformat(last_iso)
    next_available = last_played + timedelta(minutes=COOLDOWN_MINUTES)
    now = datetime.now(timezone.utc)

    if now < next_available:
        return next_available - now
    return None

async def start_cooldown(economy, user_id: int, game: str):
    field = _cooldown_field(game)
    await economy.set_field(user_id, field, datetime.now(timezone.utc).isoformat())


def format_remaining(remaining: timedelta) -> str:
    total_seconds = int(remaining.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds}s"

# ---------------------------- Bet validation ---------------------------- #

async def validate_bet(economy, user_id: int, bet: int) -> str | None:
    """Returns an error message string if the bet is invalid, else None."""
    if bet <= 0:
        return "Đặt cọc bằng 0 sao được chứ"
    if bet > BET_CAP:
        return f"Chỉ cho bet tối đa {BET_CAP} {E_CARAT}."
    balance = await economy.get_field(user_id, "carat")
    if balance < bet:
        return f"Có mỗi {balance} {E_CARAT} mà đòi chơi..."
    return None


# ---------------------------- Blackjack view ---------------------------- #

class BlackjackView(discord.ui.View):
    def __init__(self, player_id: int, bet: int, deck: list[str], player_hand: list[str], dealer_hand: list[str], economy):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.economy = economy
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("Đây không phải bài bạn", ephemeral=True)
            return False
        return True

    def _build_embed(self, reveal_dealer: bool, result_text: str | None = None) -> discord.Embed:
        embed = discord.Embed(title="🃏 Blackjack", color=0x86E6FE)
        embed.add_field(
            name=f"Your hand ({hand_value(self.player_hand)})",
            value=format_hand(self.player_hand),
            inline=False,
        )
        if reveal_dealer:
            embed.add_field(
                name=f"Tay nhà cái ({hand_value(self.dealer_hand)})",
                value=format_hand(self.dealer_hand),
                inline=False,
            )
        else:
            embed.add_field(
                name="Tay nhà cái",
                value=f"{self.dealer_hand[0]} ❓",
                inline=False,
            )
        embed.add_field(name="Bet", value=f"{self.bet} {E_CARAT}", inline=True)
        if result_text:
            embed.description = result_text
        return embed

    async def _resolve(self, interaction: discord.Interaction | None, result_text: str, payout: int):
        for child in self.children:
            child.disabled = True

        if payout > 0:
            await self.economy.increment_field(self.player_id, "carat", payout)

        embed = self._build_embed(reveal_dealer=True, result_text=result_text)

        if interaction is not None:
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message is not None:
            await self.message.edit(embed=embed, view=self)

        self.stop()

    def _dealer_play(self):
        while hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

    async def _settle_after_stand(self, interaction: discord.Interaction):
        self._dealer_play()
        player_total = hand_value(self.player_hand)
        dealer_total = hand_value(self.dealer_hand)

        if dealer_total > 21:
            await self._resolve(interaction, f"Nhà cái thua! You win **{self.bet * 2}** {E_CARAT}", self.bet * 2)
        elif player_total > dealer_total:
            await self._resolve(interaction, f"Bạn thắng! **+{self.bet * 2}** {E_CARAT}", self.bet * 2)
        elif player_total < dealer_total:
            await self._resolve(interaction, f"Nhà cái thắng, bạn lỗ **{self.bet}** {E_CARAT}", 0)
        else:
            await self._resolve(interaction, f"Hoà rồi, trả lại **{self.bet}** {E_CARAT} nè.", self.bet)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(self.deck.pop())
        total = hand_value(self.player_hand)

        if total > 21:
            await self._resolve(interaction, f"Bài nổ rồi boss ơi, mất trắng **{self.bet}** {E_CARAT}", 0)
            return

        embed = self._build_embed(reveal_dealer=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await self._settle_after_stand(interaction)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        # auto-stand on timeout
        self._dealer_play()
        player_total = hand_value(self.player_hand)
        dealer_total = hand_value(self.dealer_hand)

        if dealer_total > 21 or player_total > dealer_total:
            payout = self.bet * 2
            result_text = f"(Timed out, auto-stand) You win **{payout}** {E_CARAT}"
        elif player_total < dealer_total:
            payout = 0
            result_text = f"(Timed out, auto-stand) Dealer wins. You lose **{self.bet}** {E_CARAT}"
        else:
            payout = self.bet
            result_text = f"(Timed out, auto-stand) Push — your **{self.bet}** {E_CARAT} is returned."

        if payout > 0:
            await self.economy.increment_field(self.player_id, "carat", payout)

        if self.message is not None:
            embed = self._build_embed(reveal_dealer=True, result_text=result_text)
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.NotFound:
                pass


# ---------------------------- Cog ---------------------------- #

class UmaEvil(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.economy = bot.economy

    # -- /coinflip --------------------------------------------------------------

    @app_commands.command(name="coinflip", description=f"Flip a coin, bet up to {BET_CAP} carat")
    @app_commands.describe(bet="Cược bao nhiêu", choice="Sấp hay Ngửa")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Ngửa", value="hh"),
        app_commands.Choice(name="Sấp", value="tt"),
    ])
    async def coinflip(self, interaction: discord.Interaction, bet: int, choice: app_commands.Choice[str]):
        remaining = await check_cooldown(self.economy, interaction.user.id, "coinflip")
        if remaining:
            await interaction.response.send_message(
                f"Vừa chơi xong mà, chờ khoảng **{format_remaining(remaining)}**.", ephemeral=True
            )
            return

        error = await validate_bet(self.economy, interaction.user.id, bet)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        await start_cooldown(self.economy, interaction.user.id, "coinflip")
        await self.economy.decrement_field(interaction.user.id, "carat", bet)

        result = random.choice(["hh", "tt"])
        won = result == choice.value

        embed = discord.Embed(title="🪙 Tung đồng goldshi", color=0x86E6FE if won else 0xE64545)
        embed.add_field(name="Bạn chọn", value=choice.name, inline=True)
        embed.add_field(name="Kết quả", value=COIN_LABELS[result], inline=True)

        if won:
            payout = bet * 2
            await self.economy.increment_field(interaction.user.id, "carat", payout)
            embed.description = f"Bạn đã thắng **+{payout}** {E_CARAT} từ nhà cái"
        else:
            embed.description = f"Bạn đã bị ăn mất **{bet}** {E_CARAT} từ nhà cái"

        new_balance = await self.economy.get_field(interaction.user.id, "carat")
        embed.set_footer(text=f"Tài khoản mới của bạn: {new_balance}")
        await interaction.response.send_message(embed=embed)

    # -- /blackjack --------------------------------------------------------------

    @app_commands.command(name="blackjack", description=f"Play blackjack, bet up to {BET_CAP} carat")
    @app_commands.describe(bet="How much to bet")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        remaining = await check_cooldown(self.economy, interaction.user.id, "blackjack")
        if remaining:
            await interaction.response.send_message(
                f"Bạn vừa chơi thì phải? Chờ khoảng **{format_remaining(remaining)}**.", ephemeral=True
            )
            return

        error = await validate_bet(self.economy, interaction.user.id, bet)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        await start_cooldown(self.economy, interaction.user.id, "blackjack")
        await self.economy.decrement_field(interaction.user.id, "carat", bet)

        deck = new_deck()
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        view = BlackjackView(interaction.user.id, bet, deck, player_hand, dealer_hand, self.economy)

        # natural blackjack check -- resolves immediately, no hit/stand needed
        if is_blackjack(player_hand):
            for child in view.children:
                child.disabled = True

            if is_blackjack(dealer_hand):
                await self.economy.increment_field(interaction.user.id, "carat", bet)
                embed = view._build_embed(reveal_dealer=True, result_text=f"Cả hai blackjack? Trả lại  **{bet}** {E_CARAT} nè.")
            else:
                payout = round(bet * 2.5)  # returns stake + 3:2 winnings in one shot
                await self.economy.increment_field(interaction.user.id, "carat", payout)
                embed = view._build_embed(reveal_dealer=True, result_text=f"Blackjack! Bạn thắng **{payout}** {E_CARAT}")

            await interaction.response.send_message(embed=embed, view=view)
            view.stop()
            return

        embed = view._build_embed(reveal_dealer=False)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(UmaEvil(bot))