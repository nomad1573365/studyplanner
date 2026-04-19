from src.core import services as sv, repository as rp, database as db
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger
from src.utils.async_tools import get_lock, cleaner
from src.core.exception import DomainError, NotFoundError

logger = setup_logger("bot")

extensions = ["study","goals","dashboard","admin","scheduler","general"]

import discord
from discord import app_commands
from dotenv import load_dotenv
import asyncio
from discord.ext import commands, tasks
from discord import ui
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import datetime
from datetime import date

import zoneinfo
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


load_dotenv()
TOKEN = os.environ['TOKEN']

lock = asyncio.Lock()

intents = discord.Intents.default()
intents.message_content = True


class MyBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(command_prefix="!", intents=intents)
        
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        orig_error = getattr(error, "original", error)
        
        logger.error(f"AppCommandエラー検知: {orig_error}")
        
        if isinstance(orig_error, DomainError):
            msg = str(orig_error) or "値が不正です。ページ数などの入力を確認してみてください。"
        elif isinstance(orig_error, NotFoundError):
            msg = "データが見つかりませんでした。"
        elif isinstance(orig_error, ValueError):
            msg = "値が不正です。日付などを確認してみてください。"
        else:
            msg = f"予期せぬエラーが発生しました: {orig_error}"
            raise error
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            logger.error(f"エラー応答送信失敗: {e}")

    async def refresh_cogs(self):
        for extension in extensions:
            try:
                extension = "src.discord_bot.cogs."+str(extension)
                if extension in self.extensions:
                    await self.reload_extension(extension)
                    logger.info(f"Reloaded extension: {extension}")
                else:
                    await self.load_extension(extension)
                    logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")
        
        await self.tree.sync()
    
    async def setup_hook(self):
        self.tree.on_error = self.on_app_command_error
        await db.init_db()
        await self.refresh_cogs()
        asyncio.create_task(cleaner())
        

bot = MyBot(intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    Thread(target=run_health_check, daemon=True).start()
    logger.info(f'SERVICE STARTED: We have logged in as {bot.user}')
    activity = "おはようございます" 
    await bot.change_presence(activity=discord.Game(activity))
    
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args): return

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()


bot.run(TOKEN)
