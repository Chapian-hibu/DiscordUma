import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
from economy import EconomySys

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

#Initialize the economy system
economy = EconomySys()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='balance', aliases=['bal'])
async def balance(ctx):
    """Check your balance"""
    user_balance = economy.get_balance(ctx.author.id)
    await ctx.send(f'{ctx.author.mention}, you have **${user_balance}** coins!')


@bot.command(name='daily')
async def daily(ctx):
    """Claim daily coins"""
    amount = 100
    new_balance = economy.add_money(ctx.author.id, amount)
    await ctx.send(f'{ctx.author.mention} claimed **${amount}** daily coins! New balance: **${new_balance}**')

@bot.command(name='pay')
async def pay(ctx, member: discord.Member, amount: int):
    """Transfer money to another user"""
    if amount <= 0:
        await ctx.send("Amount must be positive!")
        return

    if member.id == ctx.author.id:
        await ctx.send("You can't pay yourself!")
        return

    result = economy.transfer_money(ctx.author.id, member.id, amount)

    if result["success"]:
        await ctx.send(f'{ctx.author.mention} paid {member.mention} **${amount}**!')
    else:
        await ctx.send(f'{ctx.author.mention}, {result["message"]}')

@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def leaderboard(ctx):
    """Show top 10 richest users"""
    top_users = economy.leaderboard(10)

    if not top_users:
        await ctx.send("No users in the economy yet!")
        return

    embed = discord.Embed(title="💰 Economy Leaderboard", color=discord.Color.gold())

    description = ""
    for index, (user_id, balances) in enumerate(top_users, 1):
        user = await bot.fetch_user(int(user_id))
        description += f"**{index}.** {user.name} - ${balances}\n"

    embed.description = description
    await ctx.send(embed=embed)

@bot.command(name='set balance')
@commands.has_permissions(administrator=True)
async def set_balance(ctx, member: discord.Member, amount: int):
    """Set a user's balance (Admin only)"""
    economy.set_balance(member.id, amount)
    await ctx.send(f'Set {member.mention}\'s balance to **${amount}**')

# Run the bot
bot.run(token, log_handler=handler,log_level=logging.DEBUG)





