import discord
from discord.ext import commands
from discord import app_commands
import logging
from dotenv import load_dotenv
import os

#from unicodedata import category

from Resource import EconomySys
import asyncio
#from word_system import WordStats
#from word_system import ConfirmView
from datetime import datetime, timedelta, timezone
import random

#wordstats = WordStats()

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

GUILD_ID = discord.Object(id=1221350780842414120)
#1221350780842414120 my server
#1413923727800008868 mi-ze server

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") :
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"Loaded cog: {filename}")

@bot.event
async def setup_hook():
    await load_cogs()

@bot.event
async def on_ready():
    print(f'{bot.user} Logged in!')

@bot.listen()
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith('hi'):
        await message.channel.send(f'Hello there {message.author.mention}!')


@bot.tree.command(name='hello',description='Say hi specifically to the bot')
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message('Hi there!')

#UmaBot

# -----------------------------STAT CHECK------------------------------------------#
@bot.tree.command(name='stats',description='Check your stats!')
async def stats(interaction: discord.Interaction):

    user = interaction.user
    speed = economy.get_field(user.id,"Spd")
    stamina = economy.get_field(user.id, "Stm")
    power = economy.get_field(user.id, "Pow")
    guts = economy.get_field(user.id, "Gut")
    wisdom = economy.get_field(user.id, "Wis")
    skill_p = economy.get_field(user.id, "s_point")
    carat = economy.get_field(user.id, "balance")

    embed = discord.Embed(title=f"{user.display_name}'s Statistic",
                          description="This is your stats",
                          color=0x52ff54)
    embed.set_author(name="Your Character Stat's")
    embed.set_thumbnail(url="https://res.cloudinary.com/haricebox/image/upload/v1784897807/i_carat.png")
    embed.add_field(name=f'<:speed:1530108148663451768> | <:stamina:1530108146519904256> | <:power:1530108150794027009> | <:guts:1530108152677138503> | <:wisdom:1530108154526826496>',
                    value=f"{speed}|{stamina}|{power}|{guts}|{wisdom}", inline=False)
    embed.add_field(name="Skill Points", value=f"{skill_p}", inline=True)
    embed.add_field(name="Your Carats", value=f"{carat}", inline=True)
    embed.set_footer(text="Tazuna quote here")
    await interaction.response.send_message(embed=embed)

DAILY_COOL_DOWN_HOURS = 24

@bot.tree.command(name='daily',description='Collect your daily rewards')
async def daily(interaction: discord.Interaction):
    """Claim daily coins"""
    user_id = interaction.user.id
    now = datetime.now(timezone.utc)

    last_daily_iso = economy.get_last_cd(user_id)

    if last_daily_iso is not None:
        last_claim = datetime.fromisoformat(last_daily_iso)
        next_available = last_claim + timedelta(hours=DAILY_COOL_DOWN_HOURS)

        if now < next_available:
            remaining = next_available - now
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)

            await interaction.response.send_message(
                f'{interaction.user.mention} Nhận thưởng hôm nay rồi mà?'
                f'Hỏi lại sau **{hours} giờ {minutes} phút và {seconds} giây ** nhé!'
                )
            return

    amount = 30 #45
    new_balance = economy.increment_field(user_id, "balance",amount)
    economy.set_last_cd(user_id,now.isoformat())

    await interaction.response.send_message(f'{interaction.user.mention} đã nhận thưởng hàng ngày {amount}<:I_Carat:1530209008814657689>'
                   f'Giờ bạn có {new_balance}<:I_Carat:1530209008814657689>'
                   )

@bot.command(name='transfer')
async def transfer(ctx, member: discord.Member, field ,amount: int):
    """Transfer money to another user"""
    if amount <= 0:
        await ctx.send("Amount must be positive!")
        return

    if member.id == ctx.author.id:
        await ctx.send("You can't pay yourself!")
        return

    result = economy.index_field(ctx.author.id, member.id,field ,amount)
    #transfer_money(ctx.author.id, member.id, amount)

    if result["success"]:
        await ctx.send(f'{ctx.author.mention}{field} paid {member.mention} {amount}')
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
async def set_balance(ctx, member: discord.Member,field: str, amount: int):
    """Set a user's balance (Admin only)"""
    economy.set_field(member.id, field, amount)
    await ctx.send(f'Set {member.mention}\'s {field} to {amount}')
