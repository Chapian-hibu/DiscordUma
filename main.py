import os
import discord
import logging
import certifi
import threading

from discord.ext import commands
from dotenv import load_dotenv

from http.server import HTTPServer, BaseHTTPRequestHandler
from motor.motor_asyncio import AsyncIOMotorClient

from item_registry import ItemRegistry

import warnings
warnings.filterwarnings("ignore", module="discord")
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('discord.webhook').setLevel(logging.WARNING)
logging.getLogger('discord.client').setLevel(logging.WARNING)
logging.getLogger('discord.state').setLevel(logging.WARNING)



load_dotenv()



token = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

client = AsyncIOMotorClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
)

if not MONGO_URI or not MONGO_DB_NAME:
    raise RuntimeError("Missing MONGO_URI and MONGO_DB_NAME")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DiscordUma')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.mongo_client = None
bot.db = None

async def load_cogs():

    priority = ["UmaEco.py"]
    all_cogs = os.listdir("./cogs")
    ordered = [f for f in priority if f in all_cogs] + [f for f in all_cogs if f not in priority]

    for filename in ordered:
        if filename.endswith(".py") :
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"Loaded cog: {filename}")

async def connect_mongo():
    bot.mongo_client = AsyncIOMotorClient(MONGO_URI)
    bot.db = bot.mongo_client[MONGO_DB_NAME]

    try:
        await bot.mongo_client.admin.command("ping")
        logger.info("Connected to mongoDb successfully")
    except Exception as e:
        logger.error(f"Failed to connect to mongoDb: {e}")
        raise

    bot.item_registry = ItemRegistry(bot.db)
    await bot.item_registry.load()
    logger.info("Loaded item database")

@bot.event
async def setup_hook():
    await connect_mongo()
    await load_cogs()

    #Shutdown Mongo w the bot
    _original_close = bot.close

    async def _close_with_mongo():
        if bot.mongo_client:
            await bot.mongo_client.close()
            logger.info("Closed mongoDb connection")
        await _original_close()

    bot.close = _close_with_mongo()

#-----------------------------DEBUGGING----------------------------------#
@bot.event
async def on_ready():
    print(f'{bot.user} Logged in!')

@bot.tree.command(name='hello',description='Say hi specifically to the bot')
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message('Hi there!')

@bot.command(name='sync')
@commands.is_owner()
async def sync_commands(ctx):
    synced = await bot.tree.sync()
    print(f"Started syncing {len(synced)} commands globally.")
    for cmd in synced:
        print(f"  - /{cmd.name}: {cmd.description}")


#Bot setup running for a webservice
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


threading.Thread(target=run_health_server, daemon=True).start()
# Run the bot
bot.run(token, log_handler=handler,log_level=logging.DEBUG)





