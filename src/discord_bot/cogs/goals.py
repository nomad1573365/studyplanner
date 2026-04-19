from src.core import services as sv, repository as rp, database as db
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger
from src.utils.async_tools import get_lock

logger = setup_logger(__name__)

import discord
from discord.ext import commands
from discord import app_commands

import datetime
from datetime import date
import asyncio


class GoalsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="make_goal",description="ゴール(参考書)の作成 dateはYYYY-MM-DDという形式で入れてください todayと入れると今日の日付が入ります")
    async def make_goal(self, interaction: discord.Interaction, goal_name: str, start_point: int, end_point: int, start_date: str, end_date: str):
        logger.info(f"COMMAND: /make_goal {goal_name} {start_point} {end_point} {start_date} {end_date} by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        start_date = await sv.change_to_date(start_date)
        end_date = await sv.change_to_date(end_date)

        await rp.add_goal(user_id, goal_name, start_point, end_point, start_date, end_date)
        await sv.apply_suggestions_to_daily_plan(user_id)
        self.bot.dispatch("delete_dashboard", user_id)
        self.bot.dispatch("generate_dashboard", user_id)
        await interaction.followup.send(":white_check_mark:ゴールが作成されました！")
        logger.info("/make_goal succeeded")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="goals",description="ゴール一覧を表示")
    async def goals(self, interaction: discord.Interaction):
        logger.info(f"COMMAND: /goals by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        goal_list = await rp.get_user_goal_list(user_id, date.today())
        output = discord_ui.show_goals_table(goal_list)
        await interaction.followup.send(f"{ output }")
        logger.info("/goals succeeded")
        
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="delete_goal",description="※注意※ゴールの削除です")
    async def delete_goal(self, interaction: discord.Interaction, goal_name: str):
        logger.info(f"COMMAND: /delete_goal {goal_name} by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        self.bot.dispatch("delete_dashboard", user_id)
        await asyncio.sleep(10)
        lock = get_lock(user_id)
        async with lock:
            await rp.delete_goal(user_id, goal_name)
            await interaction.followup.send(f":white_check_mark:正常に削除されました。")
        self.bot.dispatch("generate_dashboard", user_id)
        await sv.apply_suggestions_to_daily_plan(user_id)
        
        
async def setup(bot):
    await bot.add_cog(GoalsCog(bot))