from src.core import services as sv, repository as rp, database as db
from src.discord_bot import discord_ui
from src.utils.logger import setup_logger
from src.utils.async_tools import get_lock

logger = setup_logger(__name__)

import discord
from discord.ext import commands
from discord import app_commands, ui

import datetime
from datetime import date


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
        dmr = rp.PgDashboardMsgRepository()
        dashboard_cog = self.bot.get_cog("DashboardCog")

        lock = get_lock(user_id)
        async with lock:
            # goals削除時のCASCADEでdashboard_msgが消える前に、対象msg_idを退避する
            msgid_snapshot = await dmr.fetch_user_msgid_list(user_id)
            await rp.delete_goal(user_id, goal_name)
            if dashboard_cog and hasattr(dashboard_cog, "_generate_dashboard_unlocked"):
                await dashboard_cog._generate_dashboard_unlocked(
                    user_id,
                    msgid_snapshot=msgid_snapshot,
                )
            else:
                await sv.apply_suggestions_to_daily_plan(user_id)
                self.bot.dispatch("generate_dashboard", user_id)
        await interaction.followup.send(f":white_check_mark:正常に削除されました。")
        logger.info("/delete_goal succeeded")
        
        
        
class MakegoalModal(ui.Modal, title='Make Goal'):
    goal_name = ui.TextInput(
        label='ゴールの名前(参考書名など)',
        style=discord.TextStyle.short,
        placeholder='(例) FocusGold数3',
        required=True
    )

    start_point = ui.TextInput(
        label='開始位置(4ページから始めたい場合→4を入力)',
        style=discord.TextStyle.short,
        placeholder='1',
        required=True
    )

    end_point = ui.TextInput(
        label='終了位置(開始位置と同様)',
        style=discord.TextStyle.short,
        placeholder='100',
        required=True
    )

    start_date = ui.TextInput(
        label='開始日(空の場合は今日の日付が入力されます)',
        style=discord.TextStyle.short,
        placeholder='2026-4-20 (日付) または、100 (日後) のように入力',
        required=False,
        max_length=10
    )

    end_date = ui.TextInput(
        label='終了日(開始日と同様)',
        style=discord.TextStyle.short,
        placeholder='2026-4-20(日付) または、100(日後) のように入力',
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        goal_name_value = self.goal_name.value
        start_point_value = self.start_point.value
        end_point_value = self.end_point.value
        start_date_value = self.start_date.value
        end_date_value = self.end_date.value
        await interaction.response.send_message(
            'Modal submitted successfully!',
            ephemeral=True
        )  

async def setup(bot):
    await bot.add_cog(GoalsCog(bot))
