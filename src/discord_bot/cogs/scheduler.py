from src.core import services as sv, repository as rp, database as db
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

import discord
from discord.ext import tasks, commands

import datetime
from datetime import date

import zoneinfo
JST = zoneinfo.ZoneInfo("Asia/Tokyo")


scheduled_time = datetime.time(hour=0, minute=0, tzinfo=JST)

    
    
class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_update.start()
    
    def cog_unload(self):
        self.daily_update.cancel()
    
    @tasks.loop(time=scheduled_time)
    async def daily_update(self):
        await self.bot.wait_until_ready()
        logger.info("DAILY UPDATE STARTED")
        user_records = await db.fetch_active_userlist(within_date=3, ref_date=date.today())
        logger.info(f"DAILY UPDATE target_users={len(user_records)}")
        for record in user_records:
            user_id = record['id'] 
            try:
                await sv.apply_suggestions_to_daily_plan(user_id)
                self.bot.dispatch("generate_dashboard", user_id)
            except Exception as e:
                logger.error(
                    f"DAILY UPDATE failed: user_id={user_id}, error={e}",
                    exc_info=(type(e), e, e.__traceback__),
                )
        logger.info("DAILY UPDATE FINISHED")
        
        
async def setup(bot):
    await bot.add_cog(ScheduleCog(bot))