#----------------------------WORDINGS----------------------------------#
"""
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


@bot.hybrid_command(name='countstart', description="Start counting words in this channel/thread")
@app_commands.describe(minutes="Optional: auto-stop after this many minutes")
async def count_start(ctx: commands.Context, minutes: float = None):
    if wordstats.is_active(ctx.channel.id):
        await ctx.send("Already active, use `!countstop` (or `/countstop`) to end it")
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
                    await ctx.send(f"Time's up, stopped counting.\n\n{report}")
            except asyncio.CancelledError:
                pass

        session = wordstats._get_session(ctx.channel.id)
        session.timer_task = asyncio.create_task(auto_stop())
    else:
        await ctx.send("Counting started")

@bot.hybrid_command(name='countstop', description="Stop counting and show the report")
async def countstop(ctx: commands.Context):
    if not wordstats.is_active(ctx.channel.id):
        await ctx.send("No counting currently active")
        return

    wordstats.stop(ctx.channel.id)
    report = wordstats.build_report(ctx.channel.id)
    await ctx.send(report)

BACKFILL_WARNING_THRESHOLD = 100
@bot.hybrid_command(name='countbackfill',description ='Total count the channel messages')
async def count_backfill(ctx: commands.Context):
    if wordstats.is_active(ctx.channel.id):
        await ctx.send("Already active, somewhere or here")
        return

    await ctx.defer() #Slashes need refill within 3s,backfill can take longer

    #Peek the threshold

    preview_count = 0
    async for _ in ctx.channel.history(limit= BACKFILL_WARNING_THRESHOLD+1):
        preview_count += 1

    if preview_count > BACKFILL_WARNING_THRESHOLD:
        view = ConfirmView(author_id=ctx.author.id)
        warm_msg = await ctx.send(
            f"This channel has more than {BACKFILL_WARNING_THRESHOLD}\n"
            f"This may take a while, Proceed?",
            view = view
            )
        await view.wait()
        if view.value is None:
            await warm_msg.edit(content="Timed out for confirmation, cancelling")
            return
        if view.value is False:
            return

    wordstats.start(ctx.channel.id)
    session = wordstats._get_session(ctx.channel.id)

    progress_msg = await ctx.send("Counting message history... 0 processed")
    processed = 0

    async for message in ctx.channel.history(limit= None, oldest_first = True):
        if session.backfill_cancelled:
            await progress_msg.edit(content=f"Backfill cancelled after {processed} messages")
            wordstats.stop(ctx.channel.id)

            if message.author.bot:
                continue

            wordstats.record_message(
                ctx.channel.id,
                message.author.id,
                message.author.display_name,
                message.content
            )

            processed += 1

            if processed % 200 == 0:
                await progress_msg.edit(content=f"Counting messages history ...{processed} processed")

            wordstats.stop(ctx.channel.id)
            report = wordstats.build_report(ctx.channel.id)
            await ctx.send(f"Backfill count complete({processed} messages(s))\n\n{report}")

@bot.hybrid_command(name='countcancel', description="Cancel an in-progress backfill count in this channel")
async def count_cancel(ctx: commands.Context):
    if not wordstats.is_active(ctx.channel.id):
        await ctx.send("Nothing is currently running in this channel.")
        return

    session = wordstats._get_session(ctx.channel.id)
    session.backfill_cancelled = True
    await ctx.send("Stopping the backfill... it'll halt after the current message.")
"""
# -----------------------------TRAINING EVENT-------------------------------------#
EVENT_EMOTE = "<:I_Carat:1530209008814657689>"
EVENT_DURATION = 10
MAX_TRAINEES =6

