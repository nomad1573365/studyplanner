from src.core import services as sv, repository as rp, database as db
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

import discord
from discord.ext import commands
from discord import app_commands

import datetime
from datetime import date



class StudyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def goal_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
        ) -> list[app_commands.Choice[str]]:
            user = rp.UserRepository()
            user_id = await user.ensure_user(str(interaction.user.id))
            tasks = await sv.get_today_progresses(user_id, date.today())
            choices = []
            for task in tasks:
                goal_name = task[0]
                if current.lower() in goal_name.lower():
                    choices.append(app_commands.Choice(name=goal_name, value=goal_name))
            return choices[:25]
    
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="rc",description="今日の勉強を記録(record)")
    @app_commands.autocomplete(goal_name=goal_name_autocomplete)
    async def rc(self, interaction: discord.Interaction, goal_name: str, amount: int):
        logger.info(f"COMMAND: /record {goal_name} {amount} by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        goal_id = await db.fetch_goal_id(user_id, goal_name)
        await sv.record_progress_by_id(goal_id, amount)
        self.bot.dispatch("update_dashboard", goal_id)
        await interaction.followup.send(f":white_check_mark:{ goal_name }({ amount })が記録されました！")
        logger.info("/rc succeeded")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="rc_forgot",description="記録し忘れた勉強量を、日付を指定して追加")
    @app_commands.autocomplete(goal_name=goal_name_autocomplete)
    async def rc_forgot(self, interaction: discord.Interaction, target_date: str, goal_name: str, amount: int):
        logger.info(f"COMMAND: /rc_forgot {target_date} {goal_name} by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        target_date = await sv.change_to_date(target_date)
        goal_id = await db.fetch_goal_id(user_id, goal_name)
        await sv.record_progress_by_name(user_id, goal_name, amount, target_date)
        await sv.apply_suggestions_to_daily_plan(user_id)
        self.bot.dispatch("update_dashboard", goal_id)
        await interaction.followup.send(f":white_check_mark:{ goal_name }({ amount })が記録されました！")
        logger.info("/rc_forgot succeeded")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="td",description="今日の予定・進捗の閲覧(today)")
    async def td(self, interaction: discord.Interaction):
        logger.info(f"COMMAND: /today by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        await sv.apply_suggestions_to_daily_plan(user_id)
        task_list = await sv.get_today_progresses(user_id, date.today())
        await interaction.followup.send(discord_ui.show_daily_summary(task_list, date.today()))
        logger.info("/td succeeded")
        
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="weight",description="今週の重み付けを設定(例:数学→1.5倍など)")
    @app_commands.autocomplete(goal_name=goal_name_autocomplete)
    async def weight(self, interaction: discord.Interaction, goal_name: str, weight: float):
        logger.info(f"COMMAND: /weight {goal_name} {weight} by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        today = date.today()
        if await sv.set_weekly_weight(user_id, goal_name, weight):
            await sv.apply_suggestions_to_daily_plan(user_id)
            await interaction.followup.send(f":white_check_mark:今週の{ goal_name }の重み付けを{ weight }倍にし、今日のリストに反映させました。")
            goal_id = await db.fetch_goal_id(user_id, goal_name)
            self.bot.dispatch("update_dashboard", goal_id)
            logger.info("/weight succeeded")
        else:
            await interaction.followup.send(f":x:重み付けを設定できませんでした。weightの値が正であること、ゴールに{ goal_name }が存在すること確認した上、もう一度お試しください:sob:")
            logger.info("/weight failed")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="reset_weight",description="今週の重み付けをすべて1にリセットします")
    async def reset_weight(self, interaction: discord.Interaction):
        logger.info(f"COMMAND: /reset_weight by {interaction.user.id}")
        await interaction.response.defer(ephemeral=True)
        user = rp.UserRepository()
        user_id = await user.ensure_user(str(interaction.user.id))
        deleted_count = await rp.delete_user_weight(user_id)
        if deleted_count:
            await interaction.followup.send(f":white_check_mark:{deleted_count}個の重み付けをリセットしました！")
            self.bot.dispatch("delete_dashboard", user_id)
            self.bot.dispatch("generate_dashboard", user_id)
            logger.info("/reset_weight succeeded")
        else:
            await interaction.followup.send(f"リセットすべきものはありませんでした。")
            logger.info("/reset_weight failed (or is not done)")
        await sv.apply_suggestions_to_daily_plan(user_id)
        

async def setup(bot):
    await bot.add_cog(StudyCog(bot))