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
import uuid

import zoneinfo
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


load_dotenv()
TOKEN = os.environ['TOKEN']

lock = asyncio.Lock()
health_check_started = False

intents = discord.Intents.default()
intents.message_content = True


class MyBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(command_prefix="!", intents=intents)

    def _asyncio_exception_handler(self, loop, context):
        message = context.get("message", "Unknown asyncio exception")
        exc = context.get("exception")
        future = context.get("future")
        task = context.get("task")
        if exc:
            logger.error(
                f"ASYNCIO_UNHANDLED message={message}, future={future}, task={task}",
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        else:
            logger.error(
                f"ASYNCIO_UNHANDLED message={message}, future={future}, task={task}"
            )
        
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        orig_error = getattr(error, "original", error)
        trace_id = uuid.uuid4().hex[:8]
        command_name = interaction.command.qualified_name if interaction.command else "unknown"
        logger.error(
            f"APP_COMMAND_ERROR trace_id={trace_id} command={command_name} "
            f"user_id={interaction.user.id} channel_id={interaction.channel_id} "
            f"error_type={type(orig_error).__name__} detail={repr(orig_error)}",
            exc_info=(
                type(orig_error),
                orig_error,
                getattr(orig_error, "__traceback__", None),
            ),
        )
        
        if isinstance(orig_error, DomainError):
            msg = str(orig_error) or "値が不正です。ページ数などの入力を確認してみてください。"
        elif isinstance(orig_error, NotFoundError):
            msg = str(orig_error) or "データが見つかりませんでした。"
        elif isinstance(orig_error, ValueError):
            msg = str(orig_error) or "値が不正です。日付などを確認してみてください。"
        elif isinstance(orig_error, discord.HTTPException):
            if orig_error.status == 429:
                retry_after = getattr(orig_error, "retry_after", None)
                if retry_after is not None:
                    logger.error(f"【API制限】429 Too Many Requests: あと {retry_after:.2f} 秒待機が必要です。: {orig_error}")
                else:
                    logger.error(f"【API制限】429 Too Many Requests: {orig_error}")
                msg = f"アクセス制限中です。"
            else:
                logger.error(f"HTTPエラー: {orig_error}")
                msg = f"通信エラーが発生しました。"
        else:
            msg = "申し訳ございません。予期せぬエラーが発生しました。"

        msg = f":x:{msg}:sob:\n-# trace_id: `{trace_id}`"
 
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            logger.error(f"エラー応答送信失敗: {e}")

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command,
    ):
        logger.info(
            f"APP_COMMAND_OK command={command.qualified_name} "
            f"user_id={interaction.user.id} channel_id={interaction.channel_id}"
        )

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
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(self._asyncio_exception_handler)
        self.tree.on_error = self.on_app_command_error
        await db.init_db()
        await self.refresh_cogs()
        asyncio.create_task(cleaner())
        

bot = MyBot(intents=intents)
tree = bot.tree

@bot.event
async def on_ready():
    global health_check_started
    if not health_check_started:
        Thread(target=run_health_check, daemon=True).start()
        health_check_started = True
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
