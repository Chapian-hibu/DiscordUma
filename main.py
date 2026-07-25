import discord
from discord.ext import commands
from discord import app_commands
import logging
from dotenv import load_dotenv
import os
from Resource import EconomySys
import asyncio
from word_system import WordStats

wordstats = WordStats()

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

    try:
        guild = discord.Object(id=1221350780842414120)
        synced = await bot.tree.sync(guild = guild)
        print (f'Synced {len(synced)} commands to guild!')

    except Exception as e:
        print(f'Error syncing commands: {e}')



@bot.listen()
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith('hi'):
        await message.channel.send(f'Hello there {message.author.mention}!')

@bot.listen()
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return
    await reaction.message.channel.send(f'{user.mention} reacted, FENG SHUI ULTIMATE')

GUILD_ID = discord.Object(id=1221350780842414120)

@bot.tree.command(name='hello',description='Say hi specifically to the bot',guild = GUILD_ID)
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message('Hi there!')

#UmaBot
#Check stats(WIP)
@bot.tree.command(name='stats',description='Check your stats!',guild = GUILD_ID)
async def stats(interaction: discord.Interaction):
    embed = discord.Embed(title="Uma A's Statistic", description="This is your basic stats", color=0x52ff54)
    embed.set_author(name="Your Character Stat's")
    embed.set_thumbnail(url="https://res.cloudinary.com/haricebox/image/upload/v1784897807/i_carat.png")
    embed.add_field(name=f'<:speed:1530108148663451768> | <:stamina:1530108146519904256> | <:power:1530108150794027009> | <:guts:1530108152677138503> | <:wisdom:1530108154526826496>', value="1200|1200| 1200|1200| 1200", inline=False)
    embed.add_field(name="Skill Points", value="6767", inline=True)
    embed.add_field(name="Your Carats", value="4", inline=True)
    embed.set_footer(text="Tazuna quote here")
    await interaction.response.send_message(embed=embed)


@bot.command(name='balance', aliases=['bal'])
async def balance(ctx):
    """Check your balance"""
    user_balance = economy.get_balance(ctx.author.id)
    msg = await ctx.send(f'{ctx.author.mention}, you have {user_balance}<:I_Carat:1530209008814657689>')
    await asyncio.sleep(5)
    await msg.delete()

@bot.command(name='daily')
async def daily(ctx):
    """Claim daily coins"""
    amount = 100
    new_balance = economy.add_money(ctx.author.id, amount)
    await ctx.send(f'{ctx.author.mention} claimed {amount}<:I_Carat:1530209008814657689> daily coins! New balance: {new_balance}<:I_Carat:1530209008814657689>')

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
        await ctx.send(f'{ctx.author.mention} paid {member.mention} {amount}<:I_Carat:1530209008814657689>!')
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
        description += f"**{index}.** {user.name} - {balances} <:I_Carat:1530209008814657689>\n"

    embed.description = description
    await ctx.send(embed=embed)

@bot.command(name='set balance')
@commands.has_permissions(administrator=True)
async def set_balance(ctx, member: discord.Member, amount: int):
    """Set a user's balance (Admin only)"""
    economy.set_balance(member.id, amount)
    await ctx.send(f'Set {member.mention}\'s balance to {amount}<:I_Carat:1530209008814657689>')

@bot.event
async def on_message(message):
    # ignore the bot's mess
    if message.author.bot:
        return

    #Ignore command
    ctx = await bot.get_context(message)
    if ctx.command is None:
        wordstats.record_message(
            channel_id=message.channel.id,
            user_id=message.author.id,
            user_name=message.author.display_name,
            content=message.content,
        )

    await bot.process_commands(message)

@bot.command(name='countstart')
async def count_start(ctx,minutes: float = None):
    """Start counting letters, you can add time behind !countstart 'time'"""
    if wordstats.is_active(ctx.channel.id):
        await ctx.send("Already active, '!countstop' to end it")
        return

    wordstats.start(ctx.channel.id)

    if minutes:
        await ctx.send(f"Started counting! Auto stop in **{minutes} minute(s)**")

        async def auto_stop():
            try:
                await asyncio.sleep(minutes * 60)
                if wordstats.is_active(ctx.channel.id):
                    wordstats.stop(ctx.channel.id)
                    report = wordstats.build_report(ctx.channel.id)
                    await ctx.send(f"Time's up , stopped counting. \n \n{report}")
            except asyncio.CancelledError:
                pass #manually stop
            session = wordstats._get_session(ctx.channel.id)
            session.timer_task = asyncio.create_task(auto_stop())
    else:
        ctx.send("Counting started")

@bot.command(name='countstop')
async def countstop(ctx):
    if not wordstats.is_active(ctx.channel.id):
        await ctx.send("No counting currently active")
        return
    wordstats.stop(ctx.channel.id)
    report = wordstats.build_report(ctx.channel.id)
    await ctx.send(report)


# Run the bot
bot.run(token, log_handler=handler,log_level=logging.DEBUG)





