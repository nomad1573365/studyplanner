from src.core import services as sv, repository as rp, database as db
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

import discord
from discord.ext import commands
from discord import app_commands

import datetime
from datetime import date
from dotenv import load_dotenv
import os
load_dotenv()
from functools import wraps

ADMIN_ID = int(os.environ['ADMIN_ID'])



def is_admin(func):
    @wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        if ctx.author.id == ADMIN_ID:
            return await func(self, ctx, *args, **kwargs)
        else:
            await ctx.send("permission denied.")
            #raise PermissionError
    return wrapper

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="reload")
    @is_admin
    async def reload(self, ctx: commands.Context):
        logger.info(f"COMMAND: !reload by {ctx.author.id}")
        await self.bot.refresh_cogs()
        await ctx.send("cogs has been reloaded.", delete_after=3)
        
        
async def setup(bot):
    await bot.add_cog(AdminCog(bot))