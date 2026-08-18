import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os


#from unicodedata import category
#from word_system import WordStats
#from word_system import ConfirmView

#wordstats = WordStats()

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

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

#-----------------------------ITEMS----------------------------------#
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

#Bot setup running for a webservice
# Run the bot
bot.run(token, log_handler=handler,log_level=logging.DEBUG)