@bot.tree.command(name="training", description= "Force start a training phase")
@app_commands.describe(duration= "Seconds to stop a training phase")
async def ev_train(interaction: discord.Interaction,duration:int = EVENT_DURATION):

    await interaction.response.send_message(f"Training phase started in {duration} seconds",ephemeral=True)

    channel = interaction.channel

    train_type, default_multiplier =  economy.default_train_type()

    embed = discord.Embed(description=f"Today training regime will be {train_type}",
                          color=0x86e6fe)

    raw_train_value = economy.default_train_value()

    fail_check = economy.default_fail_value(raw_train_value)

    embed.set_thumbnail(url="https://res.cloudinary.com/haricebox/image/upload/v1784897807/i_carat.png")
    for i in range(1,7):

        embed.add_field(name=f"Friend {i}", value= "Pending", inline=True)
    embed.set_footer(text=f"Failure rate : {fail_check}%")

    event_message = await channel.send(embed=embed)

    await event_message.add_reaction(EVENT_EMOTE)

    #await asyncio.sleep(duration)

    # Collect Participants - exclude bot duhh
    trainee = set()
    end_time = asyncio.get_event_loop().time() + duration

    def check(paid):
        return(
            paid.message_id == event_message.id
            and str(paid.emoji) == EVENT_EMOTE
            and paid.member is not None
            and not paid.member.bot
        )
    while len(trainee) < MAX_TRAINEES:
        remaining = end_time - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            payload = await bot.wait_for("raw_reaction_add",
                                         timeout=remaining,
                                         check = check)
        except asyncio.TimeoutError:
            break

        if payload.member in trainee:
            continue
        trainee.add(payload.member)

        slot_index = len(trainee) -1
        embed.set_field_at(slot_index,name=f"Friend {slot_index +1}",
                           value = payload.member.mention,inline=True)
        current_reduction = len(trainee) *10
        current_adjusted_fail = max(0,fail_check - current_reduction)
        embed.set_footer(text=f"Failure rate : {current_adjusted_fail}%")

        await event_message.edit(embed=embed)

    try:
        await event_message.delete()
    except discord.NotFound:
        pass

    if not trainee:
        miss_embed = discord.Embed(description="but no one came..")
        event_response = await channel.send(embed=miss_embed)

        await asyncio.sleep(10)

        await event_response.delete()
        return
    participant_count = min(len(trainee), 6)
    adjusted_fail_check = max(0,fail_check - participant_count*10)

    success_rate = random.randint(0,100)

    if success_rate < adjusted_fail_check:
        miss_embed = discord.Embed(description="Training failed, ah dang!")
        event_response = await channel.send(embed=miss_embed)

        await asyncio.sleep(15)

        await event_response.delete()
        return
    else:
        mentions = ", ".join(u.mention for u in trainee)
        success_embed = discord.Embed(description=f"{mentions} have successfully trained",
                                      color=0x86e6fe
                                      )

        embed_result = await channel.send(embed=success_embed)

        bag = ["Spd", "Stm", "Pow", "Gut", "Wis"]

        for user in trainee:
            skill_point = default_multiplier[5]
            economy.increment_field(user.id,"s_point", skill_point)
            for i, stat_type in enumerate(bag):
                addition_value = round(raw_train_value * default_multiplier[i])
                economy.increment_field(user.id, stat_type, addition_value)


        await asyncio.sleep(30)

        await embed_result.delete()

#-----------------------------ITEMS----------------------------------#
import item_registry as ir_module
from item_registry import registry

item_id,item = registry.roll_item() # weighted roll, any category
item2_id,item2 = registry.roll_item(category="skill") # above but category
target = registry.get_upgrade_target(item_id) #what it upgrades into
chain = registry.get_full_chain(item_id) #the whole common to xxr ?

#-----------------------------DEBUGGING----------------------------------#
@bot.command(name='sync')
@commands.is_owner()
async def sync_commands(ctx):
    synced = await bot.tree.sync()
    print(f"Started syncing {len(synced)} commands globally.")
    for cmd in synced:
        print(f"  - /{cmd.name}: {cmd.description}")



# Run the bot
bot.run(token, log_handler=handler,log_level=logging.DEBUG)





